"""
Logging utility for the trading bot
Handles both console and file logging with different log levels
"""

import logging
import os
from datetime import datetime
from pathlib import Path

class TradingLogger:
    """Custom logger for trading bot with file and console output"""
    
    def __init__(self, log_dir="logs", log_level=logging.INFO):
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        
        # Create logs directory if it doesn't exist
        self.log_dir.mkdir(exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger('TradingBot')
        self.logger.setLevel(log_level)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = logging.Formatter(
            '%(message)s'
        )
        
        # File handler for detailed logs
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_handler = logging.FileHandler(
            self.log_dir / f'trading_bot_{timestamp}.log',
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler for user-friendly output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Log startup message
        self.info("=" * 80)
        self.info("TRADING BOT LOGGING STARTED")
        self.info(f"Log file: {self.log_dir / f'trading_bot_{timestamp}.log'}")
        self.info("=" * 80)
    
    def debug(self, message):
        """Log debug message"""
        self.logger.debug(message)
    
    def info(self, message):
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message):
        """Log error message"""
        self.logger.error(message)
    
    def critical(self, message):
        """Log critical message"""
        self.logger.critical(message)
    
    def log_trade_entry(self, entry_price, stop_loss, target, trigger_type, symbol):
        """Log trade entry details"""
        self.info("🎯 TRADE ENTRY")
        self.info(f"   Symbol: {symbol}")
        self.info(f"   Trigger: {trigger_type}")
        self.info(f"   Entry Price: {entry_price:.2f}")
        self.info(f"   Stop Loss: {stop_loss:.2f}")
        self.info(f"   Target: {target:.2f}")
        self.info(f"   Risk: {entry_price - stop_loss:.2f}")
        self.info(f"   Reward: {target - entry_price:.2f}")
        self.info(f"   RR Ratio: {(target - entry_price) / (entry_price - stop_loss):.2f}")
        self.info("-" * 50)
    
    def log_trade_exit(self, exit_price, reason, entry_price, pnl, account_balance=None):
        """Log trade exit details"""
        self.info("🚪 TRADE EXIT")
        self.info(f"   Reason: {reason}")
        self.info(f"   Entry Price: {entry_price:.2f}")
        self.info(f"   Exit Price: {exit_price:.2f}")
        self.info(f"   P&L: {pnl:.2f}")
        if account_balance is not None:
            self.info(f"   Account Balance: ₹{account_balance:.2f}")
        self.info("-" * 50)
    
    def log_candle_data(self, timeframe, timestamp, open_price, high, low, close, volume=None):
        """Log candle data"""
        volume_str = f" V:{volume}" if volume else ""
        self.info(f"📊 {timeframe} Candle: {timestamp.strftime('%H:%M:%S')} | O:{open_price:.2f} H:{high:.2f} L:{low:.2f} C:{close:.2f}{volume_str}")
    
    def log_sweep_detection(self, target_low, sweep_low, recovery_low, timestamp, candle_data=None):
        """Log sweep detection"""
        self.info("🎯 SWEEP DETECTED")
        self.info(f"   Target Low: {target_low:.2f}")
        self.info(f"   Sweep Low: {sweep_low:.2f}")
        self.info(f"   Recovery Low: {recovery_low:.2f}")
        self.info(f"   Time: {timestamp.strftime('%H:%M:%S')}")
        if candle_data:
            self.info(f"   Sweep Candle: O:{candle_data['open']:.2f} H:{candle_data['high']:.2f} L:{candle_data['low']:.2f} C:{candle_data['close']:.2f}")
        self.info("-" * 50)
    
    def log_fvg_detection(self, gap_size, entry, stop_loss, candles):
        """Log FVG detection"""
        self.info("✅ FVG DETECTED")
        self.info(f"   Gap Size: {gap_size:.2f}")
        self.info(f"   Entry: {entry:.2f}")
        self.info(f"   Stop Loss: {stop_loss:.2f}")
        self.info(f"   Candles: {len(candles)}")
        # Log the 3 candles that formed the FVG
        if len(candles) >= 3:
            c1, c2, c3 = candles[-3:]
            self.info(f"   C1: {c1.timestamp.strftime('%H:%M:%S')} O:{c1.open:.2f} H:{c1.high:.2f} L:{c1.low:.2f} C:{c1.close:.2f}")
            self.info(f"   C2: {c2.timestamp.strftime('%H:%M:%S')} O:{c2.open:.2f} H:{c2.high:.2f} L:{c2.low:.2f} C:{c2.close:.2f}")
            self.info(f"   C3: {c3.timestamp.strftime('%H:%M:%S')} O:{c3.open:.2f} H:{c3.high:.2f} L:{c3.low:.2f} C:{c3.close:.2f}")
        self.info("-" * 50)
    
    def log_cisd_detection(self, entry, stop_loss, bear_candle_open, bear_candle_data=None):
        """Log CISD detection"""
        self.info("✅ CISD DETECTED")
        self.info(f"   Entry: {entry:.2f}")
        self.info(f"   Stop Loss: {stop_loss:.2f}")
        self.info(f"   Bear Candle Open: {bear_candle_open:.2f}")
        if bear_candle_data:
            self.info(f"   Bear Candle: {bear_candle_data.timestamp.strftime('%H:%M:%S')} O:{bear_candle_data.open:.2f} H:{bear_candle_data.high:.2f} L:{bear_candle_data.low:.2f} C:{bear_candle_data.close:.2f}")
        self.info("-" * 50)
    
    def log_stop_loss_movement(self, old_sl, new_sl, reason):
        """Log stop loss movement"""
        self.info("🔄 STOP LOSS MOVED")
        self.info(f"   Old SL: {old_sl:.2f}")
        self.info(f"   New SL: {new_sl:.2f}")
        self.info(f"   Reason: {reason}")
        self.info("-" * 50)
    
    def log_swing_low_detection(self, price, timestamp):
        """Log swing low detection"""
        self.info(f"📉 Swing Low: {price:.2f} at {timestamp.strftime('%H:%M:%S')}")
    
    def log_strategy_status(self, status_dict):
        """Log strategy status"""
        self.debug("📊 STRATEGY STATUS")
        for key, value in status_dict.items():
            self.debug(f"   {key}: {value}")
    
    def log_15min_candle_completion(self, candle):
        """Log 15-minute candle completion"""
        self.info("🕯️ 15-MINUTE CANDLE COMPLETED")
        self.info(f"   Time: {candle.timestamp.strftime('%H:%M:%S')}")
        self.info(f"   OHLC: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
        self.info(f"   Body: {candle.body_size():.2f} ({candle.body_percentage():.1f}%)")
        self.info(f"   Type: {'BULL' if candle.is_bull_candle() else 'BEAR' if candle.is_bear_candle() else 'NEUTRAL'}")
        self.info("-" * 50)
    
    def log_1min_candle_completion(self, candle):
        """Log 1-minute candle completion"""
        self.info("📊 1-MINUTE CANDLE COMPLETED")
        self.info(f"   Time: {candle.timestamp.strftime('%H:%M:%S')}")
        self.info(f"   OHLC: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
        self.info(f"   Body: {candle.body_size():.2f} ({candle.body_percentage():.1f}%)")
        self.info(f"   Type: {'BULL' if candle.is_bull_candle() else 'BEAR' if candle.is_bear_candle() else 'NEUTRAL'}")
        self.info("-" * 50)
    
    def log_price_update(self, price, timestamp, source="unknown"):
        """Log price update"""
        self.debug(f"💰 Price Update: {price:.2f} at {timestamp.strftime('%H:%M:%S')} from {source}")
    
    def log_error(self, error_msg, exception=None):
        """Log error with optional exception details"""
        self.error(f"❌ ERROR: {error_msg}")
        if exception:
            self.error(f"   Exception: {str(exception)}")
            self.error(f"   Type: {type(exception).__name__}")
    
    def log_config(self, config_dict):
        """Log configuration details"""
        self.info("⚙️ CONFIGURATION")
        for key, value in config_dict.items():
            # Mask sensitive information
            if 'token' in key.lower() or 'password' in key.lower():
                masked_value = '*' * 10 + str(value)[-4:] if value else 'None'
                self.info(f"   {key}: {masked_value}")
            else:
                self.info(f"   {key}: {value}")
        self.info("-" * 50)
