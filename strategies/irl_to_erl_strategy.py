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
                 logger = None, exit_callback=None, entry_callback=None):
        super().__init__(tick_size, swing_look_back, logger, exit_callback, entry_callback)
        
        self.symbol = symbol
        self.initialized = False
        
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
        
        # Debug logging
        if self.logger:
            self.logger.debug(f"IRLtoERL: Processing 1m candle for {self.symbol} at {candle_1m.timestamp.strftime('%H:%M:%S')}")
            bullish_fvgs = self.liquidity_tracker.get_bullish_fvgs()
            bullish_ifvgs = self.liquidity_tracker.get_bullish_ifvgs()
            self.logger.debug(f"IRLtoERL: Found {len(bullish_fvgs)} bullish FVGs and {len(bullish_ifvgs)} bullish IFVGs")
            
            # Debug: Show FVG details if any exist
            if bullish_fvgs:
                for i, fvg in enumerate(bullish_fvgs):
                    self.logger.debug(f"IRLtoERL: Active FVG {i+1}: {fvg['lower']:.2f} - {fvg['upper']:.2f} ({fvg['timeframe']})")
            if bullish_ifvgs:
                for i, ifvg in enumerate(bullish_ifvgs):
                    self.logger.debug(f"IRLtoERL: Active IFVG {i+1}: {ifvg['lower']:.2f} - {ifvg['upper']:.2f} ({ifvg['timeframe']})")


        self.update_1min_candle_with_data(candle_data, candle_1m.timestamp)

        # Check for sting detection on every 1m candle
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
        
        # Store the candle for FVG detection (need at least 3 candles)
        if not hasattr(self, 'five_min_candles'):
            self.five_min_candles = []
        self.five_min_candles.append(candle_5m)
        
        # Keep only last 50 candles for memory efficiency
        if len(self.five_min_candles) > 50:
            self.five_min_candles = self.five_min_candles[-50:]
        
        # Process FVGs/IFVGs if we have enough candles
        if len(self.five_min_candles) >= 3:
            self.liquidity_tracker._process_candles_for_fvgs(self.five_min_candles, '5min', self.symbol)
            self.liquidity_tracker._process_candles_for_implied_fvgs(self.five_min_candles, '5min', self.symbol)
            self.liquidity_tracker._process_candles_for_previous_highs_lows(self.five_min_candles, '5min', self.symbol)
        
        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle_5m)
    
    # 15m candle updates removed - only 5m and 1m timeframes supported

    def _check_sting_detection(self, candle_1m: Candle):
        """
        Check if 1m candle stings into any bullish FVG/IFVG
        Sting condition: 1m candle low <= FVG/IFVG upper price
        """
        # Get all active bullish FVGs and IFVGs for this symbol only
        bullish_fvgs = self.liquidity_tracker.get_bullish_fvgs(symbol=self.symbol)
        bullish_ifvgs = self.liquidity_tracker.get_bullish_ifvgs(symbol=self.symbol)

        # Debug logging
        if self.logger:
            self.logger.info(f"🔍 IRLtoERL: Checking sting detection for {self.symbol}")
            self.logger.info(f"   Found {len(bullish_fvgs)} bullish FVGs, {len(bullish_ifvgs)} bullish IFVGs")
            self.logger.info(f"   1m candle low: {candle_1m.low:.2f}")

            # Log FVG details
            for i, fvg in enumerate(bullish_fvgs):
                self.logger.info(f"   FVG {i+1}: {fvg['lower']:.2f} - {fvg['upper']:.2f} ({fvg['timeframe']})")

            # Log IFVG details
            for i, ifvg in enumerate(bullish_ifvgs):
                self.logger.info(f"   IFVG {i+1}: {ifvg['lower']:.2f} - {ifvg['upper']:.2f} ({ifvg['timeframe']})")

        # Check against bullish FVGs - candle stings INTO the FVG
        for fvg in bullish_fvgs:
            # Sting condition: candle low is within the FVG range (stings into the FVG)
            if fvg['lower'] <= candle_1m.low <= fvg['upper']:
                # Only detect new stings (not already detected for this FVG)
                if not self.sting_detected or self.stung_fvg != fvg:
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

        # Check against bullish IFVGs - candle stings INTO the IFVG
        for ifvg in bullish_ifvgs:
            # Sting condition: candle low is within the IFVG range (stings into the IFVG)
            if ifvg['lower'] <= candle_1m.low <= ifvg['upper']:
                # Only detect new stings (not already detected for this IFVG)
                if not self.sting_detected or self.stung_fvg != ifvg:
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
            # Look for IMPS (1-minute bullish FVG) - IRLtoERL specific
            imps_fvg = self._detect_irl_to_erl_fvg()
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

                self.enter_trade(imps_fvg['entry'], imps_fvg['stop_loss'], imps_fvg['target'])
                # Enter trade for IMPS
                if self.entry_callback:
                    self.entry_callback(imps_fvg)
                return imps_fvg

            # Look for CISD (passing open of bear candles) - IRLtoERL specific
            cisd_trigger = self._detect_irl_to_erl_cisd()
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
                self.enter_trade(cisd_trigger['entry'], cisd_trigger['stop_loss'], cisd_trigger['target'])
                # Enter trade for CISD
                if self.entry_callback:
                    self.entry_callback(cisd_trigger)
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

    def _detect_irl_to_erl_fvg(self):
        """Detect 1-minute bullish FVG for IRLtoERL strategy (no trade execution)"""
        if not hasattr(self, 'current_1min_candle') or not self.current_1min_candle:
            return None
        
        # For IRLtoERL, we need at least 3 recent 1-minute candles
        # This is a simplified version that doesn't interfere with parent logic
        if len(self.one_min_candles) < 3:
            return None
        
        # Get the last 3 1-minute candles
        c1, c2, c3 = list(self.one_min_candles)[-3:]
        
        # Check for bullish FVG (c3.low > c1.high)
        if c3.low > c1.high:
            gap_size = c3.low - c1.high
            entry = c3.close
            stop_loss = c1.high  # Lower bound of FVG
            risk = entry - stop_loss
            target = entry + (2 * risk)  # 1:2 RR for IRLtoERL
            
            return {
                'type': 'bullish',
                'gap_size': gap_size,
                'entry': entry,
                'stop_loss': stop_loss,
                'target': target,
                'symbol': self.symbol,
                'candles': [c1, c2, c3]
            }
        
        return None
    
    def _detect_irl_to_erl_cisd(self):
        """Detect CISD for IRLtoERL strategy (no trade execution)"""
        if not hasattr(self, 'current_1min_candle') or not self.current_1min_candle:
            return None
        
        current_price = self.current_1min_candle.close
        
        # Look for bear candles in recent history
        bear_candles = []
        for candle in list(self.one_min_candles)[-10:]:  # Check last 10 candles
            if candle.close < candle.open:  # Bear candle
                bear_candles.append(candle)
        
        if not bear_candles:
            return None
        
        # Check if current price is above any bear candle open
        for bear_candle in bear_candles:
            if current_price > bear_candle.open:
                # Find the lowest low among all bear candles
                lowest_bear_low = min([candle.low for candle in bear_candles])
                
                risk = current_price - lowest_bear_low
                target = current_price + (2 * risk)  # 1:2 RR for IRLtoERL
                
                return {
                    'type': 'CISD',
                    'entry': current_price,
                    'stop_loss': lowest_bear_low,
                    'target': target,
                    'symbol': self.symbol,
                    'bear_candle': bear_candle,
                    'lowest_bear_low': lowest_bear_low
                }
        
        return None

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
