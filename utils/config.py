"""
Configuration module for trading bot settings
Clean, simple configuration for single symbol trading
"""

import os
from enum import Enum
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class TradingMode(Enum):
    LIVE = "live"
    DEMO = "demo"

class StrategyMode(Enum):
    CANDLE_STRATEGY = "candle_strategy"
    ERL_TO_IRL = "erl_to_irl"
    IRL_TO_ERL = "irl_to_erl"
    ALL = "all"

class TradingConfig:
    """Clean configuration class for single symbol trading"""
    
    def __init__(self):
        # Trading mode
        self.mode = TradingMode(os.getenv('TRADING_MODE', 'demo').lower())
        
        # Strategy mode
        self.strategy_mode = StrategyMode(os.getenv('STRATEGY_MODE', 'ALL').lower())
        
        # Trading symbol (single symbol only)
        self.symbol = self._get_trading_symbol()
        
        # Common settings
        self.tick_size = float(os.getenv('TICK_SIZE', 0.05))
        self.quantity = int(os.getenv('TRADING_QUANTITY', 1))
        
        # Account management settings
        self.account_start_balance = float(os.getenv('ACCT_START_BALANCE', 50000))
        self.fixed_sl_percentage = float(os.getenv('FIXED_SL_PERCENTAGE', 20.0))
        self.lot_size = int(os.getenv('LOT_SIZE', 75))
        self.max_sl_percentage_of_price = float(os.getenv('MAX_SL_PERCENTAGE_OF_PRICE', 25.0))
        
        # Live trading settings
        self.client_id = os.getenv('DHAN_CLIENT_ID')
        self.access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        # Demo trading settings
        self.demo_start_date = os.getenv('DEMO_START_DATE', '2025-09-01')
        self.demo_interval_minutes = int(os.getenv('DEMO_INTERVAL_MINUTES', 1))
        self.demo_server_port = int(os.getenv('DEMO_SERVER_PORT', 8080))
        self.demo_stream_interval_seconds = float(os.getenv('DEMO_STREAM_INTERVAL_SECONDS', 2.0))
        
        # Historical data settings
        self.historical_data_days = int(os.getenv('HISTORICAL_DATA_DAYS', 7))
        
        # Strategy parameters
        self.swing_look_back = int(os.getenv('SWING_LOOK_BACK', 2))
        
        # Logging settings
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.log_to_file = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
        self.log_dir = os.getenv('LOG_DIR', 'logs')
    
    def _get_trading_symbol(self):
        """Get the single trading symbol based on mode"""
        if self.is_live_mode():
            return os.getenv('LIVE_SYMBOL', os.getenv('SYMBOL', None))
        else:
            return os.getenv('DEMO_SYMBOL', 'NIFTY 16 SEP 25000 CALL')
    
    def is_live_mode(self):
        """Check if running in live trading mode"""
        return self.mode == TradingMode.LIVE
    
    def is_demo_mode(self):
        """Check if running in demo trading mode"""
        return self.mode == TradingMode.DEMO
    
    def is_erl_to_irl_strategy(self):
        """Check if ERL to IRL strategy is enabled"""
        return self.strategy_mode == StrategyMode.ERL_TO_IRL or self.strategy_mode == StrategyMode.ALL
    
    def is_irl_to_erl_strategy(self):
        """Check if IRL to ERL strategy is enabled"""
        return self.strategy_mode == StrategyMode.IRL_TO_ERL or self.strategy_mode == StrategyMode.BOTH
    
    def is_all_strategies(self):
        """Check if both strategies are enabled"""
        return self.strategy_mode == StrategyMode.ALL
    
    def get_demo_start_datetime(self):
        """Get demo start datetime with market hours"""
        base_datetime = datetime.strptime(self.demo_start_date, '%Y-%m-%d')
        # Set to 9:15 AM (market open)
        # Set to 15:29 PM of the last trading day before base_datetime (skip weekends)
        last_trading_day = base_datetime
        while last_trading_day.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            last_trading_day = last_trading_day - timedelta(days=1)
        last_trading_day = last_trading_day - timedelta(days=1)
        while last_trading_day.weekday() >= 5:
            last_trading_day = last_trading_day - timedelta(days=1)
        return last_trading_day.replace(hour=15, minute=30, second=0, microsecond=0)
        #return base_datetime.replace(hour=9, minute=14, second=0, microsecond=0)

    def get_demo_start_datetime_streaming(self):
        """Get demo start datetime with market hours"""
        base_datetime = datetime.strptime(self.demo_start_date, '%Y-%m-%d')
        return base_datetime.replace(hour=9, minute=14, second=0, microsecond=0)
    
    def get_num_hist_days(self):
        """Get number of historical data days"""
        return self.historical_data_days if self.historical_data_days > 0 else 7
    
    def get_fixed_sl_amount(self):
        """Get fixed SL amount in INR"""
        return self.account_start_balance * (self.fixed_sl_percentage / 100.0)
    
    def validate_config(self):
        """Validate configuration settings"""
        if self.is_live_mode():
            if not self.client_id or not self.access_token:
                raise ValueError("Live trading mode requires DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN")
            if not self.symbol:
                raise ValueError("Live trading mode requires LIVE_SYMBOL")
        
        if self.is_demo_mode():
            if not self.symbol:
                raise ValueError("Demo trading mode requires DEMO_SYMBOL")
            try:
                self.get_demo_start_datetime()
            except ValueError:
                raise ValueError("Invalid DEMO_START_DATE format. Use YYYY-MM-DD")
        
        # Validate account settings
        if self.account_start_balance <= 0:
            raise ValueError("ACCT_START_BALANCE must be positive")
        if self.fixed_sl_percentage <= 0 or self.fixed_sl_percentage > 100:
            raise ValueError("FIXED_SL_PERCENTAGE must be between 0 and 100")
        if self.lot_size <= 0:
            raise ValueError("LOT_SIZE must be positive")
        if self.max_sl_percentage_of_price <= 0 or self.max_sl_percentage_of_price > 100:
            raise ValueError("MAX_SL_PERCENTAGE_OF_PRICE must be between 0 and 100")
        
        return True
    
    def print_config(self):
        """Print current configuration"""
        print(f"\n=== Trading Bot Configuration ===")
        print(f"Mode: {self.mode.value.upper()}")
        print(f"Strategy: {self.strategy_mode.value.upper()}")
        print(f"Symbol: {self.symbol}")
        print(f"Tick Size: {self.tick_size}")
        print(f"Trading Quantity: {self.quantity}")
        print(f"Account Start Balance: ₹{self.account_start_balance:,.2f}")
        print(f"Fixed SL Amount: ₹{self.get_fixed_sl_amount():,.2f} ({self.fixed_sl_percentage}% of balance)")
        print(f"Lot Size: {self.lot_size}")
        print(f"Max SL % of Price: {self.max_sl_percentage_of_price}%")
        print(f"Swing Look Back: {self.swing_look_back}")
        print(f"Log Level: {self.log_level}")
        print(f"Log to File: {self.log_to_file}")
        print(f"Log Directory: {self.log_dir}")
        
        if self.is_live_mode():
            print(f"Client ID: {self.client_id}")
            print(f"Access Token: {'*' * 10}{self.access_token[-4:] if self.access_token else 'None'}")
        
        if self.is_demo_mode():
            print(f"Demo Start Date: {self.demo_start_date}")
            print(f"Demo Interval: {self.demo_interval_minutes} minutes")
            print(f"Demo Server Port: {self.demo_server_port}")
            print(f"Demo Stream Speed: {self.demo_stream_interval_seconds} seconds per candle")
            print(f"Historical Data Days: {self.historical_data_days}")
        
        print("=" * 35)