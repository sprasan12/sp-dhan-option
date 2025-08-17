"""
Dual-Mode Trading Bot - Supports Live Trading and Demo Trading (Backtesting)
"""

import os
import time
import signal
import sys
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import deque

# Import our modular components
from models.candle import Candle
from utils.market_utils import is_market_hours, is_trading_ending, round_to_tick
from strategies.candle_strategy import CandleStrategy
from brokers.dhan_broker import DhanBroker
from brokers.demo_broker import DemoBroker
from utils.market_data import MarketDataWebSocket, process_ticker_data
from position.position_manager import PositionManager
from utils.config import TradingConfig
from utils.historical_data import HistoricalDataFetcher
from demo.demo_server import DemoServer
from demo.demo_data_client import DemoDataClient
from utils.logger import TradingLogger
from utils.account_manager import AccountManager
import logging

# Load environment variables
load_dotenv()

class DualModeTradingBot:
    """Trading bot that supports both live and demo trading modes"""
    
    def __init__(self):
        # Load configuration
        self.config = TradingConfig()
        self.config.validate_config()
        self.config.print_config()
        
        # Initialize logger
        log_level = getattr(logging, self.config.log_level, logging.INFO)
        self.logger = TradingLogger(
            log_dir=self.config.log_dir,
            log_level=log_level
        )
        
        # Initialize account manager
        self.account_manager = AccountManager(self.config, self.logger)
        
        # Log configuration
        config_dict = {
            'Mode': self.config.mode.value.upper(),
            'Tick Size': self.config.tick_size,
            'Max 15-min Candles': self.config.max_15min_candles,
            'Trading Quantity': self.config.quantity,
            'Account Start Balance': f"₹{self.config.account_start_balance:,.2f}",
            'Fixed SL Amount': f"₹{self.config.get_fixed_sl_amount():,.2f}",
            'Lot Size': self.config.lot_size,
            'Max SL % of Price': f"{self.config.max_sl_percentage_of_price}%",
            'Swing Look Back': self.config.swing_look_back,
            'Log Level': self.config.log_level,
            'Log to File': self.config.log_to_file,
            'Log Directory': self.config.log_dir
        }
        
        if self.config.is_live_mode():
            config_dict.update({
                'Client ID': self.config.client_id,
                'Access Token': self.config.access_token
            })
        else:
            config_dict.update({
                'Demo Start Date': self.config.demo_start_date,
                'Demo Symbol': self.config.demo_symbol,
                'Demo Interval': f"{self.config.demo_interval_minutes} minutes",
                'Demo Server Port': self.config.demo_server_port,
                'Demo Stream Speed': f"{self.config.demo_stream_interval_seconds} seconds per candle",
                'Historical Data Days': self.config.historical_data_days
            })
        
        self.logger.log_config(config_dict)
        
        # Initialize components based on mode
        if self.config.is_live_mode():
            self._init_live_mode()
        else:
            self._init_demo_mode()
        
        # Common components
        self.strategy = CandleStrategy(
            tick_size=self.config.tick_size, 
            swing_look_back=self.config.swing_look_back,
            logger=self.logger,
            exit_callback=self._on_strategy_trade_exit
        )
        self.position_manager = PositionManager(self.broker, self.account_manager, self.config.tick_size)
        
        # Market data
        self.instruments_df = None
        self.symbol = self.config.demo_symbol if self.config.is_demo_mode() else os.getenv('TRADING_SYMBOL', 'NIFTY 21 AUG 24700 CALL')
        
        # Data sources
        self.websocket = None
        self.demo_server = None
        self.demo_client = None
        
        # Candle tracking
        self.fifteen_min_candles = deque(maxlen=self.config.max_15min_candles)
        self.one_min_candles = deque(maxlen=100)
        self.current_15min_candle = None
        self.current_1min_candle = None
        self.last_15min_candle_time = None
        self.last_1min_candle_time = None
        
        # Strategy state
        self.sweep_detected = False
        self.sweep_low = None
        self.waiting_for_sweep = False
        self.last_bear_candles = deque(maxlen=10)
        
        self.logger.info(f"Trading Bot initialized in {self.config.mode.value.upper()} mode")
        self.logger.info(f"Trading Symbol: {self.symbol}")
        self.logger.info(f"Account Balance: ₹{self.account_manager.get_current_balance():,.2f}")
    
    def _init_live_mode(self):
        """Initialize components for live trading mode"""
        self.logger.info("Initializing LIVE trading mode...")
        
        # Initialize real broker
        self.broker = DhanBroker(
            self.config.client_id, 
            self.config.access_token, 
            self.config.tick_size
        )
        
        # Initialize historical data fetcher for getting initial candles
        self.historical_fetcher = HistoricalDataFetcher(
            self.config.access_token,
            self.config.client_id
        )
        
        self.logger.info("Live mode components initialized")
    
    def _init_demo_mode(self):
        """Initialize components for demo trading mode"""
        self.logger.info("Initializing DEMO trading mode...")
        
        # Initialize demo broker with account manager
        self.broker = DemoBroker(self.config.tick_size, self.account_manager)
        
        # Initialize historical data fetcher
        self.historical_fetcher = HistoricalDataFetcher(
            self.config.access_token or "demo_token",
            self.config.client_id or "demo_client"
        )
        
        self.logger.info("Demo mode components initialized")
    
    def load_instruments(self):
        """Load instruments list from Dhan API"""
        try:
            # Fetch the detailed instrument list
            url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
            self.instruments_df = pd.read_csv(url, low_memory=False)
            
            # Save the CSV locally in the current directory
            try:
                local_path = os.path.join(os.getcwd(), "dhan_instruments.csv")
                self.instruments_df.to_csv(local_path, index=False)
                print(f"Instruments list loaded and saved to {local_path}")
            except Exception as e:
                print(f"Warning: Could not save CSV file: {e}")
                print("Continuing without saving the file...")
            
            # Print some debug information about available options
            options_df = self.instruments_df[
                (self.instruments_df['EXCH_ID'] == 'NSE') & 
                (self.instruments_df['SEGMENT'] == 'D') &
                (self.instruments_df['INSTRUMENT'] == 'OPTIDX')
            ]
            
            print(f"\nAvailable NSE Options: {len(options_df)}")
            print(f"Trading Symbol: {self.symbol}")
            
        except Exception as e:
            print(f"Error loading instruments list: {e}")
            return None
    
    def initialize_historical_data(self):
        """Initialize historical data based on mode"""
        if self.config.is_live_mode():
            self._initialize_live_historical_data()
        else:
            self._initialize_demo_historical_data()
    
    def _initialize_live_historical_data(self):
        """Initialize historical data for live trading"""
        print("Fetching last 30 days of 15-minute candles for live trading...")
        
        # Fetch last 30 days of 15-minute candles
        historical_data = self.historical_fetcher.fetch_15min_candles(
            symbol=self.symbol,
            instruments_df=self.instruments_df,
            days_back=30
        )
        
        if historical_data is not None and len(historical_data) > 0:
            # Convert to Candle objects and add to 15-minute candle list
            for _, row in historical_data.iterrows():
                candle = Candle(
                    timestamp=row['timestamp'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']) if 'volume' in row else 0
                )
                self.fifteen_min_candles.append(candle)
            
            print(f"Loaded {len(self.fifteen_min_candles)} historical 15-minute candles")
            
            # Set last candle time
            if self.fifteen_min_candles:
                self.last_15min_candle_time = self.fifteen_min_candles[-1].timestamp
        else:
            print("Warning: Could not fetch historical data for live trading")
    
    def _initialize_demo_historical_data(self):
        """Initialize historical data for demo trading"""
        print("Fetching historical data for demo trading...")
        
        # Calculate date range
        start_date = self.config.get_demo_start_datetime()
        end_date = start_date + timedelta(days=self.config.historical_data_days)
        
        # Fetch 1-minute candles for demo
        historical_data = self.historical_fetcher.fetch_1min_candles(
            symbol=self.symbol,
            instruments_df=self.instruments_df,
            start_date=start_date,
            end_date=end_date
        )
        
        if historical_data is not None and len(historical_data) > 0:
            # Create demo server
            self.demo_server = DemoServer(
                historical_data=historical_data,
                start_date=start_date,
                interval_minutes=self.config.demo_interval_minutes,
                port=self.config.demo_server_port,
                stream_interval_seconds=self.config.demo_stream_interval_seconds
            )
            
            # Create demo client
            self.demo_client = DemoDataClient(f"http://localhost:{self.config.demo_server_port}")
            
            print(f"Demo server initialized with {len(historical_data)} 1-minute candles")
            print(f"Date range: {start_date.date()} to {end_date.date()}")
        else:
            print("Warning: Could not fetch historical data for demo trading")
    
    def start_demo_server(self):
        """Start the demo server in a separate thread"""
        if self.demo_server:
            import threading
            server_thread = threading.Thread(target=self.demo_server.run)
            server_thread.daemon = True
            server_thread.start()
            
            # Wait for server to start
            time.sleep(3)
            
            # Connect client to server
            if self.demo_client.connect():
                print("Demo server started and client connected")
                return True
            else:
                print("Failed to connect to demo server")
                return False
        return False
    
    def setup_live_websocket(self):
        """Setup live trading WebSocket"""
        if self.config.is_live_mode():
            # Get security ID
            security_id = self.broker.get_security_id(self.symbol, self.instruments_df)
            if not security_id:
                print(f"Could not find security ID for symbol {self.symbol}")
                return False
            
            # Create WebSocket
            self.websocket = MarketDataWebSocket(
                access_token=self.config.access_token,
                client_id=self.config.client_id,
                on_message_callback=self._on_websocket_message,
                on_error_callback=self._on_websocket_error,
                on_close_callback=self._on_websocket_close
            )
            
            # Connect to WebSocket
            if self.websocket.connect(security_id):
                print("Live WebSocket connected successfully")
                return True
            else:
                print("Failed to connect to live WebSocket")
                return False
        
        return False
    
    def _on_websocket_message(self, ws, message):
        """Handle WebSocket messages for live trading"""
        try:
            # Process ticker data
            process_ticker_data(message, None, self._on_price_update)
        except Exception as e:
            print(f"Error processing WebSocket message: {e}")
    
    def _on_websocket_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
    
    def _on_websocket_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print(f"WebSocket closed: {close_status_code} - {close_msg}")
    
    def _on_price_update(self, price_or_candle_data, timestamp, security_id):
        """Handle price updates from live or demo data"""
        # Handle both live mode (price) and demo mode (candle_data)
        if isinstance(price_or_candle_data, dict):
            # Demo mode - we have complete candle data
            candle_data = price_or_candle_data
            price = candle_data["close"]
            # Update 1-minute candle with complete OHLC data
            self._update_1min_candle_with_data(candle_data, timestamp)
            # Log candle data
            self.logger.log_candle_data(
                "1min", timestamp,
                float(candle_data["open"]),
                float(candle_data["high"]),
                float(candle_data["low"]),
                float(candle_data["close"])
            )
        else:
            # Live mode - we have just the price
            price = price_or_candle_data
            # Update 1-minute candle with just the price
            self._update_1min_candle(price, timestamp)
            # Log price update
            self.logger.log_price_update(price, timestamp, "live")
        
        # Run strategy
        self._run_strategy_logic(price, timestamp)
    
    def _update_1min_candle(self, price, timestamp):
        """Update 1-minute candle with just price (for live mode)"""
        self.strategy.update_1min_candle(price, timestamp)
    
    def _update_1min_candle_with_data(self, candle_data, timestamp):
        """Update 1-minute candle with complete OHLC data (for demo mode)"""
        self.strategy.update_1min_candle_with_data(candle_data, timestamp)
    
    def _on_strategy_trade_exit(self, exit_price, reason):
        """Callback method called when strategy exits a trade"""
        self.logger.info(f"Strategy trade exit callback: {reason} at {exit_price:.2f}")
        # Reset position manager state
        self.position_manager.handle_trade_exit(exit_price, reason)
        
        # Get current account balance for logging
        try:
            account_balance = self.broker.get_account_balance()
            # Update the strategy's exit_trade call with account balance
            self.strategy.exit_trade(exit_price, reason, account_balance)
        except Exception as e:
            self.logger.error(f"Failed to get account balance: {e}")
            # Fallback to exit without account balance
            self.strategy.exit_trade(exit_price, reason)
    
    def _run_strategy_logic(self, price, timestamp):
        """Run the main strategy logic"""
        # Check if we're in a trade - if so, manage the trade
        if self.strategy.in_trade:
            # Check for trade exit (stop loss or target)
            exit_signal = self.strategy.check_trade_exit(price)
            if exit_signal:
                # Exit the trade in strategy (callback will handle position manager reset)
                self.strategy.exit_trade(exit_signal['price'], exit_signal['reason'])
                return
            
            # Check if we should move stop loss (50% profit rule)
            if self.strategy.should_move_stop_loss(price):
                # Once 50% profit is reached, continuously move SL to new swing lows
                if self.strategy.should_move_stop_loss_continuously():
                    self.strategy.move_stop_loss_to_swing_low()
            
            return  # Don't look for new entries while in a position
        
        # Not in trade - look for new entry opportunities
        # Check for sweep conditions using the current 1-minute candle
        sweep_trigger = None
        if self.strategy.current_1min_candle:
            sweep_trigger = self.strategy.check_sweep_conditions(self.strategy.current_1min_candle)
        
        if sweep_trigger:
            self.logger.info(f"Trade trigger detected: {sweep_trigger}")
            
            # Calculate target based on 2:1 RR
            entry_price = sweep_trigger['entry']
            stop_loss = sweep_trigger['stop_loss']
            risk = entry_price - stop_loss
            target = entry_price + (2 * risk)  # 2:1 Risk:Reward
            
            # Log trade entry
            self.logger.log_trade_entry(
                entry_price, stop_loss, target,
                sweep_trigger.get('type', 'UNKNOWN'),
                self.symbol
            )
            
            # Enter the trade using strategy's trade management
            self.strategy.enter_trade(entry_price, stop_loss, target)
            
            # Also update position manager for order placement
            symbol = self.symbol
            instruments_df = self.instruments_df
            
            success = self.position_manager.enter_trade_with_trigger(
                sweep_trigger, 
                sweep_trigger.get('type', 'UNKNOWN'),
                symbol,
                instruments_df
            )
            
            if success:
                self.logger.info("✅ Trade entered successfully!")
            else:
                self.logger.error("❌ Failed to enter trade")
                # Reset strategy if order placement failed
                self.strategy.exit_trade(entry_price, "order_failed")
    
    def _reset_sweep_detection(self):
        """Reset sweep detection after trade entry"""
        self.sweep_detected = False
        self.sweep_low = None
        self.waiting_for_sweep = False
    
    def start_trading(self):
        """Start the trading bot"""
        self.logger.info(f"Starting {self.config.mode.value.upper()} trading...")
        
        # Load instruments
        self.load_instruments()
        
        # Initialize historical data
        self.initialize_historical_data()
        
        # Initialize previous 15-minute candle (essential for proper sweep detection)
        self.initialize_previous_15min_candle()
        
        if self.config.is_live_mode():
            # Setup live WebSocket
            if not self.setup_live_websocket():
                print("Failed to setup live WebSocket. Exiting.")
                return False
        else:
            # Start demo server
            if not self.start_demo_server():
                print("Failed to start demo server. Exiting.")
                return False
            
            # Start demo data stream
            self.demo_client.set_callback(self._on_price_update)
            self.demo_client.start_data_stream()
            
            # Start demo simulation
            self.demo_client.start_simulation()
        
        self.logger.info("Trading bot started successfully!")
        return True
    
    def stop_trading(self):
        """Stop the trading bot with graceful shutdown"""
        self.logger.info("🛑 Stopping trading bot with graceful shutdown...")
        
        try:
            # Close all open positions
            self._close_all_positions()
            
            # Stop data streams
            if self.config.is_live_mode():
                if self.websocket:
                    self.websocket.close()
            else:
                if self.demo_client:
                    self.demo_client.stop_data_stream()
                    self.demo_client.stop_simulation()
            
            # Print final account summary
            self._print_final_summary()
            
        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {e}")
        finally:
            self.logger.info("Trading bot stopped.")
    
    def _close_all_positions(self):
        """Close all open positions before shutdown"""
        try:
            if self.position_manager and self.position_manager.is_trading:
                self.logger.info("🔒 Closing all open positions...")
                
                # Get current positions
                positions = self.broker.get_positions()
                
                if positions:
                    for symbol, position in positions.items():
                        if position.get('quantity', 0) > 0:
                            self.logger.info(f"   Closing position: {symbol} - Quantity: {position['quantity']}")
                            
                            # Close position using position manager
                            success = self.position_manager.close_position(symbol)
                            
                            if success:
                                self.logger.info(f"   ✅ Position closed successfully: {symbol}")
                            else:
                                self.logger.warning(f"   ⚠️ Failed to close position: {symbol}")
                else:
                    self.logger.info("   No open positions to close")
            else:
                self.logger.info("   No active trading positions")
                
        except Exception as e:
            self.logger.error(f"❌ Error closing positions: {e}")
    
    def _print_final_summary(self):
        """Print final account summary"""
        try:
            self.logger.info("📊 FINAL ACCOUNT SUMMARY")
            self.logger.info("=" * 50)
            
            # Print account balance
            current_balance = self.account_manager.get_current_balance()
            self.logger.info(f"💰 Final Account Balance: ₹{current_balance:,.2f}")
            
            # Print broker summary if available
            if hasattr(self.broker, 'print_account_summary'):
                self.broker.print_account_summary()
            
            # Print position manager summary
            if self.position_manager:
                self.position_manager.display_order_status()
            
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"❌ Error printing final summary: {e}")
    
    def run(self):
        """Main run loop"""
        global shutdown_requested
        
        try:
            # Start trading
            if not self.start_trading():
                return
            
            # Main loop
            self.logger.info("Trading bot is running. Press Ctrl+C to stop.")
            
            while not shutdown_requested:
                time.sleep(1)
                
                # Periodic tasks
                if self.config.is_demo_mode():
                    # Check if demo simulation is complete
                    status = self.demo_client.get_server_status()
                    if "error" in status or "completed" in status.get("status", ""):
                        self.logger.info("Demo simulation completed")
                        break
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Received interrupt signal (Ctrl+C)")
        except Exception as e:
            self.logger.log_error("Error in main loop", e)
        finally:
            self.stop_trading()

    def get_previous_15min_candle_time(self):
        """
        Get the timestamp for the previous 15-minute candle based on current time.
        Handles market hours (9:15 AM - 3:30 PM, Mon-Fri) and previous day logic.
        Returns timezone-aware timestamp.
        """
        import pytz
        ist_tz = pytz.timezone('Asia/Kolkata')
        
        now = datetime.now(ist_tz)
        
        # Check if it's a weekday (Monday = 0, Sunday = 6)
        if now.weekday() >= 5:  # Saturday or Sunday
            # Go back to Friday 3:30 PM
            days_back = now.weekday() - 4  # Friday is 4
            target_date = now - timedelta(days=days_back)
            target_time = target_date.replace(hour=15, minute=30, second=0, microsecond=0)
        else:
            # It's a weekday
            if now.hour < 9 or (now.hour == 9 and now.minute < 15):
                # Before market opens, get previous day's last candle
                if now.weekday() == 0:  # Monday
                    # Go back to Friday 3:30 PM
                    target_date = now - timedelta(days=3)
                else:
                    # Go back to previous day 3:30 PM
                    target_date = now - timedelta(days=1)
                target_time = target_date.replace(hour=15, minute=30, second=0, microsecond=0)
            elif now.hour > 15 or (now.hour == 15 and now.minute > 30):
                # After market closes, get today's last candle
                target_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
            else:
                # During market hours, get the previous 15-minute candle
                # 15-minute intervals: 9:15, 9:30, 9:45, 10:00, 10:15, 10:30, etc.
                current_minute = now.minute
                current_hour = now.hour
                
                # Find the previous 15-minute boundary
                if current_minute < 15:
                    if current_hour == 9:
                        # Before 9:15, get previous day's last candle
                        if now.weekday() == 0:  # Monday
                            target_date = now - timedelta(days=3)
                        else:
                            target_date = now - timedelta(days=1)
                        target_time = target_date.replace(hour=15, minute=30, second=0, microsecond=0)
                    else:
                        target_time = now.replace(hour=current_hour-1, minute=45, second=0, microsecond=0)
                elif current_minute < 30:
                    target_time = now.replace(minute=15, second=0, microsecond=0)
                elif current_minute < 45:
                    target_time = now.replace(minute=30, second=0, microsecond=0)
                else:
                    target_time = now.replace(minute=45, second=0, microsecond=0)
        
        return target_time
    
    def initialize_previous_15min_candle(self):
        """
        Initialize the previous 15-minute candle before starting to track.
        This is essential for proper sweep detection.
        """
        try:
            self.logger.info("🔄 Initializing previous 15-minute candle...")
            
            # Get the timestamp for the previous 15-minute candle
            previous_candle_time = self.get_previous_15min_candle_time()
            self.logger.info(f"   Previous 15-min candle time: {previous_candle_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            # Calculate the start time for fetching historical data
            # We need at least 1 15-minute candles for proper tracking
            start_time = previous_candle_time - timedelta(minutes=15)
            
            if self.config.is_live_mode():
                # For live mode, fetch from Dhan API
                self._fetch_live_previous_15min_candle(start_time, previous_candle_time)
            else:
                # For demo mode, use the demo server's historical data
                self._fetch_demo_previous_15min_candle(start_time, previous_candle_time)
                
        except Exception as e:
            self.logger.warning(f"⚠️ Could not initialize previous 15-minute candle: {e}")
            self.logger.info("   Continuing with current initialization method...")
            import traceback
            self.logger.warning(f"   Traceback: {traceback.format_exc()}")
    
    def _fetch_live_previous_15min_candle(self, start_time, end_time):
        """Fetch previous 15-minute candle for live trading"""
        try:
            # Fetch 15-minute candles from start_time to end_time
            historical_data = self.historical_fetcher.fetch_15min_candles(
                symbol=self.symbol,
                instruments_df=self.instruments_df,
                start_date=start_time,
                end_date=end_time
            )
            
            if historical_data is not None and len(historical_data) > 0:
                # Convert to Candle objects and add to 15-minute candle list
                for _, row in historical_data.iterrows():
                    candle = Candle(
                        timestamp=row['timestamp'],
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=int(row['volume']) if 'volume' in row else 0
                    )
                    self.fifteen_min_candles.append(candle)
                
                self.logger.info(f"✅ Loaded {len(self.fifteen_min_candles)} historical 15-minute candles")
                
                # Set last candle time
                if self.fifteen_min_candles:
                    self.last_15min_candle_time = self.fifteen_min_candles[-1].timestamp
                    self.logger.info(f"   Last 15-min candle: {self.last_15min_candle_time.strftime('%H:%M:%S')}")
            else:
                self.logger.warning("⚠️ No historical data received for previous 15-minute candle")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error fetching live previous 15-minute candle: {e}")
    
    def _fetch_demo_previous_15min_candle(self, start_time, end_time):
        """Fetch previous 15-minute candle for demo trading"""
        try:
            # For demo mode, we need to aggregate 1-minute candles into 15-minute candles
            # This should be done from the demo server's historical data
            
            if self.demo_server and hasattr(self.demo_server, 'historical_data'):
                # Get 1-minute candles from the demo server's historical data
                demo_data = self.demo_server.historical_data
                
                if demo_data is not None and len(demo_data) > 0:
                    # Convert start_time and end_time to timezone-aware timestamps
                    # to match the demo data's timezone
                    import pytz
                    ist_tz = pytz.timezone('Asia/Kolkata')
                    
                    # Make timestamps timezone-aware
                    start_time_aware = ist_tz.localize(start_time) if start_time.tzinfo is None else start_time
                    end_time_aware = ist_tz.localize(end_time) if end_time.tzinfo is None else end_time
                    
                    # Filter data for the required time range
                    filtered_data = demo_data[
                        (demo_data['timestamp'] >= start_time_aware) & 
                        (demo_data['timestamp'] <= end_time_aware)
                    ]
                    
                    if len(filtered_data) > 0:
                        # Aggregate 1-minute candles into 15-minute candles
                        self._aggregate_1min_to_15min_candles(filtered_data)
                        self.logger.info(f"✅ Aggregated {len(self.fifteen_min_candles)} 15-minute candles from demo data")
                    else:
                        self.logger.warning("⚠️ No demo data available for the required time range")
                        self.logger.info(f"   Requested range: {start_time_aware} to {end_time_aware}")
                        self.logger.info(f"   Available data range: {demo_data['timestamp'].min()} to {demo_data['timestamp'].max()}")
                else:
                    self.logger.warning("⚠️ No demo historical data available")
            else:
                self.logger.warning("⚠️ Demo server not properly initialized")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error fetching demo previous 15-minute candle: {e}")
            import traceback
            self.logger.warning(f"   Traceback: {traceback.format_exc()}")
    
    def _aggregate_1min_to_15min_candles(self, one_min_data):
        """Aggregate 1-minute candles into 15-minute candles"""
        try:
            # Group 1-minute candles by 15-minute intervals
            one_min_data['timestamp'] = pd.to_datetime(one_min_data['timestamp'])
            one_min_data['15min_group'] = one_min_data['timestamp'].dt.floor('15min')
            
            # Aggregate by 15-minute groups
            grouped = one_min_data.groupby('15min_group').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).reset_index()
            
            # Convert to Candle objects
            for _, row in grouped.iterrows():
                candle = Candle(
                    timestamp=row['15min_group'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume'])
                )
                self.fifteen_min_candles.append(candle)
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error aggregating 1-minute to 15-minute candles: {e}")

def signal_handler(signum, frame):
    """Handle interrupt signals with graceful shutdown"""
    print(f"\n🛑 Received signal {signum} (Ctrl+C)")
    print("🔄 Initiating graceful shutdown...")
    
    # Set a global flag to indicate shutdown
    global shutdown_requested
    shutdown_requested = True
    
    # Give some time for graceful shutdown
    time.sleep(2)
    sys.exit(0)

# Global flag for shutdown
shutdown_requested = False

if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run trading bot
    bot = DualModeTradingBot()
    bot.run()
