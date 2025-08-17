"""
Configuration module for trading modes and settings
"""

import os
from enum import Enum
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class TradingMode(Enum):
    LIVE = "live"
    DEMO = "demo"

class TradingConfig:
    """Configuration class for trading bot settings"""
    
    def __init__(self):
        # Trading mode
        self.mode = TradingMode(os.getenv('TRADING_MODE', 'demo').lower())
        
        # Common settings
        self.tick_size = float(os.getenv('TICK_SIZE', 0.05))
        self.max_15min_candles = int(os.getenv('MAX_15MIN_CANDLES', 30))
        self.quantity = int(os.getenv('TRADING_QUANTITY', 1))  # Number of lots/quantity to trade
        
        # Live trading settings
        self.client_id = os.getenv('DHAN_CLIENT_ID')
        self.access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        # Demo trading settings
        self.demo_start_date = os.getenv('DEMO_START_DATE', '2024-12-15')  # Recent past date
        self.demo_symbol = os.getenv('DEMO_SYMBOL', 'NIFTY 21 AUG 24700 CALL')  # Updated symbol format
        self.demo_interval_minutes = int(os.getenv('DEMO_INTERVAL_MINUTES', 1))
        self.demo_server_port = int(os.getenv('DEMO_SERVER_PORT', 8080))
        self.demo_stream_interval_seconds = float(os.getenv('DEMO_STREAM_INTERVAL_SECONDS', 5.0))  # How fast to stream data
        
        # Historical data settings
        self.historical_data_days = int(os.getenv('HISTORICAL_DATA_DAYS', 7))
        
        # Swing low detection parameters
        self.swing_look_back = int(os.getenv('SWING_LOOK_BACK', 2))  # Number of candles to look back/forward for swing low detection
        
        # Logging settings
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()  # DEBUG, INFO, WARNING, ERROR
        self.log_to_file = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
        self.log_dir = os.getenv('LOG_DIR', 'logs')
        
    def is_live_mode(self):
        """Check if running in live trading mode"""
        return self.mode == TradingMode.LIVE
    
    def is_demo_mode(self):
        """Check if running in demo trading mode"""
        return self.mode == TradingMode.DEMO
    
    def get_demo_start_datetime(self):
        """Get demo start datetime"""
        return datetime.strptime(self.demo_start_date, '%Y-%m-%d')
    
    def validate_config(self):
        """Validate configuration settings"""
        if self.is_live_mode():
            if not self.client_id or not self.access_token:
                raise ValueError("Live trading mode requires DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN")
        
        if self.is_demo_mode():
            try:
                self.get_demo_start_datetime()
            except ValueError:
                raise ValueError("Invalid DEMO_START_DATE format. Use YYYY-MM-DD")
        
        return True
    
    def print_config(self):
        """Print current configuration"""
        print(f"\n=== Trading Bot Configuration ===")
        print(f"Mode: {self.mode.value.upper()}")
        print(f"Tick Size: {self.tick_size}")
        print(f"Max 15-min Candles: {self.max_15min_candles}")
        print(f"Trading Quantity: {self.quantity}")
        print(f"Swing Look Back: {self.swing_look_back}")
        print(f"Log Level: {self.log_level}")
        print(f"Log to File: {self.log_to_file}")
        print(f"Log Directory: {self.log_dir}")
        
        if self.is_live_mode():
            print(f"Client ID: {self.client_id}")
            print(f"Access Token: {'*' * 10}{self.access_token[-4:] if self.access_token else 'None'}")
        
        if self.is_demo_mode():
            print(f"Demo Start Date: {self.demo_start_date}")
            print(f"Demo Symbol: {self.demo_symbol}")
            print(f"Demo Interval: {self.demo_interval_minutes} minutes")
            print(f"Demo Server Port: {self.demo_server_port}")
            print(f"Demo Stream Speed: {self.demo_stream_interval_seconds} seconds per candle")
            print(f"Historical Data Days: {self.historical_data_days}")
        
        print("=" * 35)
