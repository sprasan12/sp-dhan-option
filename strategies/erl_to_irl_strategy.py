"""
ERL to IRL Trading Strategy
Trades price movement from External Range Liquidity (ERL) to Internal Range Liquidity (IRL)
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from models.candle import Candle
from strategies.liquidity_tracker import LiquidityTracker, LiquidityZone
from strategies.implied_fvg_detector import ImpliedFVGDetector
from utils.market_utils import round_to_tick
from strategies.candle_strategy import CandleStrategy

class ERLToIRLStrategy(CandleStrategy):
    """Main strategy class for ERL to IRL trading"""
    
    def __init__(self, tick_size: float, swing_look_back=2, logger=None, exit_callback=None, entry_callback=None):
        super().__init__(tick_size, swing_look_back, logger, exit_callback, entry_callback)
        self.tick_size = tick_size
        self.swing_look_back = swing_look_back
        #self.logger = logger
        
        # Initialize components
        self.liquidity_tracker = LiquidityTracker(logger)
        self.ifvg_detector = ImpliedFVGDetector(logger)
        
        # Strategy state
        self.initialized = False

    
    def set_callbacks(self, entry_callback=None, exit_callback=None):
        """Set callback functions for trade entry and exit"""
        self.entry_callback = entry_callback
        self.exit_callback = exit_callback
    
    def initialize_with_historical_data(self, symbol: str, historical_data: Dict[str, List[Candle]]):
        """
        Initialize the strategy with 10 days of historical data
        
        Args:
            symbol: Trading symbol
            historical_data: Dictionary with '5min' and '15min' candle lists
        """
        if self.logger:
            self.logger.info(f"Initializing ERL to IRL strategy for {symbol}")
        
        # Convert Candle objects to lists for liquidity tracker
        candles_5min = historical_data.get('5min', [])
        candles_15min = historical_data.get('15min', [])
        
        if not candles_5min or not candles_15min:
            if self.logger:
                self.logger.error("Missing historical data for strategy initialization")
            return False
        
        # Process historical data to identify liquidity zones
        self.liquidity_tracker.add_historical_data(candles_5min, candles_15min, symbol)
        
        # Set initial sweep targets from the most recent 5m and 15m lows
        self._set_initial_sweep_targets(candles_5min, candles_15min)
        
        self.initialized = True
        
        if self.logger:
            summary = self.liquidity_tracker.get_liquidity_summary()
            self.logger.info(f"Strategy initialized with {summary['total_active_zones']} active liquidity zones")
        
        return True
    
    def _set_initial_sweep_targets(self, candles_5min: List[Candle], candles_15min: List[Candle]):
        """Set initial sweep targets from recent lows"""
        if candles_5min:
            # Set 5m low as target for 1m sweeps
            #recent_5m_low = min(candle.low for candle in candles_5min[-10:])  # Last 10 candles
            recent_5m_low = candles_5min[-1].low

            
            if self.logger:
                self.logger.info(f"Set initial 5m sweep target: {recent_5m_low:.2f}")
        
        if candles_15min:
            # Set 15m low as target for 1m sweeps
            recent_15m_low = candles_15min[-1].low

            
            if self.logger:
                self.logger.info(f"Set initial 15m sweep target: {recent_15m_low:.2f}")
    
    def update_price(self, price: float, symbol: str = None):
        """Update strategy with current price (for live trading)"""
        if not self.initialized:
            return
        
        # For live trading, we would create a 1m candle from the price
        # This is a simplified implementation
        current_time = datetime.now()
        current_candle = Candle(current_time, price, price, price, price)
        self.update_1m_candle(current_candle)
    
    def update_1m_candle(self, candle_1m: Candle, candle_15m: Candle = None):
        """
        Update strategy with new 1-minute candle
        
        Args:
            candle_1m: The 1-minute candle
            candle_15m: The current 15-minute candle (if available)
        """
        if not self.initialized:
            return
        candle_data = {"open": candle_1m.open, "high": candle_1m.high,
                       "low": candle_1m.low, "close": candle_1m.close}

        # Call parent class method to handle candle updates and trade logic

        self.update_1min_candle_with_data(candle_data, candle_1m.timestamp)
        
        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle_1m)
    
    def update_5m_candle(self, candle_5m: Candle):
        """
        Update strategy with new 5-minute candle
        
        Args:
            candle_5m: The 5-minute candle
        """
        if not self.initialized:
            return
        
        # Call parent class method to handle 5m candle updates
        # Note: CandleStrategy doesn't have update_5min_candle_with_data, so we'll skip this for now
        # The 5m candle processing is handled internally by the parent class
        
        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle_5m)
    
    def update_15m_candle(self, candle_15m: Candle):
        """
        Update strategy with new 15-minute candle
        
        Args:
            candle_15m: The 15-minute candle
        """
        if not self.initialized:
            return
        
        # Call parent class method to handle 15m candle updates and set sweep targets
        self.update_15min_candle(candle_15m.close, candle_15m.timestamp)
        
        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle_15m)
    
    def update_price(self, price: float, timestamp: datetime):
        """
        Update strategy with current price
        
        Args:
            price: Current price
            timestamp: Current timestamp
        """
        if not self.initialized:
            return
        
        # This method can be used for price-based updates
        # For now, it's a placeholder for future enhancements
        pass

    def set_callbacks(self, entry_callback=None, exit_callback=None):
        """Set entry and exit callbacks"""
        self.entry_callback = entry_callback
        self.exit_callback = exit_callback
    
    def get_strategy_status(self) -> Dict:
        """Get current strategy status"""
        return {
            'initialized': self.initialized,
            'in_trade': self.in_trade,
            'trade_type': getattr(self, 'trade_type', None),
            'entry_price': self.entry_price,
            'stop_loss': self.current_stop_loss,
            'target': self.current_target,
            'liquidity_summary': self.liquidity_tracker.get_liquidity_summary(),
            'sweep_status': {
                'waiting_for_sweep': self.waiting_for_sweep,
                'sweep_detected': self.sweep_detected,
                'sweep_low': self.sweep_low,
                'recovery_low': self.recovery_low
            }
        }
