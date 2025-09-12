"""
IRL to ERL Strategy - Internal Range Liquidity to External Range Liquidity
This strategy looks for 1m candles that "sting" into bullish FVGs/IFVGs and then trade on CISD/IMPS
"""

from typing import Dict, Optional, List
from models.candle import Candle
from strategies.candle_strategy import CandleStrategy
from strategies.liquidity_tracker import LiquidityTracker
import logging


class IRLToERLStrategy():
    """
    IRL to ERL Strategy: Trade when 1m candle stings into bullish FVGs/IFVGs
    and then CISD/IMPS is triggered
    """
    
    def __init__(self, symbol: str, tick_size: float = 0.05, swing_look_back: int = 2, 
                 logger = None, exit_callback=None, entry_callback=None):
        #super().__init__(tick_size, swing_look_back, logger, exit_callback, entry_callback)
        
        self.symbol = symbol
        self.initialized = False
        self.logger = logger
        # Debug logging
        if self.logger:
            self.logger.info(f"IRL_to_ERL Strategy initialized with symbol: {self.symbol}")
            self.logger.info(f"IRL_to_ERL Strategy logger type: {type(self.logger)}")
        else:
            print(f"IRL_to_ERL Strategy initialized with symbol: {self.symbol} (NO LOGGER)")
        
        # Initialize liquidity tracker for FVG/IFVG management
        self.liquidity_tracker = LiquidityTracker(logger)
        
        # Initialize sting detection state
        self.sting_detected = False
        self.stung_fvg = None
        
        if self.logger:
            self.logger.info(f"IRL to ERL Strategy initialized for {symbol}")
    
    def set_callbacks(self, entry_callback=None, exit_callback=None):
        """Set entry and exit callbacks"""
        self.entry_callback = entry_callback
        self.exit_callback = exit_callback
    
    def initialize_with_historical_data(self,  symbol: str, historical_data: Dict[str, List[Candle]]):
        """Initialize strategy with historical data"""
        if self.logger:
            self.logger.info(f"Initializing IRL to ERL strategy for {symbol}")
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
        self._set_initial_sting_targets(candles_5min)

        self.initialized = True

        if self.logger:
            summary = self.liquidity_tracker.get_liquidity_summary()
            self.logger.info(f"Strategy initialized with {summary['total_zones']} active liquidity zones")
            #self.logger.info(f"✅ IRL to ERL strategy initialized for {self.symbol}")

        return True

    def _set_initial_sting_targets(self, candles_5min: List[Candle]):
        """Set initial sweep targets from recent lows"""
        if candles_5min:
            # Set 5m low as target for 1m sweeps
            recent_5m_low = candles_5min[-1].low
            self.sweep_low_5m = recent_5m_low

            if self.logger:
                self.logger.info(f"Set initial 5m sweep target: {recent_5m_low:.2f}")

    def update_1m_candle(self, candle_1m: Candle):
        """
        Update strategy with new 1-minute candle
        
        Args:
            candle_1m: The 1-minute candle
        """
        if not self.initialized:
            if self.logger:
                self.logger.debug(f"IRL_to_ERL strategy not initialized yet for {self.symbol}")
            return
        
        # Debug logging
        if self.logger:
            self.logger.debug(f"IRL_to_ERL: Processing 1m candle for {self.symbol} at {candle_1m.timestamp.strftime('%H:%M:%S')}")
        
        # IRLtoERL strategy should NOT call parent's sweep detection logic
        # We only need to store the candle for our own sting detection
        self.current_1min_candle = candle_1m

        candle_data = {"open": candle_1m.open, "high": candle_1m.high,
                       "low": candle_1m.low, "close": candle_1m.close}

        # Call parent class method to handle candle updates and trade logic
        
        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle_1m)

        # Check for sting detection on every 1m candle
        self.c(candle_1m)
        
        # If sting detected, check for CISD/IMPS triggers
        if self.sting_detected:
            self._check_cisd_imps_triggers(candle_1m)
    
    def update_5m_candle(self, candle_5m: Candle):
        """
        Update strategy with new 5-minute candle
        
        Args:
            candle_5m: The 5-minute candle
        """
        if not self.initialized:
            return

        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle_5m)

    def _get_nearest_swing_high(self, entry_price: float) -> float:
        """
        Get the nearest swing high above entry price
        """
        # Get all swing highs from liquidity tracker
        swing_highs = self.liquidity_tracker.get_swing_highs()
        
        # Find the nearest swing high above entry price
        nearest_high = None
        min_distance = float('inf')
        
        for high in swing_highs:
            if high > entry_price:
                distance = high - entry_price
                if distance < min_distance:
                    min_distance = distance
                    nearest_high = high
        
        return nearest_high if nearest_high else entry_price + (2 * (entry_price - self.stung_fvg['lower']))

    def get_strategy_status(self) -> Dict:
        """Get current strategy status"""
        return {
            'initialized': self.initialized,
            'in_trade': self.in_trade,
            'trade_type': getattr(self, 'trade_type', None),
            'entry_price': self.entry_price,
            'stop_loss': self.current_stop_loss,
            'target': self.current_target,
            'sting_detected': self.sting_detected,
            'stung_fvg': self.stung_fvg,
            'sting_target_upper': self.sting_target_upper,
            'liquidity_summary': self.liquidity_tracker.get_liquidity_summary()
        }
