"""
Logger wrapper that provides symbol-specific logging to strategies
"""

class LoggerWrapper:
    """Wrapper that provides symbol-specific logging methods to strategies"""
    
    def __init__(self, symbol_logger, symbol: str = None):
        self.symbol_logger = symbol_logger
        self.symbol = symbol
    
    def debug(self, message):
        """Log debug message"""
        self.symbol_logger.debug(message, self.symbol)
    
    def info(self, message):
        """Log info message"""
        self.symbol_logger.info(message, self.symbol)
    
    def warning(self, message):
        """Log warning message"""
        self.symbol_logger.warning(message, self.symbol)
    
    def error(self, message):
        """Log error message"""
        self.symbol_logger.error(message, self.symbol)
    
    def critical(self, message):
        """Log critical message"""
        self.symbol_logger.critical(message, self.symbol)
    
    def log_trade_entry(self, entry_price, stop_loss, target, trigger_type, symbol=None):
        """Log trade entry details"""
        self.symbol_logger.log_trade_entry(entry_price, stop_loss, target, trigger_type, symbol or self.symbol)
    
    def log_trade_exit(self, exit_price, reason, entry_price, pnl, account_balance=None, symbol=None):
        """Log trade exit details"""
        self.symbol_logger.log_trade_exit(exit_price, reason, entry_price, pnl, account_balance, symbol or self.symbol)
    
    def log_fvg_detection(self, gap_size, entry_price, stop_loss, candles, symbol=None):
        """Log FVG detection details"""
        self.symbol_logger.log_fvg_detection(gap_size, entry_price, stop_loss, candles, symbol or self.symbol)
    
    def log_sweep_detection(self, target_low, sweep_low, recovery_low, timestamp, candle_data=None, symbol=None):
        """Log sweep detection details"""
        self.symbol_logger.log_sweep_detection(target_low, sweep_low, recovery_low, timestamp, candle_data, symbol or self.symbol)
    
    def log_price_update(self, price, timestamp, source="unknown", symbol=None):
        """Log price update"""
        self.symbol_logger.log_price_update(price, timestamp, source, symbol or self.symbol)
    
    def log_error(self, error_msg, exception=None, symbol=None):
        """Log error with optional exception details"""
        self.symbol_logger.log_error(error_msg, exception, symbol or self.symbol)
    
    def log_candle_data(self, timeframe, timestamp, open_price, high, low, close, volume=None, symbol=None):
        """Log candle data"""
        self.symbol_logger.log_candle_data(timeframe, timestamp, open_price, high, low, close, volume, symbol or self.symbol)
    
    def log_15min_candle_completion(self, candle, symbol=None):
        """Log 15-minute candle completion"""
        self.symbol_logger.log_15min_candle_completion(candle, symbol or self.symbol)
    
    def log_5min_candle_completion(self, candle, symbol=None):
        """Log 5-minute candle completion"""
        self.symbol_logger.log_5min_candle_completion(candle, symbol or self.symbol)
    
    def log_1min_candle_completion(self, candle, symbol=None):
        """Log 1-minute candle completion"""
        self.symbol_logger.log_1min_candle_completion(candle, symbol or self.symbol)
    
    def log_cisd_detection(self, entry, stop_loss, bear_candle_open, bear_candle_data=None, symbol=None):
        """Log CISD detection"""
        self.symbol_logger.log_cisd_detection(entry, stop_loss, bear_candle_open, bear_candle_data, symbol or self.symbol)
    
    def log_stop_loss_movement(self, old_sl, new_sl, reason, symbol=None):
        """Log stop loss movement"""
        self.symbol_logger.log_stop_loss_movement(old_sl, new_sl, reason, symbol or self.symbol)
    
    def log_target_movement(self, old_target, new_target, reason, symbol=None):
        """Log target movement"""
        self.symbol_logger.log_target_movement(old_target, new_target, reason, symbol or self.symbol)
    
    def log_swing_low_detection(self, price, timestamp, symbol=None):
        """Log swing low detection"""
        self.symbol_logger.log_swing_low_detection(price, timestamp, symbol or self.symbol)
    
    def log_strategy_status(self, status_dict, symbol=None):
        """Log strategy status"""
        self.symbol_logger.log_strategy_status(status_dict, symbol or self.symbol)
    
    def log_config(self, config_dict):
        """Log configuration details"""
        self.symbol_logger.log_config(config_dict)
    
    def log_trade_entry(self, entry_price, stop_loss, target, trigger_type, symbol=None):
        """Log trade entry details"""
        self.symbol_logger.log_trade_entry(entry_price, stop_loss, target, trigger_type, symbol or self.symbol)
