"""
New Architecture Trading Bot
Uses CandleData + StrategyManager for clean separation of concerns
"""

import os
import time
import signal
import sys
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytz

# Import our new components
from models.candle import Candle
from utils.market_utils import is_market_hours, is_trading_ending, round_to_tick
from strategies.candle_data import CandleData
from strategies.strategy_manager import StrategyManager
from demo.demo_server import DemoServer
from demo.demo_data_client import DemoDataClient
from brokers.dhan_broker import DhanBroker
from brokers.demo_broker import DemoBroker
from utils.market_data import MarketDataWebSocket, process_ticker_data
from position.position_manager import PositionManager
from utils.config import TradingConfig
from utils.historical_data import HistoricalDataFetcher
from utils.logger import TradingLogger
from utils.account_manager import AccountManager
import logging

# Load environment variables
load_dotenv()

class NewArchitectureTradingBot:
    """Trading bot using new architecture with CandleData + StrategyManager"""
    
    def __init__(self):
        # Load configuration
        self.config = TradingConfig()
        self.config.print_config()
        
        # Initialize logger
        self.logger = TradingLogger(
            log_dir=self.config.log_dir,
            log_level=getattr(logging, self.config.log_level, logging.INFO)
        )
        
        # Initialize account manager
        self.account_manager = AccountManager(self.config, self.logger)
        
        # Initialize broker based on mode
        if self.config.is_live_mode():
            self.broker = DhanBroker(
                client_id=self.config.client_id,
                access_token=self.config.access_token
            )
        else:
            self.broker = DemoBroker(account_manager=self.account_manager)
        
        # Initialize position manager
        self.position_manager = PositionManager(self.broker, self.account_manager, self.config.tick_size)
        
        # Initialize historical data fetcher
        if self.config.is_live_mode():
            self.historical_fetcher = HistoricalDataFetcher(
                access_token=self.config.access_token,
                client_id=self.config.client_id
            )
        else:
            # For demo mode, we still need credentials to fetch historical data
            access_token = os.getenv('DHAN_ACCESS_TOKEN', 'demo_token')
            client_id = os.getenv('DHAN_CLIENT_ID', 'demo_client')
            self.historical_fetcher = HistoricalDataFetcher(
                access_token=access_token,
                client_id=client_id
            )
        
        # Initialize strategy manager (this will create CandleData internally)
        self.strategy_manager = StrategyManager(
            symbol=self.config.symbol,
            tick_size=self.config.tick_size,
            logger=self.logger
        )
        
        # Set callbacks for trade management
        self.strategy_manager.set_callbacks(
            entry_callback=self._on_strategy_trade_entry,
            exit_callback=self._on_strategy_trade_exit
        )
        
        # Market data
        self.instruments_df = None
        self.websocket = None
        self.demo_server = None
        self.demo_client = None
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(f"New Architecture Trading Bot initialized in {self.config.mode.value.upper()} mode")
        self.logger.info(f"Symbol: {self.config.symbol}")
        self.logger.info(f"Account Balance: ₹{self.account_manager.get_current_balance():,.2f}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """Start the trading bot"""
        try:
            self.logger.info("Starting new architecture trading bot...")
            
            # Load instruments
            self._load_instruments()
            
            # Initialize historical data
            self._initialize_historical_data()
            
            # Start data streaming based on mode
            if self.config.is_live_mode():
                self._start_live_trading()
            else:
                self._start_demo_trading()
                
        except Exception as e:
            self.logger.error(f"Error starting trading bot: {e}")
            raise
    
    def _load_instruments(self):
        """Load instrument data"""
        try:
            # Fetch the detailed instrument list
            url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
            self.instruments_df = pd.read_csv(url, low_memory=False)
            
            # Save locally for future use
            local_path = os.path.join(os.getcwd(), "dhan_instruments.csv")
            self.instruments_df.to_csv(local_path, index=False)
            
            self.logger.info(f"Loaded {len(self.instruments_df)} instruments")
            
        except Exception as e:
            self.logger.error(f"Error loading instruments: {e}")
            raise
    
    def _initialize_historical_data(self):
        """Initialize historical data for the strategy manager"""
        self.logger.info("Initializing historical data...")
        
        # Determine reference date
        if self.config.is_demo_mode():
            reference_date = self.config.get_demo_start_datetime()
            self.logger.info(f"Demo mode: Using {reference_date.strftime('%Y-%m-%d %H:%M:%S')} as reference date")
        else:
            reference_date = datetime.now()
            self.logger.info(f"Live mode: Using current time {reference_date.strftime('%Y-%m-%d %H:%M:%S')} as reference date")
        
        # Fetch historical data
        hist_days = self.config.get_num_hist_days()
        self.logger.info(f"Fetching {hist_days} days of historical data for {self.config.symbol}...")

        historical_data = self.historical_fetcher.fetch_historical_data_v2(
            symbol=self.config.symbol,
            instruments_df=self.instruments_df,
            reference_date=reference_date,
            hist_days=float(hist_days)
        )

        if historical_data['5min'] is not None and historical_data['1min'] is not None:
            # Convert DataFrames to Candle objects
            candles_5min = []
            for _, row in historical_data['5min'].iterrows():
                candle = Candle(
                    timestamp=row['timestamp'],
                    open_price=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close'])
                )
                candles_5min.append(candle)

            candles_1min = []
            for _, row in historical_data['1min'].iterrows():
                candle = Candle(
                    timestamp=row['timestamp'],
                    open_price=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close'])
                )
                candles_1min.append(candle)

            # Initialize strategy manager with historical data
            candle_data = {
                '5min': candles_5min,
                '1min': candles_1min
            }
            
            if candles_5min and candles_1min:
                success = self.strategy_manager.initialize_with_historical_data(candle_data)
                if success:
                    self.logger.info(f"✅ StrategyManager initialized with {len(candles_5min)} 5-minute candles")
                    self.logger.info(f"✅ StrategyManager initialized with {len(candles_1min)} 1-minute candles")
                else:
                    self.logger.error("❌ Failed to initialize StrategyManager")
            else:
                self.logger.error("❌ No historical data available")
        else:
            self.logger.error(f"❌ Failed to fetch historical data for {self.config.symbol}")

        # For demo mode, also initialize demo server
        if self.config.is_demo_mode():
            self._initialize_demo_server()

    def _initialize_demo_server(self):
        """Initialize demo server for backtesting"""
        try:
            # Fetch historical data for demo server
            from datetime import datetime
            historical_data = self.historical_fetcher.fetch_1min_candles(
                symbol=self.config.symbol,
                instruments_df=self.instruments_df,
                start_date=self.config.get_demo_start_datetime(),
                end_date=datetime.now()
            )
            
            if historical_data is not None:
                # Convert to DataFrame for demo server
                df = historical_data.copy()
                
                # Filter data to only include candles from demo start date onwards
                demo_start_date = self.config.get_demo_start_datetime()
                
                # Convert demo_start_date to timezone-aware (Asia/Kolkata) for comparison
                if demo_start_date.tzinfo is None:
                    import pytz
                    kolkata_tz = pytz.timezone('Asia/Kolkata')
                    demo_start_date = kolkata_tz.localize(demo_start_date)
                
                df = df[df['timestamp'] >= demo_start_date].copy()
                
                if len(df) == 0:
                    self.logger.error(f"No data available from demo start date {demo_start_date}")
                    return
                
                # Find the exact 09:15:00 candle to start from
                demo_start_time = self.config.get_demo_start_datetime()
                if demo_start_time.tzinfo is None:
                    import pytz
                    kolkata_tz = pytz.timezone('Asia/Kolkata')
                    demo_start_time = kolkata_tz.localize(demo_start_time)
                
                # Debug: Show what candles we actually have
                self.logger.info(f"Available candles in data:")
                for i in range(min(5, len(df))):
                    candle_time = df.iloc[i]['timestamp']
                    self.logger.info(f"  Candle {i}: {candle_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Find the first candle that starts at or after 09:15:00
                start_candle_index = None
                for i, row in df.iterrows():
                    if row['timestamp'] >= demo_start_time:
                        start_candle_index = i
                        break
                
                if start_candle_index is None:
                    self.logger.error(f"No candle found at or after demo start time {demo_start_time}")
                    return
                
                # Slice the dataframe to start from the correct candle
                df = df.iloc[start_candle_index:].copy()
                
                self.logger.info(f"Demo start time: {demo_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"First candle to stream: {df.iloc[0]['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # If the first candle is not exactly 09:15:00, we need to create a synthetic 09:15:00 candle
                first_candle_time = df.iloc[0]['timestamp']
                if first_candle_time > demo_start_time:
                    self.logger.warning(f"⚠️  No 09:15:00 candle found! First available candle is {first_candle_time.strftime('%H:%M:%S')}")
                    self.logger.warning(f"⚠️  Creating synthetic 09:15:00 candle using first available candle data")
                    
                    # Create a synthetic 09:15:00 candle using the first available candle's data
                    first_candle = df.iloc[0]
                    synthetic_candle = {
                        'timestamp': demo_start_time,
                        'open': first_candle['open'],
                        'high': first_candle['high'], 
                        'low': first_candle['low'],
                        'close': first_candle['close'],
                        'volume': first_candle.get('volume', 0)
                    }
                    
                    # Insert the synthetic candle at the beginning
                    df = pd.concat([pd.DataFrame([synthetic_candle]), df], ignore_index=True)
                    self.logger.info(f"✅ Created synthetic 09:15:00 candle: O:{synthetic_candle['open']:.2f} H:{synthetic_candle['high']:.2f} L:{synthetic_candle['low']:.2f} C:{synthetic_candle['close']:.2f}")
                
                self.demo_server = DemoServer(
                    historical_data=df,
                    start_date=demo_start_time,
                    port=self.config.demo_server_port,
                    stream_interval_seconds=self.config.demo_stream_interval_seconds
                )
                
                # Set data callback to process candles through strategy manager
                self.demo_server.set_data_callback(self._on_demo_data)
                
                # Initialize demo client
                self.demo_client = DemoDataClient(f"http://localhost:{self.config.demo_server_port}")
                self.logger.info(f"Demo server initialized with {len(df)} 1-minute candles for {self.config.symbol}")
                
                # Show date range
                if len(df) > 0:
                    start_date = df.iloc[0]['timestamp']
                    end_date = df.iloc[-1]['timestamp']
                    self.logger.info(f"Demo streaming date range: {start_date.date()} to {end_date.date()}")
                    # Log the configured demo start time, not the first available candle
                    self.logger.info(f"Demo start time: {demo_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    self.logger.error("Warning: Could not fetch historical data for demo trading")
                    
        except Exception as e:
            self.logger.error(f"Error initializing demo server: {e}")
    
    def _start_live_trading(self):
        """Start live trading mode"""
        self.logger.info("Starting live trading mode...")
        
        # Get security ID for the symbol
        security_id = self.broker.get_security_id(self.config.symbol, self.instruments_df)
        if not security_id:
            raise ValueError(f"Could not find security ID for symbol: {self.config.symbol}")
            
        self.logger.info(f"Security ID for {self.config.symbol}: {security_id}")
        
        # Initialize WebSocket for market data
        self.websocket = MarketDataWebSocket(
            client_id=self.config.client_id,
            access_token=self.config.access_token,
            on_message_callback=self._on_websocket_message,
            on_error_callback=self._on_websocket_error,
            on_close_callback=self._on_websocket_close
        )
        
        # Connect and start streaming
        self.websocket.connect({self.config.symbol: security_id})
        
        # Keep running
        self._run_live_loop()
    
    def _start_demo_trading(self):
        """Start demo trading mode"""
        self.logger.info("Starting demo trading mode...")
        
        # Start demo server
        if self.demo_server:
            self.start_demo_server()
            self.demo_client.set_callback(self._on_demo_data)
            self.demo_client.start_data_stream()
            self.demo_client.start_simulation()
            # Keep running
            self._run_demo_loop()
        else:
            raise ValueError("Demo server not initialized")

    def start_demo_server(self):
        """Start the demo server in a separate thread"""
        import threading
        server_thread = threading.Thread(target=self.demo_server.run)
        server_thread.daemon = True
        server_thread.start()

        # Wait for server to start
        time.sleep(3)

        # Connect client to server
        if self.demo_client.connect():
            self.logger.info("Demo server started and client connected")
            return True
        else:
            self.logger.error("Failed to connect to demo server")
            return False
    
    def _run_live_loop(self):
        """Main loop for live trading"""
        self.logger.info("Live trading loop started")
        
        try:
            while True:
                # Check if market is open
                if not is_market_hours():
                    self.logger.info("Market is closed, waiting...")
                    time.sleep(60)
                    continue
                
                # Check if trading should end
                if is_trading_ending():
                    self.logger.info("Trading session ending, closing positions...")
                    self._close_all_positions()
                    break
                
                # Sleep for a short interval
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Error in live trading loop: {e}")
        finally:
            self.stop()
    
    def _run_demo_loop(self):
        """Main loop for demo trading"""
        self.logger.info("Demo trading loop started")
        
        try:
            loop_count = 0
            while True:
                loop_count += 1
                
                # Check if demo client is still running
                if not self.demo_client.is_running():
                    self.logger.info("Demo client stopped")
                    break
                
                # Log status every 30 seconds
                if loop_count % 30 == 0:
                    self.logger.info(f"Demo trading loop running... (loop {loop_count})")
                
                # Sleep for a short interval
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Error in demo trading loop: {e}")
        finally:
            self.stop()
    
    def _on_websocket_message(self, ws, message):
        """Handle WebSocket market data messages"""
        try:
            # Process ticker data
            ticker_data = process_ticker_data(message)
            if ticker_data:
                price = ticker_data['last_price']
                timestamp = ticker_data['timestamp']
                
                # Update strategy manager with new price
                trade_trigger = self.strategy_manager.candle_data.update_1min_candle(price, timestamp)
                if trade_trigger:
                    self.logger.info(f"🎯 Trade triggered from live data: {trade_trigger['strategy_name']}")
                    
        except Exception as e:
            self.logger.error(f"Error processing WebSocket message: {e}")
    
    def _on_demo_data(self, candle_data, timestamp):
        """Handle demo data updates"""
        try:
            # Log demo data reception
            self.logger.info(f"📡 DEMO DATA RECEIVED")
            self.logger.info(f"   Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"   OHLC: O:{candle_data['open']:.2f} H:{candle_data['high']:.2f} L:{candle_data['low']:.2f} C:{candle_data['close']:.2f}")
            
            # Process candle through strategy manager
            trade_trigger = self.strategy_manager.candle_data.update_1min_candle_with_data(candle_data, timestamp)
            if trade_trigger:
                self.logger.info(f"🎯 Trade triggered from demo data: {trade_trigger['strategy_name']}")
            
        except Exception as e:
            self.logger.error(f"❌ Error processing demo data: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _on_websocket_error(self, ws, error):
        """Handle WebSocket errors"""
        self.logger.error(f"WebSocket error: {error}")
    
    def _on_websocket_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        self.logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
    
    def _on_strategy_trade_entry(self, trigger):
        """Handle trade entry from strategy"""
        try:
            entry_price = trigger.get('entry', 0)
            stop_loss = trigger.get('stop_loss', 0)
            target = trigger.get('target', 0)
            strategy_name = trigger.get('strategy_name', 'Unknown')
            
            self.logger.info(f"💰 TRADE ENTRY TRIGGERED!")
            self.logger.info(f"   📊 Strategy: {strategy_name}")
            self.logger.info(f"   📈 Entry: {entry_price:.2f}")
            self.logger.info(f"   🛑 Stop Loss: {stop_loss:.2f}")
            self.logger.info(f"   🎯 Target: {target:.2f}")
            self.logger.info(f"   💰 Risk: {entry_price - stop_loss:.2f}")
            self.logger.info(f"   💎 Reward: {target - entry_price:.2f}")
            
            # Enter trade using position manager
            success = self.position_manager.enter_trade(
                symbol=self.config.symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                trigger_type=strategy_name,
                instruments_df=self.instruments_df
            )
            
            if success:
                self.logger.info(f"✅ Trade entered successfully for {self.config.symbol}!")
            else:
                self.logger.error(f"❌ Failed to enter trade for {self.config.symbol}")
                # Reset strategy manager
                self.strategy_manager.exit_trade(entry_price, "order_failed")
                    
        except Exception as e:
            self.logger.error(f"Error handling trade entry: {e}")
    
    def _on_strategy_trade_exit(self, exit_price, reason):
        """Handle trade exit from strategy"""
        try:
            self.logger.info(f"🚪 TRADE EXIT TRIGGERED!")
            self.logger.info(f"   💰 Exit Price: {exit_price:.2f}")
            self.logger.info(f"   📝 Reason: {reason}")
            
            # Close position using position manager
            success = self.position_manager.close_position(self.config.symbol)
            
            if success:
                self.logger.info(f"✅ Position closed successfully for {self.config.symbol}")
            else:
                self.logger.error(f"❌ Failed to close position for {self.config.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error handling trade exit: {e}")
    
    def _close_all_positions(self):
        """Close all open positions"""
        try:
            positions = self.broker.get_positions()
            for symbol, position in positions.items():
                if position['quantity'] != 0:
                    self.logger.info(f"Closing position for {symbol}")
                    self.position_manager.close_position(symbol)
        except Exception as e:
            self.logger.error(f"Error closing positions: {e}")
    
    def stop(self):
        """Stop the trading bot gracefully"""
        self.logger.info("Stopping trading bot...")
        
        # Close WebSocket
        if self.websocket:
            self.websocket.close()
        
        # Stop demo client
        if self.demo_client:
            self.demo_client.stop_data_stream()
            self.demo_client.stop_simulation()
        
        # Stop demo server
        if self.demo_server:
            self.demo_server.stop_simulation()
        
        # Close all positions
        self._close_all_positions()
        
        self.logger.info("Trading bot stopped")

def main():
    """Main entry point"""
    bot = None
    try:
        # Create and start trading bot
        bot = NewArchitectureTradingBot()
        bot.start()
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, shutting down...")
        if bot:
            bot.stop()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        if bot:
            bot.stop()
    finally:
        print("Trading bot stopped")

if __name__ == "__main__":
    main()
