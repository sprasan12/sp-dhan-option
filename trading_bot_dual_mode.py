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
import pytz

# Import our modular components
from models.candle import Candle
from utils.market_utils import is_market_hours, is_trading_ending, round_to_tick
from strategies.candle_strategy import CandleStrategy
from strategies.symbol_manager import SymbolManager
from strategies.erl_to_irl_strategy import ERLToIRLStrategy
from demo.demo_server import DemoServer
from demo.demo_data_client import DemoDataClient
from demo.multi_symbol_demo_server import MultiSymbolDemoServer
from demo.multi_symbol_demo_client import MultiSymbolDemoClient
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
                'Demo 15-min Candles Back': self.config.demo_15min_candles_back,
                'Historical Data Days': self.config.historical_data_days
            })
        
        self.logger.log_config(config_dict)
        
        # Initialize components based on mode
        if self.config.is_live_mode():
            self._init_live_mode()
        else:
            self._init_demo_mode()
        
        # Get symbols to trade
        self.symbols = self.config.get_symbols()
        if not self.symbols:
            raise ValueError("No symbols configured for trading")

        if self.config.is_dual_symbol_mode():
            # Dual symbol mode - use SymbolManager
            self.strategy_manager = SymbolManager(
                symbols=self.symbols,
                tick_size=self.config.tick_size,
                swing_look_back=self.config.swing_look_back,
                logger=self.logger,
                exit_callback=self._on_strategy_trade_exit,
                entry_callback=self._on_strategy_trade_entry
            )
            # Also create ERL to IRL strategy for dual symbol mode
            self.erl_to_irl_strategy = ERLToIRLStrategy(
                tick_size=self.config.tick_size,
                logger=self.logger
            )
            # Set callbacks for the ERL to IRL strategy
            self.erl_to_irl_strategy.set_callbacks(
                entry_callback=self._on_erl_to_irl_trade_entry,
                exit_callback=self._on_erl_to_irl_trade_exit
            )
            self.strategy = None  # Not used in dual mode
        else:
            # Single symbol mode - use original CandleStrategy
            self.strategy = CandleStrategy(
                tick_size=self.config.tick_size, 
                swing_look_back=self.config.swing_look_back,
                logger=self.logger,
                exit_callback=self._on_strategy_trade_exit,
                entry_callback=self._on_strategy_trade_entry
            )
            self.strategy_manager = None  # Not used in single mode
            self.erl_to_irl_strategy = None  # Not used in single mode
        
        self.position_manager = PositionManager(self.broker, self.account_manager, self.config.tick_size)
        
        # Market data
        self.instruments_df = None
        self.symbol = self.symbols[0]  # Primary symbol for backward compatibility
        
        # Data sources
        self.websocket = None
        self.demo_server = None
        self.demo_client = None
        self.multi_symbol_demo_server = None
        self.multi_symbol_demo_client = None

        # Candle tracking
        self.fifteen_min_candles = deque(maxlen=1000)
        self.five_min_candles = deque(maxlen=3000)# Keep last 10 days
        self.one_min_candles = deque(maxlen=10000)
        self.current_15min_candle = None
        self.current_5min_candle = None
        self.current_1min_candle = None
        self.last_15min_candle_time = None
        self.last_1min_candle_time = None
        
        # Strategy state
        self.sweep_detected = False
        self.sweep_low = None
        self.waiting_for_sweep = False
        self.last_bear_candles = deque(maxlen=10)
        
        self.logger.info(f"Trading Bot initialized in {self.config.mode.value.upper()} mode")
        self.logger.info(f"Strategy Mode: {self.config.strategy_mode.value.upper()}")
        
        if self.config.is_erl_to_irl_strategy():
            self.logger.info("ERL to IRL Strategy: Trading External Range Liquidity to Internal Range Liquidity")
            self.logger.info(f"Trading Symbol: {self.symbol}")
        elif self.config.is_dual_symbol_mode():
            self.logger.info(f"Trading Symbols: {self.symbols[0]} (Primary), {self.symbols[1]} (Secondary)")
            self.logger.info("Dual Symbol Mode: Will monitor both symbols but trade only one at a time")
        else:
            self.logger.info(f"Trading Symbol: {self.symbol}")
        self.logger.info(f"Account Balance: ₹{self.account_manager.get_current_balance():,.2f}")
    
    def _init_live_mode(self):
        """Initialize components for live trading mode"""
        self.logger.info("Initializing LIVE trading mode...")
        
        # Validate live trading credentials
        if not self.config.client_id or not self.config.access_token:
            raise ValueError("Live trading mode requires DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN in environment variables")
        
        # Initialize real broker
        self.broker = DhanBroker(
            self.config.client_id, 
            self.config.access_token, 
            self.config.tick_size
        )
        
        # Test API connectivity
        try:
            balance = self.broker.get_account_balance()
            self.logger.info(f"✅ API connectivity test successful. Account balance: ₹{balance:,.2f}")
        except Exception as e:
            self.logger.error(f"❌ API connectivity test failed: {e}")
            raise ValueError("Cannot connect to Dhan API. Please check your credentials and internet connection.")
        
        # Initialize historical data fetcher for getting initial candles
        self.historical_fetcher = HistoricalDataFetcher(
            self.config.access_token,
            self.config.client_id
        )
        
        self.logger.info("Live mode components initialized successfully")
        self.logger.warning("⚠️ LIVE TRADING MODE - Real money will be used!")
    
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
    
    def _initialize_erl_to_irl_historical_data(self):
        """Initialize historical data for ERL to IRL strategy"""
        self.logger.info("Initializing ERL to IRL strategy with 10 days of historical data...")
        
        # Determine the reference date for fetching historical data
        if self.config.is_demo_mode():
            # For demo mode, use DEMO_START_DATE as the reference (current time for strategy)
            reference_date = self.config.get_demo_start_datetime()
            self.logger.info(f"Demo mode: Using {reference_date.strftime('%Y-%m-%d %H:%M:%S')} as reference date for strategy")
        else:
            # For live mode, use current time as reference
            reference_date = datetime.now()
            self.logger.info(f"Live mode: Using current time {reference_date.strftime('%Y-%m-%d %H:%M:%S')} as reference date")
        hist_days = self.config.get_num_hist_days()
        # For ERL to IRL strategy, we need 10 days of 5min and 15min data
        for symbol in self.symbols:
            self.logger.info(f"Fetching 10 days of historical data for {symbol}...")
            
            # Fetch 10 days of data for both 5min and 15min
            historical_data = self.historical_fetcher.fetch_10_days_historical_data(
                symbol=symbol,
                instruments_df=self.instruments_df,
                reference_date=reference_date,
                hist_days=float(hist_days)
            )
            
            if historical_data['5min'] is not None and historical_data['15min'] is not None:
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
                
                candles_15min = []
                for _, row in historical_data['15min'].iterrows():
                    candle = Candle(
                        timestamp=row['timestamp'],
                        open_price=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close'])
                    )
                    candles_15min.append(candle)
                
                # Initialize the ERL to IRL strategy with historical data
                candle_data = {
                    '5min': candles_5min,
                    '15min': candles_15min
                }
                
                success = self.erl_to_irl_strategy.initialize_with_historical_data(symbol, candle_data)
                
                if success:
                    self.logger.info(f"✅ ERL to IRL strategy initialized for {symbol}")
                    self.logger.info(f"   Loaded {len(candles_5min)} 5-minute candles")
                    self.logger.info(f"   Loaded {len(candles_15min)} 15-minute candles")
                else:
                    self.logger.error(f"❌ Failed to initialize ERL to IRL strategy for {symbol}")
            else:
                self.logger.error(f"❌ Failed to fetch historical data for {symbol}")
        
        # For demo mode, also initialize demo server components
        if self.config.is_demo_mode():
            self._initialize_demo_server_for_erl_to_irl()
        
        self.logger.info("ERL to IRL strategy initialization completed")
    
    def _initialize_demo_server_for_erl_to_irl(self):
        """Initialize demo server components for ERL to IRL strategy in demo mode"""
        try:
            # For demo mode, stream 1-minute candles from DEMO_START_DATE to current time
            start_date = self.config.get_demo_start_datetime()
            end_date = datetime.now()  # Stream until current time
            
            self.logger.info(f"Demo server: Streaming 1min candles from {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Fetch historical data for all symbols
            symbols_data = {}
            for symbol in self.symbols:
                self.logger.info(f"Fetching 1min data for {symbol}...")
                historical_data = self.historical_fetcher.fetch_1min_candles(
                    symbol=symbol,
                    instruments_df=self.instruments_df,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if historical_data is not None and len(historical_data) > 0:
                    symbols_data[symbol] = historical_data
                    self.logger.info(f"✅ Loaded {len(historical_data)} 1min candles for {symbol}")
                else:
                    self.logger.warning(f"❌ Could not fetch historical data for {symbol}")
            
            if symbols_data:
                # Create multi-symbol demo server
                self.multi_symbol_demo_server = MultiSymbolDemoServer(
                    symbols_data=symbols_data,
                    start_date=start_date,
                    interval_minutes=self.config.demo_interval_minutes,
                    port=self.config.demo_server_port,
                    stream_interval_seconds=self.config.demo_stream_interval_seconds
                )
                
                # Create multi-symbol demo client
                self.multi_symbol_demo_client = MultiSymbolDemoClient(f"http://localhost:{self.config.demo_server_port}")
                
                self.logger.info(f"Multi-symbol demo server initialized for {len(symbols_data)} symbols")
                self.logger.info(f"Symbols: {', '.join(symbols_data.keys())}")
                self.logger.info(f"Streaming date range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                self.logger.error("Could not fetch historical data for any symbol")
                
        except Exception as e:
            self.logger.error(f"Error initializing demo server for ERL to IRL strategy: {e}")
    
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
        #if self.config.is_erl_to_irl_strategy():
        self._initialize_erl_to_irl_historical_data()
        #elif self.config.is_live_mode():
            #self._initialize_live_historical_data()
        #else:
            #self._initialize_demo_historical_data()
    
    def _initialize_live_historical_data(self):
        """Initialize historical data for live trading"""
        print("Fetching last 30 days of 15-minute candles for live trading...")
        
        for symbol in self.symbols:
            print(f"Fetching historical data for {symbol}...")
            
            # Fetch last 30 days of 15-minute candles
            historical_data = self.historical_fetcher.fetch_15min_candles(
                symbol=symbol,
                instruments_df=self.instruments_df,
                days_back=30
            )
            
            if historical_data is not None and len(historical_data) > 0:
                # Convert to Candle objects and add to 15-minute candle list
                candles = []
                for _, row in historical_data.iterrows():
                    candle = Candle(
                        timestamp=row['timestamp'],
                        open_price=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close'])
                    )
                    candles.append(candle)
                
                print(f"Loaded {len(candles)} historical 15-minute candles for {symbol}")
                
                # Set initial candle for the symbol's strategy
                if self.config.is_dual_symbol_mode() and self.strategy_manager:
                    if candles:
                        self.strategy_manager.set_initial_15min_candle(symbol, candles[-1])
                else:
                    # Single symbol mode - use legacy approach
                    self.fifteen_min_candles.extend(candles)
                    if self.fifteen_min_candles:
                        self.last_15min_candle_time = self.fifteen_min_candles[-1].timestamp
            else:
                print(f"Warning: Could not fetch historical data for {symbol}")
    
    def _initialize_demo_historical_data(self):
        """Initialize historical data for demo trading"""
        print("Fetching historical data for demo trading...")
        
        # Calculate date range
        start_date = self.config.get_demo_start_datetime()
        end_date = start_date + timedelta(days=self.config.historical_data_days)
        
        # For demo mode, we'll use the primary symbol for the demo server
        # but track both symbols in the strategy manager
        primary_symbol = self.symbols[0]
        
        # Fetch 1-minute candles for demo (using primary symbol)
        historical_data = self.historical_fetcher.fetch_1min_candles(
            symbol=primary_symbol,
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
            
            print(f"Demo server initialized with {len(historical_data)} 1-minute candles for {primary_symbol}")
            print(f"Date range: {start_date.date()} to {end_date.date()}")
            
            # For dual symbol mode, we'll simulate the second symbol's data
            if self.config.is_dual_symbol_mode() and len(self.symbols) > 1:
                print(f"Note: Demo mode will simulate data for both {self.symbols[0]} and {self.symbols[1]}")
                print("In live mode, both symbols will receive real market data")
        else:
            print("Warning: Could not fetch historical data for demo trading")
    
    def start_demo_server(self):
        """Start the demo server in a separate thread"""
        # Check if we have multi-symbol demo server (for ERL to IRL strategy)
        if self.multi_symbol_demo_server:
            import threading
            server_thread = threading.Thread(target=self.multi_symbol_demo_server.run)
            server_thread.daemon = True
            server_thread.start()
            
            # Wait for server to start
            time.sleep(3)
            
            # Connect client to server
            if self.multi_symbol_demo_client.connect():
                print("Multi-symbol demo server started and client connected")
                return True
            else:
                print("Failed to connect to multi-symbol demo server")
                return False
        # Fallback to single-symbol demo server (for regular strategy)
        elif self.demo_server:
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
            # Get security IDs for all symbols
            self.security_ids = {}
            for symbol in self.symbols:
                security_id = self.broker.get_security_id(symbol, self.instruments_df)
                if not security_id:
                    print(f"Could not find security ID for symbol {symbol}")
                    return False
                self.security_ids[symbol] = security_id
                print(f"Found security ID {security_id} for symbol {symbol}")
            
            # Create WebSocket
            self.websocket = MarketDataWebSocket(
                access_token=self.config.access_token,
                client_id=self.config.client_id,
                on_message_callback=self._on_websocket_message,
                on_error_callback=self._on_websocket_error,
                on_close_callback=self._on_websocket_close
            )
            
            # Connect to WebSocket with all security IDs
            if self.websocket.connect(list(self.security_ids.values())):
                print(f"Live WebSocket connected successfully for {len(self.symbols)} symbols")
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
        # Determine which symbol this data belongs to
        symbol = self._get_symbol_from_security_id(security_id)
        if not symbol:
            return  # Skip if we can't identify the symbol
        
        # Handle both live mode (price) and demo mode (candle_data)
        if isinstance(price_or_candle_data, dict):
            # Demo mode - we have complete candle data
            candle_data = price_or_candle_data
            price = round_to_tick(float(candle_data["close"]), self.config.tick_size)
            # Update 1-minute candle with complete OHLC data
            self._update_1min_candle_with_data(symbol, candle_data, timestamp)
            # Log candle data
            self.logger.log_candle_data(
                "1min", timestamp,
                float(candle_data["open"]),
                float(candle_data["high"]),
                float(candle_data["low"]),
                float(candle_data["close"]),
                symbol=symbol
            )
        else:
            # Live mode - we have just the price
            price = round_to_tick(float(price_or_candle_data), self.config.tick_size)
            # Update 1-minute candle with just the price
            self._update_1min_candle(symbol, price, timestamp)
            # Log price update
            self.logger.log_price_update(price, timestamp, "live")
        
        # Run strategy
        self._run_strategy_logic(symbol, price, timestamp)
    
    def _on_multi_symbol_price_update(self, candles_data, timestamp, security_id):
        """Handle multi-symbol price updates from demo data"""
        # Process each symbol's candle data
        for symbol, candle_data in candles_data.items():
            if candle_data:
                # Create Candle object from candle data
                candle_1m = Candle(
                    timestamp=timestamp,
                    open_price=float(candle_data["open"]),
                    high=float(candle_data["high"]),
                    low=float(candle_data["low"]),
                    close=float(candle_data["close"])
                )
                

                # Log the 1m candle
                self.logger.log_candle_data(
                    "1min", timestamp,
                    candle_1m.open, candle_1m.high, candle_1m.low, candle_1m.close,
                    symbol=symbol
                )

                # Update strategy with 1m candle for sweep detection
                if self.erl_to_irl_strategy:
                    self.erl_to_irl_strategy.update_1m_candle(candle_1m)
                
                # Run strategy logic with the candle data
                self._run_strategy_logic(symbol, candle_data, timestamp)
    
    def _get_symbol_from_security_id(self, security_id):
        """Get symbol from security ID"""
        if hasattr(self, 'security_ids'):
            for symbol, sid in self.security_ids.items():
                if sid == security_id:
                    return symbol
        # Fallback for single symbol mode
        return self.symbol if hasattr(self, 'symbol') else None
    
    def _update_1min_candle(self, symbol, price, timestamp):
        """Update 1-minute candle with just price (for live mode)"""
        if self.config.is_dual_symbol_mode() and self.strategy_manager:
            self.strategy_manager.update_1min_candle(symbol, price, timestamp)
        elif self.strategy:
            self.strategy.update_1min_candle(price, timestamp)
    
    def _update_1min_candle_with_data(self, symbol, candle_data, timestamp):
        """Update 1-minute candle with complete OHLC data (for demo mode)"""
        if self.config.is_dual_symbol_mode() and self.strategy_manager:
            self.strategy_manager.update_1min_candle_with_data(symbol, candle_data, timestamp)
        elif self.strategy:
            self.strategy.update_1min_candle_with_data(candle_data, timestamp)
    
    def _on_strategy_trade_exit(self, exit_price, reason, symbol=None):
        """Callback method called when strategy exits a trade"""
        # Round exit price to tick size
        exit_price = round_to_tick(exit_price, self.config.tick_size)
        self.logger.info(f"Strategy trade exit callback for {symbol or 'symbol'}: {reason} at {exit_price:.2f}")
        # Reset position manager state
        self.position_manager.handle_trade_exit(exit_price, reason)
        
        # Get current account balance for logging
        try:
            account_balance = self.broker.get_account_balance()
            # Note: exit_trade is already called by the strategy itself, we just need to log the account balance
            self.logger.info(f"Account balance after trade exit: ₹{account_balance:.2f}")
        except Exception as e:
            self.logger.error(f"Failed to get account balance: {e}")
    
    def _on_strategy_trade_entry(self, sweep_trigger, symbol=None):
        """Callback method called when strategy detects a trade entry trigger"""
        # Get the symbol from trigger if not provided
        if symbol is None:
            symbol = sweep_trigger.get('symbol', self.symbol)
        
        self.logger.info(f"Strategy trade entry trigger detected for {symbol}: {sweep_trigger}")
        
        # Calculate target based on 2:1 RR - ROUND ALL PRICES TO TICK SIZE
        entry_price = round_to_tick(sweep_trigger['entry'], self.config.tick_size)
        stop_loss = round_to_tick(sweep_trigger['stop_loss'], self.config.tick_size)
        risk = entry_price - stop_loss
        target = round_to_tick(entry_price + (2 * risk), self.config.tick_size)  # 2:1 Risk:Reward
        
        # Log trade entry
        self.logger.log_trade_entry(
            entry_price, stop_loss, target,
            sweep_trigger.get('type', 'UNKNOWN'),
            symbol
        )
        
        # Enter the trade using strategy's trade management
        if self.config.is_dual_symbol_mode() and self.strategy_manager:
            # Dual symbol mode - use the specific symbol's strategy
            if symbol in self.strategy_manager.strategies:
                self.strategy_manager.strategies[symbol].enter_trade(entry_price, stop_loss, target)
        elif self.strategy:
            # Single symbol mode
            self.strategy.enter_trade(entry_price, stop_loss, target)
        
        # Also update position manager for order placement
        instruments_df = self.instruments_df
        
        success = self.position_manager.enter_trade_with_trigger(
            sweep_trigger, 
            sweep_trigger.get('type', 'UNKNOWN'),
            symbol,
            instruments_df
        )
        
        if success:
            self.logger.info(f"✅ Trade entered successfully for {symbol}!")
        else:
            self.logger.error(f"❌ Failed to enter trade for {symbol}")
            # Reset strategy if order placement failed
            if self.config.is_dual_symbol_mode() and self.strategy_manager and symbol in self.strategy_manager.strategies:
                self.strategy_manager.strategies[symbol].exit_trade(entry_price, "order_failed")
            elif self.strategy:
                self.strategy.exit_trade(entry_price, "order_failed")
    
    def _on_erl_to_irl_trade_entry(self, trigger):
        """Callback method called when ERL to IRL strategy detects a trade entry trigger"""
        self.logger.info(f"ERL to IRL trade entry trigger detected: {trigger}")
        
        # Calculate target based on 2:1 RR - ROUND ALL PRICES TO TICK SIZE
        entry_price = round_to_tick(trigger['entry'], self.config.tick_size)
        stop_loss = round_to_tick(trigger['stop_loss'], self.config.tick_size)
        risk = entry_price - stop_loss
        target = round_to_tick(trigger['target'], self.config.tick_size)
        
        # Log trade entry
        self.logger.log_trade_entry(
            entry_price, stop_loss, target,
            trigger.get('type', 'ERL_TO_IRL'),
            self.symbol
        )
        
        # Enter the trade using position manager
        success = self.position_manager.enter_trade_with_trigger(
            trigger, 
            trigger.get('type', 'ERL_TO_IRL'),
            self.symbol,
            self.instruments_df
        )
        
        if success:
            self.logger.info(f"✅ ERL to IRL trade entered successfully!")
        else:
            self.logger.error(f"❌ Failed to enter ERL to IRL trade")
    
    def _on_erl_to_irl_trade_exit(self, exit_signal):
        """Callback method called when ERL to IRL strategy exits a trade"""
        exit_price = round_to_tick(exit_signal['price'], self.config.tick_size)
        self.logger.info(f"ERL to IRL trade exit: {exit_signal['reason']} at {exit_price:.2f}")
        
        # Reset position manager state
        self.position_manager.handle_trade_exit(exit_price, exit_signal['reason'])
    
    def _run_strategy_logic(self, symbol, price, timestamp):
        """Run the main strategy logic"""
        if self.config.is_erl_to_irl_strategy() and self.erl_to_irl_strategy:
            # ERL to IRL strategy mode
            self._run_erl_to_irl_strategy_logic(symbol, price, timestamp)
        elif self.config.is_dual_symbol_mode() and self.strategy_manager:
            # Dual symbol mode
            self._run_dual_symbol_strategy_logic(symbol, price, timestamp)
        elif self.strategy:
            # Single symbol mode - original logic
            self._run_single_symbol_strategy_logic(price, timestamp)
    
    def _run_single_symbol_strategy_logic(self, price, timestamp):
        """Run strategy logic for single symbol mode"""
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
            
            # Check if we should move target based on profit levels
            target_action = self.strategy.should_move_target(price)
            if target_action == "move_to_rr4":
                self.strategy.move_target_to_rr4()
            elif target_action == "remove_target":
                self.strategy.remove_target_and_trail()
            
            return  # Don't look for new entries while in a position
        
        # Not in trade - look for new entry opportunities
        # Note: Sweep conditions are checked by the strategy when 1-minute candles complete
        # No need to check here on every price update
        
        # The strategy will automatically call the callback when a trade trigger is detected
        pass
    
    def _run_dual_symbol_strategy_logic(self, symbol, price, timestamp):
        """Run strategy logic for dual symbol mode"""
        # Check if we're already in a trade
        if self.strategy_manager.is_any_symbol_in_trade():
            # Get the active symbol's strategy
            active_symbol = self.strategy_manager.get_active_symbol()
            if active_symbol and active_symbol in self.strategy_manager.strategies:
                active_strategy = self.strategy_manager.strategies[active_symbol]
                
                # Check for trade exit (stop loss or target)
                exit_signal = active_strategy.check_trade_exit(price)
                if exit_signal:
                    # Exit the trade in strategy (callback will handle position manager reset)
                    active_strategy.exit_trade(exit_signal['price'], exit_signal['reason'])
                    return
                
                # Check if we should move stop loss (50% profit rule)
                if active_strategy.should_move_stop_loss(price):
                    # Once 50% profit is reached, continuously move SL to new swing lows
                    if active_strategy.should_move_stop_loss_continuously():
                        active_strategy.move_stop_loss_to_swing_low()
                
                # Check if we should move target based on profit levels
                target_action = active_strategy.should_move_target(price)
                if target_action == "move_to_rr4":
                    active_strategy.move_target_to_rr4()
                elif target_action == "remove_target":
                    active_strategy.remove_target_and_trail()
            
            return  # Don't look for new entries while in a position
        
        # Not in trade - check for triggers from all symbols
        # Get all pending triggers
        triggers = self.strategy_manager.get_all_pending_triggers()
        
        if triggers:
            # Select the best trigger
            best_trigger = self.strategy_manager.select_best_trigger(triggers)
            if best_trigger:
                # The trigger already contains the symbol information
                # The entry callback will be called automatically by the strategy
                pass
    
    def _run_erl_to_irl_strategy_logic(self, symbol, price_or_candle_data, timestamp):
        """Run strategy logic for ERL to IRL strategy mode"""
        # Handle both price (live mode) and candle data (demo mode)
        if isinstance(price_or_candle_data, dict):
            # Demo mode - we have complete candle data
            candle_data = price_or_candle_data
            price = round_to_tick(float(candle_data["close"]), self.config.tick_size)
            
            # Create Candle object
            current_candle = Candle(
                timestamp=timestamp,
                open_price=float(candle_data["open"]),
                high=float(candle_data["high"]),
                low=float(candle_data["low"]),
                close=float(candle_data["close"])
            )
        else:
            # Live mode - we have just the price
            price = round_to_tick(float(price_or_candle_data), self.config.tick_size)
            
            # Create a simple candle from the price (live mode limitation)
            current_candle = Candle(
                timestamp=timestamp,
                open_price=price,
                high=price,
                low=price,
                close=price
            )
        
        # Update the ERL to IRL strategy with current price
        self.erl_to_irl_strategy.update_price(price, timestamp)
        
        # Update liquidity zones with new candles
        #self._update_liquidity_zones_with_new_candles(symbol, current_candle, None)
    
    def _update_liquidity_zones_with_new_candles(self, symbol, candle_1m, current_candles):
        """Update liquidity zones (FVGs, IFVGs, highs/lows) with new candles"""
        try:
            # Get latest candles for FVG/IFVG detection
            latest_candles = self.candle_aggregator.get_latest_candles(symbol, count=10)
            
            # Update FVGs and IFVGs with new 5m candles
            if latest_candles['5m'] and len(latest_candles['5m']) >= 3:
                self.erl_to_irl_strategy.liquidity_tracker._process_candles_for_fvgs(
                    latest_candles['5m'], "5min", symbol
                )
                self.erl_to_irl_strategy.liquidity_tracker._process_candles_for_implied_fvgs(
                    latest_candles['5m'], "5min", symbol
                )
                self.erl_to_irl_strategy.liquidity_tracker._process_candles_for_previous_highs_lows(
                    latest_candles['5m'], "5min", symbol
                )
            
            # Update FVGs and IFVGs with new 15m candles
            if latest_candles['15m'] and len(latest_candles['15m']) >= 3:
                self.erl_to_irl_strategy.liquidity_tracker._process_candles_for_fvgs(
                    latest_candles['15m'], "15min", symbol
                )
                self.erl_to_irl_strategy.liquidity_tracker._process_candles_for_implied_fvgs(
                    latest_candles['15m'], "15min", symbol
                )
                self.erl_to_irl_strategy.liquidity_tracker._process_candles_for_previous_highs_lows(
                    latest_candles['15m'], "15min", symbol
                )
            
            # Check for mitigation with 1m candle
            self.erl_to_irl_strategy.liquidity_tracker.check_and_mark_mitigation(candle_1m)
            
        except Exception as e:
            self.logger.error(f"Error updating liquidity zones for {symbol}: {e}")
    
    def _on_erl_to_irl_trade_entry(self, trade_data):
        """Handle ERL to IRL trade entry"""
        try:
            if self.logger:
                self.logger.info(f"🎯 ERL to IRL Trade Entry: {trade_data}")
            
            # Execute the trade through position manager
            success = self.position_manager.enter_trade_with_trigger(
                trigger=trade_data,
                trigger_type=trade_data['type'],
                symbol=trade_data.get('symbol', 'NIFTY 09 SEP 24800 CALL'),  # Default symbol
                instruments_df=self.instruments_df
            )
            
            if success:
                if self.logger:
                    self.logger.info(f"✅ ERL to IRL trade entered successfully")
            else:
                if self.logger:
                    self.logger.error(f"❌ Failed to enter ERL to IRL trade")
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in ERL to IRL trade entry: {e}")
    
    def _on_erl_to_irl_trade_exit(self, trade_data):
        """Handle ERL to IRL trade exit"""
        try:
            if self.logger:
                self.logger.info(f"🎯 ERL to IRL Trade Exit: {trade_data}")
            
            # Execute the exit through position manager
            success = self.position_manager.exit_position(
                symbol=trade_data['symbol'],
                price=trade_data['exit_price'],
                reason=trade_data.get('reason', 'Strategy Exit')
            )
            
            if success:
                if self.logger:
                    self.logger.info(f"✅ ERL to IRL trade exited successfully")
            else:
                if self.logger:
                    self.logger.error(f"❌ Failed to exit ERL to IRL trade")
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in ERL to IRL trade exit: {e}")
    
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
            if self.multi_symbol_demo_client:
                # Use multi-symbol demo client for ERL to IRL strategy
                self.multi_symbol_demo_client.set_callback(self._on_multi_symbol_price_update)
                self.multi_symbol_demo_client.start_data_stream()
                self.multi_symbol_demo_client.start_simulation()
            else:
                # Use single-symbol demo client for regular strategy
                self.demo_client.set_callback(self._on_price_update)
                self.demo_client.start_data_stream()
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
                    if self.multi_symbol_demo_client:
                        # Use multi-symbol demo client for ERL to IRL strategy
                        status = self.multi_symbol_demo_client.get_server_status()
                    elif self.demo_client:
                        # Use single-symbol demo client for regular strategy
                        status = self.demo_client.get_server_status()
                    else:
                        status = {"error": "No demo client available"}
                    
                    if "error" in status or "completed" in status.get("status", ""):
                        self.logger.info("Demo simulation completed")
                        break
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Received interrupt signal (Ctrl+C)")
        except Exception as e:
            self.logger.log_error("Error in main loop", e)
        finally:
            self.stop_trading()


    
    def initialize_previous_15min_candle(self):
        """
        Initialize the latest 15-minute candle from Dhan API for proper tracking.
        This is essential for proper sweep detection.
        """
        try:
            self.logger.info("🔄 Initializing latest 15-minute candle from Dhan API...")
            
            # Calculate the correct time range based on mode
            if self.config.is_demo_mode():
                # For demo mode, get the last 15-minute candle from previous trading day
                demo_start = self.config.get_demo_start_datetime()
                previous_day = demo_start - timedelta(days=1)
                
                # If previous day was weekend, go back to Friday
                while previous_day.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    previous_day -= timedelta(days=1)
                
                # Last 15-minute candle of previous trading day: 15:14-15:29
                start_time = previous_day.replace(hour=15, minute=14, second=0, microsecond=0)
                end_time = previous_day.replace(hour=15, minute=29, second=59, microsecond=999999)
                
                self.logger.info(f"   Demo mode: Fetching last 15-min candle from previous trading day")
                self.logger.info(f"   Previous trading day: {previous_day.strftime('%Y-%m-%d')}")
                self.logger.info(f"   Time range: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                # For live mode, get the last completed 15-minute candle based on current time
                current_time = datetime.now(pytz.timezone('Asia/Kolkata'))
                
                # Calculate the last completed 15-minute candle time
                # 15-minute periods: 9:15-9:29, 9:30-9:44, 9:45-9:59, 10:00-10:14, etc.
                
                # Calculate which period we're currently in
                minutes_since_9_15 = (current_time.hour - 9) * 60 + (current_time.minute - 15)
                current_period = minutes_since_9_15 // 15
                
                # Go back one period to get the last completed period
                last_completed_period = current_period - 1
                
                # Calculate the start time of the last completed period
                last_completed_minutes = last_completed_period * 15
                last_candle_start = current_time.replace(hour=9, minute=15, second=0, microsecond=0) + timedelta(minutes=last_completed_minutes)
                
                # Handle edge case: if we're before 9:15, get previous day's last candle
                if last_candle_start >= current_time:
                    previous_day = current_time - timedelta(days=1)
                    while previous_day.weekday() >= 5:  # Weekend
                        previous_day -= timedelta(days=1)
                    last_candle_start = previous_day.replace(hour=15, minute=15, second=0, microsecond=0)
                
                # Set time range for the last completed 15-minute candle
                start_time = last_candle_start
                end_time = last_candle_start + timedelta(minutes=15, seconds=-1, microseconds=999999)
                
                self.logger.info(f"   Live mode: Fetching last completed 15-minute candle")
                self.logger.info(f"   Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"   Last completed candle: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Fetch from Dhan API for all symbols
            for symbol in self.symbols:
                self.logger.info(f"   Fetching latest 15-min candle for {symbol}...")
                self._fetch_latest_15min_candles_for_symbol(symbol, start_time, end_time)
                
        except Exception as e:
            self.logger.warning(f"⚠️ Could not initialize 15-minute candles: {e}")
            self.logger.info("   Continuing without 15-minute candle initialization...")
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
                        open_price=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close'])
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
    
    def _fetch_latest_15min_candles_for_symbol(self, symbol, start_time, end_time):
        """Fetch latest 15-minute candle from Dhan API for a specific symbol"""
        try:
            self.logger.info(f"   Fetching latest 15-minute candle for {symbol}: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Use the historical fetcher to get 15-minute candles directly
            historical_data = self.historical_fetcher.fetch_15min_candles(
                symbol=symbol,
                instruments_df=self.instruments_df,
                start_date=start_time,
                end_date=end_time
            )
            
            if historical_data is not None and len(historical_data) > 0:
                # Debug: Print what we requested vs what we received
                self.logger.info(f"   REQUESTED: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"   API Response: Received {len(historical_data)} candles for {symbol}")
                for i, (_, row) in enumerate(historical_data.iterrows()):
                    self.logger.info(f"   Candle {i+1}: {row['timestamp']} | O:{row['open']} H:{row['high']} L:{row['low']} C:{row['close']}")
                
                # Find the candle that matches our requested start time
                matching_candle = None
                for _, row in historical_data.iterrows():
                    if row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') == start_time.strftime('%Y-%m-%d %H:%M:%S'):
                        matching_candle = row
                        break
                
                # If no exact match, take the first candle (closest to our request)
                if matching_candle is None:
                    self.logger.warning(f"   No exact timestamp match found for {symbol}, taking first candle")
                    matching_candle = historical_data.iloc[0]
                
                candle = Candle(
                    timestamp=matching_candle['timestamp'],
                    open_price=round_to_tick(float(matching_candle['open']), self.config.tick_size),
                    high=round_to_tick(float(matching_candle['high']), self.config.tick_size),
                    low=round_to_tick(float(matching_candle['low']), self.config.tick_size),
                    close=round_to_tick(float(matching_candle['close']), self.config.tick_size)
                )
                
                self.logger.info(f"✅ Loaded latest 15-minute candle for {symbol}")
                self.logger.info(f"   Latest 15-min candle: {candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Log the OHLC data of the loaded candle
                self.logger.log_candle_data(
                    "15min", candle.timestamp,
                    candle.open, candle.high, candle.low, candle.close,
                    symbol=symbol
                )
                
                # Pass the 15-minute candle to strategy for tracking
                if self.config.is_dual_symbol_mode() and self.strategy_manager:
                    self.strategy_manager.set_initial_15min_candle(symbol, candle)
                elif self.strategy:
                    self.strategy.set_initial_15min_candle(candle)
                    # Legacy single symbol mode
                    self.fifteen_min_candles.clear()
                    self.fifteen_min_candles.append(candle)
                    self.last_15min_candle_time = candle.timestamp
            else:
                self.logger.warning(f"⚠️ No 15-minute candle data received for {symbol}")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error fetching latest 15-minute candle for {symbol}: {e}")
            import traceback
            self.logger.warning(f"   Traceback: {traceback.format_exc()}")
    
    def _fetch_latest_15min_candles(self, start_time, end_time):
        """Fetch latest 15-minute candle from Dhan API for both live and demo modes (legacy method)"""
        # This method is kept for backward compatibility but now delegates to the new method
        self._fetch_latest_15min_candles_for_symbol(self.symbol, start_time, end_time)
    
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
                    open_price=round_to_tick(float(row['open']), self.config.tick_size),
                    high=round_to_tick(float(row['high']), self.config.tick_size),
                    low=round_to_tick(float(row['low']), self.config.tick_size),
                    close=round_to_tick(float(row['close']), self.config.tick_size)
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
