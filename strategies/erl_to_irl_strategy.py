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
    
    def __init__(self, symbol: str, tick_size: float, swing_look_back=2, logger=None, exit_callback=None, entry_callback=None):
        super().__init__(tick_size, swing_look_back, logger, exit_callback, entry_callback)
        self.symbol = symbol
        self.tick_size = tick_size
        self.swing_look_back = swing_look_back
        #self.logger = logger
        
        # Debug logging
        if self.logger:
            self.logger.info(f"ERL_to_IRL Strategy initialized with symbol: {self.symbol}")
        
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
        Initialize the strategy with historical data
        
        Args:
            symbol: Trading symbol
            historical_data: Dictionary with '5min' and '1min' candle lists
        """
        if self.logger:
            self.logger.info(f"Initializing ERL to IRL strategy for {symbol}")
        
        # Convert Candle objects to lists for liquidity tracker
        candles_5min = historical_data.get('5min', [])
        candles_1min = historical_data.get('1min', [])
        
        if not candles_5min or not candles_1min:
            if self.logger:
                self.logger.error("Missing historical data for strategy initialization")
            return False
        
        # Process historical data to identify liquidity zones
        self.liquidity_tracker.add_historical_data(candles_5min, symbol)
        
        # Set initial sweep targets from the most recent 5m lows
        self._set_initial_sweep_targets(candles_5min)
        
        self.initialized = True
        
        if self.logger:
            summary = self.liquidity_tracker.get_liquidity_summary()
            self.logger.info(f"Strategy initialized with {summary['total_zones']} active liquidity zones")
            #self.logger.info(f"✅ ERL to IRL strategy initialized for {self.symbol}")
        
        return True
    
    def _set_initial_sweep_targets(self, candles_5min: List[Candle]):
        """Set initial sweep targets from recent lows"""
        if candles_5min:
            # Set 5m low as target for 1m sweeps
            recent_5m_low = candles_5min[-1].low
            self.sweep_low_5m = recent_5m_low
            
            if self.logger:
                self.logger.info(f"Set initial 5m sweep target: {recent_5m_low:.2f}")
    
    def update_price(self, price: float, symbol: str = None):
        """Update strategy with current price (for live trading)"""
        if not self.initialized:
            return
        
        # For live trading, we would create a 1m candle from the price
        # This is a simplified implementation
        current_time = datetime.now()
        current_candle = Candle(current_time, price, price, price, price)
        self.update_1m_candle(current_candle)
    
    def update_1m_candle(self, candle_1m: Candle):
        """
        Update strategy with new 1-minute candle
        
        Args:
            candle_1m: The 1-minute candle
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
    
    # 15m candle updates removed - only 5m and 1m timeframes supported

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
