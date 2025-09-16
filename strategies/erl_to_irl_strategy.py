"""
ERL to IRL Trading Strategy
Trades price movement from External Range Liquidity (ERL) to Internal Range Liquidity (IRL)
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from models.candle import Candle
from strategies.candle_data import CandleData
from strategies.liquidity_tracker import LiquidityTracker, LiquidityZone
from strategies.implied_fvg_detector import ImpliedFVGDetector
from utils.market_utils import round_to_tick
from strategies.candle_strategy import CandleStrategy

class ERLToIRLStrategy():
    """Main strategy class for ERL to IRL trading"""
    
    def __init__(self, symbol: str, tick_size: float, swing_look_back=2, logger=None, exit_callback=None, entry_callback=None, candle_data=None):
        #super().__init__(tick_size, swing_look_back, logger, exit_callback, entry_callback)
        self.symbol = symbol
        self.tick_size = tick_size
        self.swing_look_back = swing_look_back
        self.logger = logger
        
        # Debug logging
        if self.logger:
            self.logger.info(f"ERL_to_IRL Strategy initialized with symbol: {self.symbol}")
        
        # Initialize components
        self.liquidity_tracker = LiquidityTracker(logger)
        self.ifvg_detector = ImpliedFVGDetector(logger)
        
        # Strategy state
        self.initialized = False

        self.sweep_detected = False
        self.candle_data = candle_data if candle_data else {}

    
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
        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle_1m)

        if self.candle_data.check_for_sweep(candle_1m.timestamp):
            if self.logger:
                self.logger.info(f"Sweep conditions met at {candle_1m.timestamp}")
            cisd_trigger = self.candle_data.detect_cisd()
            if cisd_trigger:
                if self.logger:
                    self.logger.info(f"✅ CISD  Found!")
                    self.logger.info(f"   Symbol: {self.symbol}")
                    self.logger.info(f"   Candle Time: {candle_1m.timestamp.strftime('%H:%M:%S')}")
                    self.logger.info(f"   Entry: {cisd_trigger['entry']:.2f}")
                    self.logger.info(f"   Stop Loss: {cisd_trigger['stop_loss']:.2f}")
                    self.logger.info(f"   Target: {cisd_trigger['target']:.2f}")
                
                # Set strategy state before calling callback
                self.in_trade = True
                self.entry_price = cisd_trigger['entry']
                self.current_stop_loss = cisd_trigger['stop_loss']
                self.current_target = cisd_trigger['target']
                self.trade_type = 'CISD'
                
                # Execute trade entry callback
                if self.entry_callback:
                    self.entry_callback(self.symbol, "ERLtoIRL", cisd_trigger)
                return cisd_trigger

        # Now need to check for sweeps and trade entries/exits through candle data helper methods

    
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
            'in_trade': getattr(self, 'in_trade', False),
            'trade_type': getattr(self, 'trade_type', None),
            'entry_price': getattr(self, 'entry_price', None),
            'stop_loss': getattr(self, 'current_stop_loss', None),
            'target': getattr(self, 'current_target', None),
            'liquidity_summary': self.liquidity_tracker.get_liquidity_summary(),
            'sweep_status': {
                'sweep_detected': getattr(self, 'sweep_detected', False),
                'sweep_low_5m': getattr(self, 'sweep_low_5m', None)
            }
        }
