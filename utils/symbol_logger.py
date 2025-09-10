"""
Symbol-specific logging utility for the trading bot
Creates separate log files for each symbol to avoid confusion
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

class SymbolLogger:
    """Custom logger that creates separate log files for each symbol"""
    
    def __init__(self, log_dir="logs", log_level=logging.INFO):
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        
        # Create logs directory if it doesn't exist
        self.log_dir.mkdir(exist_ok=True)
        
        # Dictionary to store symbol-specific loggers
        self.symbol_loggers: Dict[str, logging.Logger] = {}
        self.symbol_handlers: Dict[str, logging.FileHandler] = {}
        
        # Create main bot logger (for general bot operations)
        self.main_logger = self._create_main_logger()
        
        # Log startup message
        self.info("=" * 80)
        self.info("TRADING BOT LOGGING STARTED")
        self.info(f"Log directory: {self.log_dir}")
        self.info("=" * 80)
    
    def _create_main_logger(self) -> logging.Logger:
        """Create the main bot logger for general operations"""
        logger = logging.getLogger('TradingBot_Main')
        logger.setLevel(self.log_level)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
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
            self.log_dir / f'trading_bot_main_{timestamp}.log',
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler for user-friendly output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _create_symbol_logger(self, symbol: str) -> logging.Logger:
        """Create a logger for a specific symbol"""
        # Sanitize symbol name for filename
        safe_symbol = "".join(c for c in symbol if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_symbol = safe_symbol.replace(' ', '_')
        
        logger = logging.getLogger(f'TradingBot_{safe_symbol}')
        logger.setLevel(self.log_level)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = logging.Formatter(
            f'[{symbol}] %(message)s'
        )
        
        # File handler for symbol-specific logs
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_handler = logging.FileHandler(
            self.log_dir / f'trading_bot_{safe_symbol}_{timestamp}.log',
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler with symbol prefix
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # Store the file handler for cleanup
        self.symbol_handlers[symbol] = file_handler
        
        return logger
    
    def get_symbol_logger(self, symbol: str) -> logging.Logger:
        """Get or create a logger for a specific symbol"""
        if symbol not in self.symbol_loggers:
            self.symbol_loggers[symbol] = self._create_symbol_logger(symbol)
            self.info(f"Created symbol-specific logger for: {symbol}")
        return self.symbol_loggers[symbol]
    
    def debug(self, message: str, symbol: Optional[str] = None):
        """Log debug message"""
        if symbol:
            self.get_symbol_logger(symbol).debug(message)
        else:
            self.main_logger.debug(message)
    
    def info(self, message: str, symbol: Optional[str] = None):
        """Log info message"""
        if symbol:
            self.get_symbol_logger(symbol).info(message)
        else:
            self.main_logger.info(message)
    
    def warning(self, message: str, symbol: Optional[str] = None):
        """Log warning message"""
        if symbol:
            self.get_symbol_logger(symbol).warning(message)
        else:
            self.main_logger.warning(message)
    
    def error(self, message: str, symbol: Optional[str] = None):
        """Log error message"""
        if symbol:
            self.get_symbol_logger(symbol).error(message)
        else:
            self.main_logger.error(message)
    
    def critical(self, message: str, symbol: Optional[str] = None):
        """Log critical message"""
        if symbol:
            self.get_symbol_logger(symbol).critical(message)
        else:
            self.main_logger.critical(message)
    
    def log_trade_entry(self, entry_price, stop_loss, target, trigger_type, symbol):
        """Log trade entry details"""
        self.info("🎯 TRADE ENTRY", symbol)
        self.info(f"   Symbol: {symbol}", symbol)
        self.info(f"   Trigger: {trigger_type}", symbol)
        self.info(f"   Entry Price: {entry_price:.2f}", symbol)
        self.info(f"   Stop Loss: {stop_loss:.2f}", symbol)
        self.info(f"   Target: {target:.2f}", symbol)
        self.info(f"   Risk: {entry_price - stop_loss:.2f}", symbol)
        self.info(f"   Reward: {target - entry_price:.2f}", symbol)
        self.info(f"   RR Ratio: {(target - entry_price) / (entry_price - stop_loss):.2f}", symbol)
        self.info("-" * 50, symbol)
    
    def log_trade_exit(self, exit_price, reason, entry_price, pnl, account_balance=None, symbol=None):
        """Log trade exit details"""
        self.info("🚪 TRADE EXIT", symbol)
        self.info(f"   Reason: {reason}", symbol)
        self.info(f"   Entry Price: {entry_price:.2f}", symbol)
        self.info(f"   Exit Price: {exit_price:.2f}", symbol)
        self.info(f"   P&L: {pnl:.2f}", symbol)
        if account_balance is not None:
            self.info(f"   Account Balance: {account_balance:.2f}", symbol)
        self.info("-" * 50, symbol)
    
    def log_fvg_detection(self, gap_size, entry_price, stop_loss, candles, symbol=None):
        """Log FVG detection details"""
        self.info("✅ FVG DETECTED", symbol)
        self.info(f"   Symbol: {symbol}", symbol)
        self.info(f"   Gap Size: {gap_size:.2f}", symbol)
        self.info(f"   Entry Price: {entry_price:.2f}", symbol)
        self.info(f"   Stop Loss: {stop_loss:.2f}", symbol)
        self.info(f"   Candles: {len(candles)}", symbol)
        self.info("-" * 50, symbol)
    
    def log_sweep_detection(self, target_low, sweep_low, recovery_low, timestamp, candle_data=None, symbol=None):
        """Log sweep detection details"""
        self.info("🔄 SWEEP DETECTED", symbol)
        self.info(f"   Symbol: {symbol}", symbol)
        self.info(f"   Target Low: {target_low:.2f}", symbol)
        self.info(f"   Sweep Low: {sweep_low:.2f}", symbol)
        self.info(f"   Recovery Low: {recovery_low:.2f}", symbol)
        self.info(f"   Time: {timestamp.strftime('%H:%M:%S')}", symbol)
        if candle_data:
            self.info(f"   Sweep Candle: O:{candle_data['open']:.2f} H:{candle_data['high']:.2f} L:{candle_data['low']:.2f} C:{candle_data['close']:.2f}", symbol)
        self.info("-" * 50, symbol)
    
    def log_price_update(self, price, timestamp, source="unknown", symbol=None):
        """Log price update"""
        self.debug(f"💰 Price Update: {price:.2f} at {timestamp.strftime('%H:%M:%S')} from {source}", symbol)
    
    def log_error(self, error_msg, exception=None, symbol=None):
        """Log error with optional exception details"""
        self.error(f"❌ ERROR: {error_msg}", symbol)
        if exception:
            self.error(f"   Exception: {str(exception)}", symbol)
            self.error(f"   Type: {type(exception).__name__}", symbol)
    
    def log_candle_data(self, timeframe, timestamp, open_price, high, low, close, volume=None, symbol=None):
        """Log candle data"""
        volume_str = f" V:{volume}" if volume else ""
        symbol_str = f" [{symbol}]" if symbol else ""
        self.info(f"📊 {timeframe} Candle{symbol_str}: {timestamp.strftime('%Y-%m-%d %H:%M:%S')} | O:{open_price:.2f} H:{high:.2f} L:{low:.2f} C:{close:.2f}{volume_str}", symbol)
    
    def log_15min_candle_completion(self, candle, symbol=None):
        """Log 15-minute candle completion"""
        self.info("🕯️ 15-MINUTE CANDLE COMPLETED", symbol)
        self.info(f"   Time: {candle.timestamp.strftime('%H:%M:%S')}", symbol)
        self.info(f"   OHLC: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}", symbol)
        self.info(f"   Body: {candle.body_size():.2f} ({candle.body_percentage():.1f}%)", symbol)
        self.info(f"   Type: {'BULL' if candle.is_bull_candle() else 'BEAR' if candle.is_bear_candle() else 'NEUTRAL'}", symbol)
        self.info("-" * 50, symbol)

    def log_5min_candle_completion(self, candle, symbol=None):
        """Log 5-minute candle completion"""
        self.info("🕯️ 5-MINUTE CANDLE COMPLETED", symbol)
        self.info(f"   Time: {candle.timestamp.strftime('%H:%M:%S')}", symbol)
        self.info(f"   OHLC: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}", symbol)
        self.info(f"   Body: {candle.body_size():.2f} ({candle.body_percentage():.1f}%)", symbol)
        self.info(f"   Type: {'BULL' if candle.is_bull_candle() else 'BEAR' if candle.is_bear_candle() else 'NEUTRAL'}", symbol)
        self.info("-" * 50, symbol)

    def log_1min_candle_completion(self, candle, symbol=None):
        """Log 1-minute candle completion"""
        self.info("📊 1-MINUTE CANDLE COMPLETED", symbol)
        self.info(f"   Time: {candle.timestamp.strftime('%H:%M:%S')}", symbol)
        self.info(f"   OHLC: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}", symbol)
        self.info(f"   Body: {candle.body_size():.2f} ({candle.body_percentage():.1f}%)", symbol)
        self.info(f"   Type: {'BULL' if candle.is_bull_candle() else 'BEAR' if candle.is_bear_candle() else 'NEUTRAL'}", symbol)
        self.info("-" * 50, symbol)
    
    def log_cisd_detection(self, entry, stop_loss, bear_candle_open, bear_candle_data=None, symbol=None):
        """Log CISD detection"""
        self.info("🎯 CISD DETECTED", symbol)
        self.info(f"   Entry: {entry:.2f}", symbol)
        self.info(f"   Stop Loss: {stop_loss:.2f}", symbol)
        self.info(f"   Bear Candle Open: {bear_candle_open:.2f}", symbol)
        if bear_candle_data:
            self.info(f"   Bear Candle: O:{bear_candle_data['open']:.2f} H:{bear_candle_data['high']:.2f} L:{bear_candle_data['low']:.2f} C:{bear_candle_data['close']:.2f}", symbol)
        self.info("-" * 50, symbol)
    
    def log_stop_loss_movement(self, old_sl, new_sl, reason, symbol=None):
        """Log stop loss movement"""
        self.info("🛡️ STOP LOSS MOVED", symbol)
        self.info(f"   Old SL: {old_sl:.2f}", symbol)
        self.info(f"   New SL: {new_sl:.2f}", symbol)
        self.info(f"   Reason: {reason}", symbol)
        self.info("-" * 50, symbol)
    
    def log_target_movement(self, old_target, new_target, reason, symbol=None):
        """Log target movement"""
        self.info("🎯 TARGET MOVED", symbol)
        self.info(f"   Old Target: {old_target:.2f}", symbol)
        self.info(f"   New Target: {new_target:.2f}", symbol)
        self.info(f"   Reason: {reason}", symbol)
        self.info("-" * 50, symbol)
    
    def log_swing_low_detection(self, price, timestamp, symbol=None):
        """Log swing low detection"""
        self.info("📉 SWING LOW DETECTED", symbol)
        self.info(f"   Price: {price:.2f}", symbol)
        self.info(f"   Time: {timestamp.strftime('%H:%M:%S')}", symbol)
        self.info("-" * 50, symbol)
    
    def log_strategy_status(self, status_dict, symbol=None):
        """Log strategy status"""
        self.info("📊 STRATEGY STATUS", symbol)
        for key, value in status_dict.items():
            self.info(f"   {key}: {value}", symbol)
        self.info("-" * 50, symbol)
    
    def log_trade_entry(self, entry_price, stop_loss, target, trigger_type, symbol=None):
        """Log trade entry details"""
        risk = entry_price - stop_loss
        reward = target - entry_price
        rr_ratio = reward / risk if risk > 0 else 0
        
        # If symbol is None, log to main logger instead of creating N/A logger
        if symbol is None:
            self.main_logger.info(f"🎯 TRADE ENTRY")
            self.main_logger.info(f"   Symbol: N/A")
            self.main_logger.info(f"   Trigger: {trigger_type.upper()}")
            self.main_logger.info(f"   Entry Price: {entry_price:.2f}")
            self.main_logger.info(f"   Stop Loss: {stop_loss:.2f}")
            self.main_logger.info(f"   Target: {target:.2f}")
            self.main_logger.info(f"   Risk: {risk:.2f}")
            self.main_logger.info(f"   Reward: {reward:.2f}")
            self.main_logger.info(f"   RR Ratio: {rr_ratio:.2f}")
            self.main_logger.info("-" * 50)
        else:
            self.info(f"🎯 TRADE ENTRY", symbol)
            self.info(f"   Symbol: {symbol}", symbol)
            self.info(f"   Trigger: {trigger_type.upper()}", symbol)
            self.info(f"   Entry Price: {entry_price:.2f}", symbol)
            self.info(f"   Stop Loss: {stop_loss:.2f}", symbol)
            self.info(f"   Target: {target:.2f}", symbol)
            self.info(f"   Risk: {risk:.2f}", symbol)
            self.info(f"   Reward: {reward:.2f}", symbol)
            self.info(f"   RR Ratio: {rr_ratio:.2f}", symbol)
            self.info("-" * 50, symbol)
    
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
    
    def close_all_handlers(self):
        """Close all file handlers"""
        for handler in self.symbol_handlers.values():
            handler.close()
        
        # Close main logger handlers
        for handler in self.main_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.close()
