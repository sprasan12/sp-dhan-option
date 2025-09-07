"""
IRL to ERL Strategy - Internal Range Liquidity to External Range Liquidity
This strategy looks for 1m candles that "sting" into bullish FVGs/IFVGs and then trade on CISD/IMPS
"""

from typing import Dict, Optional, List
from models.candle import Candle
from strategies.candle_strategy import CandleStrategy
from strategies.liquidity_tracker import LiquidityTracker
import logging


class IRLToERLStrategy(CandleStrategy):
    """
    IRL to ERL Strategy: Trade when 1m candle stings into bullish FVGs/IFVGs
    and then CISD/IMPS is triggered
    """
    
    def __init__(self, symbol: str, tick_size: float = 0.05, swing_look_back: int = 2, 
                 logger: logging.Logger = None, exit_callback=None, entry_callback=None):
        super().__init__(tick_size, swing_look_back, logger, exit_callback, entry_callback)
        
        self.symbol = symbol
        self.initialized = False
        
        # Initialize liquidity tracker for FVG/IFVG management
        self.liquidity_tracker = LiquidityTracker(logger)
        
        # IRL to ERL specific state
        self.sting_detected = False
        self.stung_fvg = None  # The FVG/IFVG that was stung
        self.sting_target_upper = None  # Upper price of the stung FVG/IFVG
        
        if self.logger:
            self.logger.info(f"IRL to ERL Strategy initialized for {symbol}")
    
    def set_callbacks(self, entry_callback=None, exit_callback=None):
        """Set entry and exit callbacks"""
        self.entry_callback = entry_callback
        self.exit_callback = exit_callback
    
    def initialize_with_historical_data(self, five_min_candles: List[Candle], 
                                      fifteen_min_candles: List[Candle]):
        """Initialize strategy with historical data"""
        if self.logger:
            self.logger.info(f"Initializing IRL to ERL strategy for {self.symbol}")
            self.logger.info(f"Processing historical data for {self.symbol}: {len(five_min_candles)} 5min candles, {len(fifteen_min_candles)} 15min candles")
        
        # Process historical 5-minute candles to detect FVGs/IFVGs
        for candle in five_min_candles:
            self.liquidity_tracker.process_candle(candle, '5min')
        
        # Process historical 15-minute candles to detect FVGs/IFVGs
        for candle in fifteen_min_candles:
            self.liquidity_tracker.process_candle(candle, '15min')
        
        # Set initial 15-minute candle if available
        if fifteen_min_candles:
            self.set_initial_15min_candle(fifteen_min_candles[-1])
        
        self.initialized = True
        
        if self.logger:
            summary = self.liquidity_tracker.get_liquidity_summary()
            self.logger.info(f"Strategy initialized with {summary['total_zones']} active liquidity zones")
            self.logger.info(f"✅ IRL to ERL strategy initialized for {self.symbol}")
    
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

        self.update_1min_candle_with_data(candle_data, candle_1m.timestamp)
        
        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle_1m)
        
        # Check for sting detection if not already detected
        if not self.sting_detected:
            self._check_sting_detection(candle_1m)
        
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
        
        # Process 5m candle to detect new FVGs/IFVGs
        self.liquidity_tracker.process_candle(candle_5m, '5min')
        
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
        
        # Process 15m candle to detect new FVGs/IFVGs
        self.liquidity_tracker.process_candle(candle_15m, '15min')
        
        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle_15m)
    
    def _check_sting_detection(self, candle_1m: Candle):
        """
        Check if 1m candle stings into any bullish FVG/IFVG
        Sting condition: 1m candle low <= FVG/IFVG upper price
        """
        # Get all active bullish FVGs and IFVGs
        bullish_fvgs = self.liquidity_tracker.get_bullish_fvgs()
        bullish_ifvgs = self.liquidity_tracker.get_bullish_ifvgs()
        
        # Check against bullish FVGs
        for fvg in bullish_fvgs:
            if candle_1m.low <= fvg['upper']:
                self.sting_detected = True
                self.stung_fvg = fvg
                self.sting_target_upper = fvg['upper']
                
                if self.logger:
                    self.logger.info(f"🎯 STING DETECTED!")
                    self.logger.info(f"   Symbol: {self.symbol}")
                    self.logger.info(f"   Candle Time: {candle_1m.timestamp.strftime('%H:%M:%S')}")
                    self.logger.info(f"   1-Min Candle Low: {candle_1m.low:.2f}")
                    self.logger.info(f"   FVG Upper: {fvg['upper']:.2f}")
                    self.logger.info(f"   FVG Lower: {fvg['lower']:.2f}")
                    self.logger.info(f"   FVG Timeframe: {fvg['timeframe']}")
                    self.logger.info(f"   🔍 Looking for CISD/IMPS...")
                else:
                    print(f"🎯 STING DETECTED!")
                    print(f"   Symbol: {self.symbol}")
                    print(f"   Candle Time: {candle_1m.timestamp.strftime('%H:%M:%S')}")
                    print(f"   1-Min Candle Low: {candle_1m.low:.2f}")
                    print(f"   FVG Upper: {fvg['upper']:.2f}")
                    print(f"   FVG Lower: {fvg['lower']:.2f}")
                    print(f"   FVG Timeframe: {fvg['timeframe']}")
                    print(f"   🔍 Looking for CISD/IMPS...")
                return
        
        # Check against bullish IFVGs
        for ifvg in bullish_ifvgs:
            if candle_1m.low <= ifvg['upper']:
                self.sting_detected = True
                self.stung_fvg = ifvg
                self.sting_target_upper = ifvg['upper']
                
                if self.logger:
                    self.logger.info(f"🎯 STING DETECTED!")
                    self.logger.info(f"   Symbol: {self.symbol}")
                    self.logger.info(f"   Candle Time: {candle_1m.timestamp.strftime('%H:%M:%S')}")
                    self.logger.info(f"   1-Min Candle Low: {candle_1m.low:.2f}")
                    self.logger.info(f"   IFVG Upper: {ifvg['upper']:.2f}")
                    self.logger.info(f"   IFVG Lower: {ifvg['lower']:.2f}")
                    self.logger.info(f"   IFVG Timeframe: {ifvg['timeframe']}")
                    self.logger.info(f"   🔍 Looking for CISD/IMPS...")
                else:
                    print(f"🎯 STING DETECTED!")
                    print(f"   Symbol: {self.symbol}")
                    print(f"   Candle Time: {candle_1m.timestamp.strftime('%H:%M:%S')}")
                    print(f"   1-Min Candle Low: {candle_1m.low:.2f}")
                    print(f"   IFVG Upper: {ifvg['upper']:.2f}")
                    print(f"   IFVG Lower: {ifvg['lower']:.2f}")
                    print(f"   IFVG Timeframe: {ifvg['timeframe']}")
                    print(f"   🔍 Looking for CISD/IMPS...")
                return
    
    def _check_cisd_imps_triggers(self, candle_1m: Candle):
        """
        Check for CISD/IMPS triggers after sting detection
        """
        if self.logger:
            self.logger.info(f"🔍 Checking for CISD/IMPS - Close: {candle_1m.close:.2f} >= Sting Target: {self.sting_target_upper:.2f}")
        else:
            print(f"🔍 Checking for CISD/IMPS - Close: {candle_1m.close:.2f} >= Sting Target: {self.sting_target_upper:.2f}")
        
        # Check if close is above the sting target (recovery condition)
        if candle_1m.close >= self.sting_target_upper:
            # Look for IMPS (1-minute bullish FVG)
            imps_fvg = self.detect_1min_bullish_fvg()
            if imps_fvg:
                if self.logger:
                    self.logger.info(f"✅ IMPS (1-Min Bullish FVG) Found!")
                    self.logger.info(f"   Symbol: {self.symbol}")
                    self.logger.info(f"   Candle Time: {candle_1m.timestamp.strftime('%H:%M:%S')}")
                    self.logger.info(f"   Entry: {imps_fvg['entry']:.2f}")
                    self.logger.info(f"   Stop Loss: {imps_fvg['stop_loss']:.2f}")
                    self.logger.info(f"   Target: {imps_fvg['target']:.2f}")
                else:
                    print(f"✅ IMPS (1-Min Bullish FVG) Found!")
                    print(f"   Symbol: {self.symbol}")
                    print(f"   Candle Time: {candle_1m.timestamp.strftime('%H:%M:%S')}")
                    print(f"   Entry: {imps_fvg['entry']:.2f}")
                    print(f"   Stop Loss: {imps_fvg['stop_loss']:.2f}")
                    print(f"   Target: {imps_fvg['target']:.2f}")
                
                # Override stop loss with FVG low
                imps_fvg['stop_loss'] = self.stung_fvg['lower']
                # Calculate target (1:2 RR or nearest swing high)
                risk = imps_fvg['entry'] - imps_fvg['stop_loss']
                target_1_2 = imps_fvg['entry'] + (2 * risk)
                swing_high_target = self._get_nearest_swing_high(imps_fvg['entry'])
                imps_fvg['target'] = max(target_1_2, swing_high_target)
                
                return imps_fvg
            
            # Look for CISD (passing open of bear candles)
            cisd_trigger = self.detect_cisd()
            if cisd_trigger:
                if self.logger:
                    self.logger.info(f"✅ CISD (Bear Candle Open) Found!")
                    self.logger.info(f"   Symbol: {self.symbol}")
                    self.logger.info(f"   Candle Time: {candle_1m.timestamp.strftime('%H:%M:%S')}")
                    self.logger.info(f"   Entry: {cisd_trigger['entry']:.2f}")
                    self.logger.info(f"   Stop Loss: {cisd_trigger['stop_loss']:.2f}")
                    self.logger.info(f"   Target: {cisd_trigger['target']:.2f}")
                else:
                    print(f"✅ CISD (Bear Candle Open) Found!")
                    print(f"   Symbol: {self.symbol}")
                    print(f"   Candle Time: {candle_1m.timestamp.strftime('%H:%M:%S')}")
                    print(f"   Entry: {cisd_trigger['entry']:.2f}")
                    print(f"   Stop Loss: {cisd_trigger['stop_loss']:.2f}")
                    print(f"   Target: {cisd_trigger['target']:.2f}")
                
                # Override stop loss with FVG low
                cisd_trigger['stop_loss'] = self.stung_fvg['lower']
                # Calculate target (1:2 RR or nearest swing high)
                risk = cisd_trigger['entry'] - cisd_trigger['stop_loss']
                target_1_2 = cisd_trigger['entry'] + (2 * risk)
                swing_high_target = self._get_nearest_swing_high(cisd_trigger['entry'])
                cisd_trigger['target'] = max(target_1_2, swing_high_target)
                
                return cisd_trigger
        else:
            if self.logger:
                self.logger.info(f"   ⏳ Waiting for close >= sting target ({self.sting_target_upper:.2f}). Current close: {candle_1m.close:.2f}")
            else:
                print(f"   ⏳ Waiting for close >= sting target ({self.sting_target_upper:.2f}). Current close: {candle_1m.close:.2f}")
        
        return None
    
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
    
    def reset_sting_detection(self):
        """Reset sting detection after entering trade"""
        self.sting_detected = False
        self.stung_fvg = None
        self.sting_target_upper = None
    
    def update_price(self, price: float, timestamp):
        """Update strategy with current price (for live mode)"""
        if not self.initialized:
            return
        
        # Create a simple candle from the price (live mode limitation)
        current_candle = Candle(
            timestamp=timestamp,
            open_price=price,
            high=price,
            low=price,
            close=price
        )
        
        # Update with the candle
        self.update_1m_candle(current_candle)
    
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