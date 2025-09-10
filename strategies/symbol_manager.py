"""
Symbol Manager for handling multiple symbols in dual trading mode
Manages separate CandleStrategy instances for each symbol
"""

from strategies.candle_strategy import CandleStrategy
from utils.market_utils import round_to_tick
from utils.logger_wrapper import LoggerWrapper

class SymbolManager:
    """Manages multiple symbol strategies for dual trading"""
    
    def __init__(self, symbols, tick_size=0.05, swing_look_back=2, logger=None, 
                 exit_callback=None, entry_callback=None):
        self.symbols = symbols
        self.tick_size = tick_size
        self.swing_look_back = swing_look_back
        self.logger = logger
        self.exit_callback = exit_callback
        self.entry_callback = entry_callback
        
        # Create separate strategy instances for each symbol
        self.strategies = {}
        for symbol in symbols:
            # Create symbol-specific logger wrapper
            symbol_logger = LoggerWrapper(logger, symbol) if logger else None
            
            self.strategies[symbol] = CandleStrategy(
                tick_size=tick_size,
                swing_look_back=swing_look_back,
                logger=symbol_logger,
                exit_callback=self._create_symbol_exit_callback(symbol),
                entry_callback=self._create_symbol_entry_callback(symbol)
            )
        
        # Track which symbol is currently being traded (only one at a time)
        self.active_symbol = None
        
        if self.logger:
            self.logger.info(f"SymbolManager initialized with {len(symbols)} symbols: {symbols}")
        else:
            print(f"SymbolManager initialized with {len(symbols)} symbols: {symbols}")
    
    def _create_symbol_exit_callback(self, symbol):
        """Create exit callback for a specific symbol"""
        def symbol_exit_callback(exit_price, reason):
            if self.logger:
                self.logger.info(f"Symbol {symbol} trade exit: {reason} at {exit_price:.2f}")
            else:
                print(f"Symbol {symbol} trade exit: {reason} at {exit_price:.2f}")
            
            # Clear active symbol when trade exits
            if self.active_symbol == symbol:
                self.active_symbol = None
            
            # Call the main exit callback
            if self.exit_callback:
                self.exit_callback(exit_price, reason, symbol)
        
        return symbol_exit_callback
    
    def _create_symbol_entry_callback(self, symbol):
        """Create entry callback for a specific symbol"""
        def symbol_entry_callback(sweep_trigger):
            if self.logger:
                self.logger.info(f"Symbol {symbol} trade entry trigger: {sweep_trigger}")
            else:
                print(f"Symbol {symbol} trade entry trigger: {sweep_trigger}")
            
            # Set this symbol as active
            self.active_symbol = symbol
            
            # Call the main entry callback
            if self.entry_callback:
                self.entry_callback(sweep_trigger, symbol)
        
        return symbol_entry_callback
    
    def update_15min_candle(self, symbol, price, timestamp):
        """Update 15-minute candle for a specific symbol"""
        if symbol in self.strategies:
            self.strategies[symbol].update_15min_candle(price, timestamp)
    
    def update_1min_candle(self, symbol, price, timestamp):
        """Update 1-minute candle for a specific symbol"""
        if symbol in self.strategies:
            self.strategies[symbol].update_1min_candle(price, timestamp)
    
    def update_1min_candle_with_data(self, symbol, candle_data, timestamp):
        """Update 1-minute candle with complete OHLC data for a specific symbol"""
        if symbol in self.strategies:
            self.strategies[symbol].update_1min_candle_with_data(candle_data, timestamp)
    
    def check_sweep_conditions(self, symbol):
        """Check sweep conditions for a specific symbol"""
        if symbol not in self.strategies:
            return None
        
        strategy = self.strategies[symbol]
        if strategy.current_1min_candle:
            return strategy.check_sweep_conditions(strategy.current_1min_candle)
        return None
    
    def is_any_symbol_in_trade(self):
        """Check if any symbol is currently in a trade"""
        return any(strategy.in_trade for strategy in self.strategies.values())
    
    def get_active_symbol(self):
        """Get the symbol that is currently being traded"""
        return self.active_symbol
    
    def get_strategy_status(self, symbol=None):
        """Get strategy status for a specific symbol or all symbols"""
        if symbol:
            if symbol in self.strategies:
                return self.strategies[symbol].get_strategy_status()
            return None
        else:
            return {sym: strategy.get_strategy_status() for sym, strategy in self.strategies.items()}
    
    def set_initial_15min_candle(self, symbol, candle):
        """Set initial 15-minute candle for a specific symbol"""
        if symbol in self.strategies:
            self.strategies[symbol].set_initial_15min_candle(candle)
    
    def reset_sweep_detection(self, symbol=None):
        """Reset sweep detection for a specific symbol or all symbols"""
        if symbol:
            if symbol in self.strategies:
                self.strategies[symbol].reset_sweep_detection()
        else:
            for strategy in self.strategies.values():
                strategy.reset_sweep_detection()
    
    def get_all_pending_triggers(self):
        """Get all pending triggers from all symbols"""
        triggers = []
        for symbol, strategy in self.strategies.items():
            if strategy.current_1min_candle:
                trigger = strategy.check_sweep_conditions(strategy.current_1min_candle)
                if trigger:
                    trigger['symbol'] = symbol
                    triggers.append(trigger)
        return triggers
    
    def select_best_trigger(self, triggers):
        """Select the best trigger when multiple symbols have triggers"""
        if not triggers:
            return None
        
        if len(triggers) == 1:
            return triggers[0]
        
        # Selection criteria: prioritize IMPS over CISD, then by entry price (lower is better)
        def trigger_priority(trigger):
            type_priority = 0 if trigger.get('type') == 'bullish' else 1  # IMPS first
            entry_price = trigger.get('entry', float('inf'))
            return (type_priority, entry_price)
        
        best_trigger = min(triggers, key=trigger_priority)
        
        if self.logger:
            self.logger.info(f"Selected best trigger from {len(triggers)} options: {best_trigger['symbol']} - {best_trigger.get('type', 'UNKNOWN')}")
        else:
            print(f"Selected best trigger from {len(triggers)} options: {best_trigger['symbol']} - {best_trigger.get('type', 'UNKNOWN')}")
        
        return best_trigger
