"""
Liquidity Tracker for ERL to IRL Trading Strategy
Manages FVGs, Implied FVGs, and previous highs/lows for liquidity-based trading
"""
from collections import deque
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from models.candle import Candle
from strategies.implied_fvg_detector import ImpliedFVGDetector
import bisect


class LiquidityZone:
    """Represents a liquidity zone (FVG, IFVG, or previous high/low)"""
    
    def __init__(self, zone_type: str, price_high: float, price_low: float,timestamp: datetime,
                 candle: Candle = None, midpoint: float = None, mitigated: bool = False, symbol: str = "Unknown"):
        self.zone_type = zone_type  # 'bullish_fvg', 'bearish_fvg', 'bullish_ifvg', 'bearish_ifvg', 'previous_high', 'previous_low'
        self.price_high = price_high  # The high price level for this zone
        self.price_low = price_low    # The low price level for this zone
        self.midpoint = midpoint or ((price_high + price_low)/2)  # Target price (midpoint for FVGs/IFVGs)
        self.timestamp = timestamp
        self.candle = candle
        self.mitigated = mitigated
        self.mitigation_timestamp = None
        self.symbol = symbol
    
    def __repr__(self):
        return (f"LiquidityZone({self.zone_type}, {self.symbol},  {self.price_high:.2f},   {self.price_low:.2f},"
                f"{self.timestamp.strftime('%H:%M:%S')}, mitigated={self.mitigated})")


class LiquidityTracker:
    """Tracks and manages all liquidity zones for ERL to IRL trading strategy"""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.ifvg_detector = ImpliedFVGDetector(logger)
        
        # Storage for different types of liquidity zones
        self.bullish_fvgs = []  # List of LiquidityZone objects
        self.bearish_fvgs = []
        self.bullish_ifvgs = []
        self.bearish_ifvgs = []
        self.previous_highs = []  # For ERL targets
        self.previous_lows = []   # For ERL targets
        self.swing_highs = []  # For ERL targets
        self.swing_lows = []  # For ERL targets
        self.swing_look_back = 1
        # Candle storage - only 5m and 1m
        self.lt_five_min_candles = deque(maxlen=30000)  # Store 5-minute candles
        self.lt_one_min_candles = deque(maxlen=1500)  # Store 1-minute candles for swing low detection
        
        # Sorted price lists for efficient lookup
        self._bullish_fvg_prices = []
        self._bearish_fvg_prices = []
        self._bullish_ifvg_prices = []
        self._bearish_ifvg_prices = []
        self._previous_high_prices = []
        self._previous_low_prices = []
    
    def add_historical_data(self, candles_5min: List[Candle], symbol: str = "Unknown"):
        """
        Process historical data to identify and store all liquidity zones with 2-pass mitigation check
        
        Args:
            candles_5min: List of 5-minute candles
            symbol: Trading symbol name for logging
        """
        if self.logger:
            self.logger.info(f"Processing historical data for {symbol}: {len(candles_5min)} 5min candles")
        for i in range(len(candles_5min)):
            self.lt_five_min_candles.append(candles_5min[i])
        # 1st Pass: Process 5-minute candles to detect FVGs/IFVGs
        self._process_candles_for_fvgs(candles_5min, "5min", symbol)
        self._process_candles_for_implied_fvgs(candles_5min, "5min", symbol)
        self._process_candles_for_previous_highs_lows(candles_5min, "5min", symbol)
        self._process_candles_for_swing_lows(candles_5min, "5min", symbol)
        self._process_candles_for_swing_highs(candles_5min, "5min", symbol)
        
        # 2nd Pass: Check for mitigation in 5m timeframe
        if len(candles_5min) >= 3:
            self._check_historical_mitigation(candles_5min, "5min", symbol)
        
        # Sort all price lists for efficient lookup
        self._sort_price_lists()
        
        if self.logger:
            summary = self.get_liquidity_summary()
            self.logger.info(f"Liquidity zones identified after 2-pass processing:")
            self.logger.info(f"  Active Bullish FVGs: {summary['bullish_fvgs']}")
            self.logger.info(f"  Active Bearish FVGs: {summary['bearish_fvgs']}")
            self.logger.info(f"  Active Bullish IFVGs: {summary['bullish_ifvgs']}")
            self.logger.info(f"  Active Bearish IFVGs: {summary['bearish_ifvgs']}")
            self.logger.info(f"  Previous Highs: {len(self.previous_highs)}")
            self.logger.info(f"  Previous Lows: {len(self.previous_lows)}")
            for zone in self.swing_highs:
                self.logger.info(f"  Swing High: {zone}")
            for zone in self.swing_lows:
                self.logger.info(f"  Swing Low: {zone}")

    
    def _process_candles_for_fvgs(self, candles: List[Candle], timeframe: str, symbol: str = "Unknown"):
        """Process candles to detect and store FVGs"""
        for i in range(len(candles) - 2):
            # Candle A (oldest): candles[i]
            # Candle B (middle): candles[i + 1] 
            # Candle C (newest): candles[i + 2]
            
            # Check for bullish FVG (C.low > A.high)
            if candles[i + 2].low > candles[i].high:
                gap_size = candles[i + 2].low - candles[i].high
                midpoint = candles[i].high + (gap_size / 2)
                
                zone = LiquidityZone(
                    zone_type=f"bullish_fvg_{timeframe}",
                    price_high=candles[i + 2].low,
                    price_low=candles[i].high,
                    timestamp=candles[i].timestamp,
                    candle=candles[i],
                    midpoint=midpoint,
                    symbol=symbol
                )
                self.bullish_fvgs.append(zone)
                
                if self.logger:
                    self.logger.debug(f"Bullish FVG ({timeframe}) detected for {symbol}: {candles[i].timestamp.strftime('%Y-%m-%d %H:%M:%S')} - "
                                      f"Lower:{candles[i].high:.2f}, Upper:{candles[i + 2].low:.2f}, Gap: {gap_size:.2f}, Midpoint: {midpoint:.2f}")
            
            # Check for bearish FVG (A.high > C.low)
            elif candles[i+2].high < candles[i].low:
                gap_size = candles[i].low - candles[i + 2].high
                midpoint = candles[i].low - (gap_size / 2)
                
                zone = LiquidityZone(
                    zone_type=f"bearish_fvg_{timeframe}",
                    price_high=candles[i].low,
                    price_low=candles[i+2].high,
                    timestamp=candles[i].timestamp,
                    candle=candles[i],
                    midpoint=midpoint,
                    symbol=symbol
                )
                self.bearish_fvgs.append(zone)
                
                if self.logger:
                    self.logger.debug(f"Bearish FVG ({timeframe}) detected for {symbol}: {candles[i].timestamp.strftime('%Y-%m-%d %H:%M:%S')} - "
                                      f"Upper:{candles[i].low:.2f},Lower:{candles[i+2].high:.2f},  Gap: {gap_size:.2f}, Midpoint: {midpoint:.2f}")
    
    def _process_candles_for_implied_fvgs(self, candles: List[Candle], timeframe: str, symbol: str = "Unknown"):
        """Process candles to detect and store Implied FVGs"""
        ifvgs = self.ifvg_detector.scan_candles_for_implied_fvgs(candles, symbol)
        
        for ifvg in ifvgs['bullish']:
            zone = LiquidityZone(
                zone_type=f"bullish_ifvg_{timeframe}",
                price_high=ifvg['price_high'],
                price_low=ifvg['price_low'],
                timestamp=ifvg['timestamp'],
                candle=ifvg['candle'],
                midpoint=ifvg['midpoint'],
                symbol=symbol
            )
            self.bullish_ifvgs.append(zone)
            
            if self.logger:
                self.logger.debug(f"Bullish IFVG ({timeframe}) detected for {symbol}: {ifvg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} "
                                  f"Upper:{ifvg['price_high']:.2f},Lower:{ifvg['price_low']:.2f}, Midpoint: {ifvg['midpoint']:.2f}")
        
        for ifvg in ifvgs['bearish']:
            zone = LiquidityZone(
                zone_type=f"bearish_ifvg_{timeframe}",
                price_high=ifvg['price_high'],
                price_low=ifvg['price_low'],
                timestamp=ifvg['timestamp'],
                candle=ifvg['candle'],
                midpoint=ifvg['midpoint'],
                symbol=symbol
            )
            self.bearish_ifvgs.append(zone)
            
            if self.logger:
                self.logger.debug(f"Bearish IFVG ({timeframe}) detected for {symbol}: {ifvg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} "
                                  f"Upper:{ifvg['price_high']:.2f},Lower:{ifvg['price_low']:.2f}, Midpoint: {ifvg['midpoint']:.2f}")
    
    def _process_candles_for_previous_highs_lows(self, candles: List[Candle], timeframe: str, symbol: str = "Unknown"):
        """Process candles to store previous highs and lows for ERL targets"""
        for candle in candles:
            # Store previous highs (for bearish ERL targets)
            zone = LiquidityZone(
                zone_type=f"previous_high_{timeframe}",
                price_high=candle.high,
                price_low=candle.high-0.05, # Small buffer below high
                timestamp=candle.timestamp,
                candle=candle,
                midpoint=candle.high
            )
            self.previous_highs.append(zone)
            
            # Store previous lows (for bullish ERL targets)
            zone = LiquidityZone(
                zone_type=f"previous_low_{timeframe}",
                price_high=candle.low+0.05, # Small buffer above low
                price_low=candle.low,
                timestamp=candle.timestamp,
                candle=candle,
                midpoint=candle.low
            )
            self.previous_lows.append(zone)

    def _process_candles_for_swing_lows(self, candles: List[Candle], timeframe: str, symbol: str = "Unknown"):
        """Process candles to store previous highs and lows for ERL targets"""
        for i in range(len(candles)):
            # Store previous lows (for bullish ERL targets)
            if self._check_swing_low(candles, i):
                candle = candles[i]
                zone = LiquidityZone(
                    zone_type=f"swing_low_{timeframe}",
                    price_high=candle.low,
                    price_low=candle.low,
                    timestamp=candle.timestamp,
                    candle=candle,
                    midpoint=candle.low,
                    symbol=symbol
                )
                self.swing_lows.append(zone)

    def _check_swing_low(self, candles: List[Candle], candle_index):
        """Detect if a candle at given index is a swing low"""
        if len(candles) < (2 * self.swing_look_back + 1):
            return False

        current_candle = candles[candle_index]
        current_low = current_candle.low

        # Check if current low is lower than previous N candles
        for i in range(1, self.swing_look_back + 1):
            if candle_index - i < 0:
                return False
            prev_candle = candles[candle_index - i]
            if current_low >= prev_candle.low:
                return False

        # Check if current low is lower than next N candles
        for i in range(1, self.swing_look_back + 1):
            if candle_index + i >= len(candles):
                return False
            next_candle = candles[candle_index + i]
            if current_low >= next_candle.low:
                return False

        return True

    def _process_candles_for_swing_highs(self, candles: List[Candle], timeframe: str, symbol: str = "Unknown"):
        """Process candles to store previous highs and lows for ERL targets"""
        for i in range(len(candles)):
            # Store previous lows (for bullish ERL targets)
            if self._check_swing_high(candles, i):
                candle = candles[i]
                zone = LiquidityZone(
                    zone_type=f"swing_high_{timeframe}",
                    price_high=candle.high,
                    price_low=candle.high,
                    timestamp=candle.timestamp,
                    candle=candle,
                    midpoint=candle.high,
                    symbol=symbol
                )
                self.swing_highs.append(zone)

    def _check_swing_high(self, candles: List[Candle], candle_index):
        """Detect if a candle at given index is a swing low"""
        if len(candles) < (2 * self.swing_look_back + 1):
            return False

        current_candle = candles[candle_index]
        current_high = current_candle.high

        # Check if current low is lower than previous N candles
        for i in range(1, self.swing_look_back + 1):
            if candle_index - i < 0:
                return False
            prev_candle = candles[candle_index - i]
            if current_high <= prev_candle.high:
                return False

        # Check if current low is lower than next N candles
        for i in range(1, self.swing_look_back + 1):
            if candle_index + i >= len(candles):
                return False
            next_candle = candles[candle_index + i]
            if current_high <= next_candle.high:
                return False

        return True
    
    def _sort_price_lists(self):
        """Sort all price lists for efficient binary search lookup"""
        self._bullish_fvg_prices = sorted([zone.midpoint for zone in self.bullish_fvgs])
        self._bearish_fvg_prices = sorted([zone.midpoint for zone in self.bearish_fvgs])
        self._bullish_ifvg_prices = sorted([zone.midpoint for zone in self.bullish_ifvgs])
        self._bearish_ifvg_prices = sorted([zone.midpoint for zone in self.bearish_ifvgs])
        self._previous_high_prices = sorted([zone.midpoint for zone in self.previous_highs])
        self._previous_low_prices = sorted([zone.midpoint for zone in self.previous_lows])
    
    def find_nearest_bearish_target(self, price: float, timeframe: str = None) -> Optional[LiquidityZone]:
        """
        Find the nearest bearish FVG/IFVG above the given price (for bullish trades)
        
        Args:
            price: Current price
            timeframe: Filter by timeframe ('5min') or None for all
        
        Returns:
            Nearest bearish liquidity zone above price
        """
        bearish_zones = []
        
        # Collect bearish FVGs
        for zone in self.bearish_fvgs:
            if timeframe is None or timeframe in zone.zone_type:
                if zone.midpoint > price and not zone.mitigated:
                    bearish_zones.append(zone)
        
        # Collect bearish IFVGs
        for zone in self.bearish_ifvgs:
            if timeframe is None or timeframe in zone.zone_type:
                if zone.midpoint > price and not zone.mitigated:
                    bearish_zones.append(zone)
        
        if not bearish_zones:
            return None
        
        # Find the nearest one
        nearest = min(bearish_zones, key=lambda x: abs(x.midpoint - price))
        return nearest
    
    def find_nearest_bullish_target(self, price: float, timeframe: str = None) -> Optional[LiquidityZone]:
        """
        Find the nearest bullish FVG/IFVG below the given price (for bearish trades)
        
        Args:
            price: Current price
            timeframe: Filter by timeframe ('5min') or None for all
        
        Returns:
            Nearest bullish liquidity zone below price
        """
        bullish_zones = []
        
        # Collect bullish FVGs
        for zone in self.bullish_fvgs:
            if timeframe is None or timeframe in zone.zone_type:
                if zone.midpoint < price and not zone.mitigated:
                    bullish_zones.append(zone)
        
        # Collect bullish IFVGs
        for zone in self.bullish_ifvgs:
            if timeframe is None or timeframe in zone.zone_type:
                if zone.midpoint < price and not zone.mitigated:
                    bullish_zones.append(zone)
        
        if not bullish_zones:
            return None
        
        # Find the nearest one
        nearest = min(bullish_zones, key=lambda x: abs(x.midpoint - price))
        return nearest
    
    def _check_historical_mitigation(self, candles: List[Candle], timeframe: str, symbol: str = "Unknown"):
        """
        Check for mitigation of FVGs/IFVGs within the same timeframe during historical processing
        
        Args:
            candles: List of candles in the timeframe
            timeframe: Timeframe string (5min)
            symbol: Symbol name for logging
        """
        if not candles or len(candles) < 3:
            return
        
        mitigated_count = 0
        
        # Get all FVGs and IFVGs for this timeframe
        timeframe_bullish_fvgs = [zone for zone in self.bullish_fvgs + self.bullish_ifvgs if timeframe in zone.zone_type]
        timeframe_bearish_fvgs = [zone for zone in self.bearish_fvgs + self.bearish_ifvgs if timeframe in zone.zone_type]
        
        if self.logger:
            self.logger.debug(f"Checking historical mitigation for {symbol} {timeframe}: {len(timeframe_bullish_fvgs)} Bullish I/FVGs, {len(timeframe_bearish_fvgs)} BearishI/FVGs")

        # Check each candle against all FVGs/IFVGs that were created before it
        for candle in candles:
            for zone in timeframe_bullish_fvgs:
                # Only check zones that were created before this candle
                if not zone.mitigated and zone.timestamp < candle.timestamp - timedelta(minutes=10):
                    # Check if candle touches the midpoint (mitigation condition)
                    if candle.low <= zone.midpoint <= candle.high:
                        zone.mitigated = True
                        zone.mitigation_timestamp = candle.timestamp
                        mitigated_count += 1
                        
                        if self.logger:
                            self.logger.debug(f"Historical {zone.zone_type} mitigated at {candle.timestamp.strftime('%H:%M:%S')} - Price: {zone.midpoint:.2f}")
            for zone in timeframe_bearish_fvgs:
                # Only check zones that were created before this candle
                if not zone.mitigated and zone.timestamp < candle.timestamp - timedelta(minutes=10):
                    # Check if candle touches the midpoint (mitigation condition)
                    if candle.high >= zone.midpoint >= candle.low:
                        zone.mitigated = True
                        zone.mitigation_timestamp = candle.timestamp
                        mitigated_count += 1

                        if self.logger:
                            self.logger.debug(
                                f"Historical {zone.zone_type} mitigated at {candle.timestamp.strftime('%H:%M:%S')} - Price: {zone.midpoint:.2f}")
        if mitigated_count > 0 and self.logger:
            self.logger.info(f"Marked {mitigated_count} {timeframe} liquidity zones as mitigated during historical processing for {symbol}")
    
    def check_and_mark_mitigation(self, current_candle: Candle):
        """
        Check if any FVGs/IFVGs have been mitigated by the current candle
        and mark them as mitigated
        
        Args:
            current_candle: The current candle to check against
        """
        mitigated_count = 0
        
        # Check bullish FVGs/IFVGs (mitigated if current candle touches their midpoint)
        for zone in self.bullish_fvgs + self.bullish_ifvgs:
            if not zone.mitigated and zone.timestamp < current_candle.timestamp - timedelta(minutes=10):
                if current_candle.low <= zone.midpoint <= current_candle.high:
                    zone.mitigated = True
                    zone.mitigation_timestamp = current_candle.timestamp
                    mitigated_count += 1
                    
                    if self.logger:
                        self.logger.debug(f"Bullish {zone.zone_type} mitigated at {current_candle.timestamp.strftime('%H:%M:%S')} - Price: {zone.midpoint:.2f}")
        
        # Check bearish FVGs/IFVGs (mitigated if current candle touches their midpoint)
        for zone in self.bearish_fvgs + self.bearish_ifvgs:
            if not zone.mitigated and zone.timestamp < current_candle.timestamp - timedelta(minutes=10):
                if current_candle.high >= zone.midpoint >= current_candle.low:
                    zone.mitigated = True
                    zone.mitigation_timestamp = current_candle.timestamp
                    mitigated_count += 1
                    
                    if self.logger:
                        self.logger.debug(f"Bearish {zone.zone_type} mitigated at {current_candle.timestamp.strftime('%H:%M:%S')} - Price: {zone.midpoint:.2f}")
        
        if mitigated_count > 0 and self.logger:
            self.logger.info(f"Marked {mitigated_count} liquidity zones as mitigated")
    
    def get_liquidity_summary(self) -> Dict:
        """Get a summary of all liquidity zones"""
        return {
            'bullish_fvgs': len([z for z in self.bullish_fvgs if not z.mitigated]),
            'bearish_fvgs': len([z for z in self.bearish_fvgs if not z.mitigated]),
            'bullish_ifvgs': len([z for z in self.bullish_ifvgs if not z.mitigated]),
            'bearish_ifvgs': len([z for z in self.bearish_ifvgs if not z.mitigated]),
            'previous_highs': len(self.previous_highs),
            'previous_lows': len(self.previous_lows),
            'total_zones': len([z for z in self.bullish_fvgs + self.bearish_fvgs + self.bullish_ifvgs + self.bearish_ifvgs if not z.mitigated])
        }
    
    def get_bullish_fvgs(self, symbol: str = None) -> List[Dict]:
        """Get all active bullish FVGs as dictionaries, optionally filtered by symbol"""
        return [
            {
                'upper': zone.price_high,
                'lower': zone.price_low,
                'midpoint': (zone.price_high + zone.price_low) / 2,
                'timestamp': zone.timestamp,
                'timeframe': zone.zone_type.split('_')[1] if '_' in zone.zone_type else 'unknown',
                'symbol': zone.symbol
            }
            for zone in self.bullish_fvgs 
            if not zone.mitigated and (symbol is None or zone.symbol == symbol)
        ]
    
    def get_bullish_ifvgs(self, symbol: str = None) -> List[Dict]:
        """Get all active bullish IFVGs as dictionaries, optionally filtered by symbol"""
        return [
            {
                'upper': zone.price_high,
                'lower': zone.price_low,
                'midpoint': (zone.price_high + zone.price_low) / 2,
                'timestamp': zone.timestamp,
                'timeframe': zone.zone_type.split('_')[1] if '_' in zone.zone_type else 'unknown',
                'symbol': zone.symbol
            }
            for zone in self.bullish_ifvgs 
            if not zone.mitigated and (symbol is None or zone.symbol == symbol)
        ]
    
    def get_swing_highs(self) -> List[float]:
        """Get all swing highs as a list of prices"""
        return self.previous_highs.copy()
    
    def process_candle(self, candle: Candle, timeframe: str, symbol: str = "Unknown"):
        """
        Process a single candle to detect new FVGs/IFVGs/SwingHighs/SwingLows
        Uses the new candle combined with existing candle history for pattern detection
        
        Args:
            candle: The completed candle to process
            timeframe: Timeframe string ('5min')
            symbol: Trading symbol name for logging
        """
        if timeframe == '5min':
            if candle not in self.lt_five_min_candles:
                self.lt_five_min_candles.append(candle)
            # Process for FVGs using new candle + last 2 candles from history
            self._process_single_candle_for_fvgs(candle, timeframe, symbol)
            
            # Process for Implied FVGs using new candle + history
            self._process_single_candle_for_implied_fvgs(candle, timeframe, symbol)
            
            # Process for previous highs/lows (always add new candle's high/low)
            self._process_single_candle_for_previous_highs_lows(candle, timeframe, symbol)
            
            # Process for swing highs/lows using new candle + lookback from history
            self._process_single_candle_for_swing_highs(candle, timeframe, symbol)
            self._process_single_candle_for_swing_lows(candle, timeframe, symbol)
            
            # Sort price lists after adding new zones
            self._sort_price_lists()
            
            if self.logger:
                self.logger.info(f"🕯️ PROCESSED 5-MINUTE CANDLE")
                self.logger.info(f"   Time: {candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"   OHLC: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
                self.logger.info(f"   Symbol: {symbol}")
                
                # Log summary of what was detected
                summary = self.get_liquidity_summary()
                self.logger.info(f"   📊 Liquidity Summary: {summary['total_zones']} active zones")
                if summary['bullish_fvgs'] > 0 or summary['bearish_fvgs'] > 0:
                    self.logger.info(f"      FVGs: {summary['bullish_fvgs']} Bullish, {summary['bearish_fvgs']} Bearish")
                if summary['bullish_ifvgs'] > 0 or summary['bearish_ifvgs'] > 0:
                    self.logger.info(f"      IFVGs: {summary['bullish_ifvgs']} Bullish, {summary['bearish_ifvgs']} Bearish")
                self.logger.info(f"      Previous Highs: {summary['previous_highs']}, Previous Lows: {summary['previous_lows']}")
                self.logger.info(f"   ✅ 5-minute candle processing completed")
        elif timeframe == '1min':
            if candle not in self.lt_one_min_candles:
                self.lt_one_min_candles.append(candle)
            # Process for 1-minute swing lows
            self._process_single_candle_for_1min_swing_lows(candle, symbol)
        # Only 5min and 1min timeframes are supported now
    
    def _process_single_candle_for_fvgs(self, new_candle: Candle, timeframe: str, symbol: str = "Unknown"):
        """
        Process a single new candle for FVG detection using the last 2 candles from history
        
        Args:
            new_candle: The new completed candle
            timeframe: Timeframe string
            symbol: Symbol name for logging
        """
        # Get the last 2 candles from history for FVG pattern detection
        # We need candles in order: [oldest, middle, newest] where newest is the new_candle
        
        # For FVG detection, we need to check if the new candle (C) forms a gap with candle A
        # But we need to get the last 2 candles from our stored history
        
        # Get recent candles from our stored zones (they contain the candle references)
        recent_candles = []

        recent_candles = list(self.lt_five_min_candles)[-3:]  # Get last 3 from deque

        if len(recent_candles) >= 3:
            candle_a = recent_candles[-3]  # Third to last
            candle_b = recent_candles[-2]  # second Last
            candle_c = new_candle          # New candle
            
            # Check for bullish FVG (C.low > A.high)
            if candle_c.low > candle_a.high:
                gap_size = candle_c.low - candle_a.high
                midpoint = candle_a.high + (gap_size / 2)
                
                zone = LiquidityZone(
                    zone_type=f"bullish_fvg_{timeframe}",
                    price_high=candle_c.low,
                    price_low=candle_a.high,
                    timestamp=candle_a.timestamp,
                    candle=candle_a,
                    midpoint=midpoint,
                    symbol=symbol
                )
                self.bullish_fvgs.append(zone)
                
                if self.logger:
                    self.logger.info(f"🟢 BULLISH FVG DETECTED!")
                    self.logger.info(f"   Time: {candle_a.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.logger.info(f"   Lower: {candle_a.high:.2f}, Upper: {candle_c.low:.2f}")
                    self.logger.info(f"   Gap Size: {gap_size:.2f}, Midpoint: {midpoint:.2f}")
                    self.logger.info(f"   Symbol: {symbol}")
            
            # Check for bearish FVG (A.high > C.low)
            elif candle_c.high < candle_a.low:
                gap_size = candle_a.low - candle_c.high
                midpoint = candle_a.low - (gap_size / 2)
                
                zone = LiquidityZone(
                    zone_type=f"bearish_fvg_{timeframe}",
                    price_high=candle_a.low,
                    price_low=candle_c.high,
                    timestamp=candle_a.timestamp,
                    candle=candle_a,
                    midpoint=midpoint,
                    symbol=symbol
                )
                self.bearish_fvgs.append(zone)
                
                if self.logger:
                    self.logger.info(f"🔴 BEARISH FVG DETECTED!")
                    self.logger.info(f"   Time: {candle_a.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.logger.info(f"   Upper: {candle_a.low:.2f}, Lower: {candle_c.high:.2f}")
                    self.logger.info(f"   Gap Size: {gap_size:.2f}, Midpoint: {midpoint:.2f}")
                    self.logger.info(f"   Symbol: {symbol}")
    
    def _process_single_candle_for_implied_fvgs(self, new_candle: Candle, timeframe: str, symbol: str = "Unknown"):
        """
        Process a single new candle for Implied FVG detection
        
        Args:
            new_candle: The new completed candle
            timeframe: Timeframe string
            symbol: Symbol name for logging
        """
        # For IFVG detection, we need to use the ImpliedFVGDetector
        # We need to provide it with a list of candles including the new one
        
        # Get recent candles from history (similar to FVG processing)
        recent_candles = []

        recent_candles = list(self.lt_five_min_candles)[-3:]  # Get last 3 from deque
        
        # Remove duplicates and sort by timestamp
        recent_candles = list(set(recent_candles))
        recent_candles.sort(key=lambda x: x.timestamp)
        
        # Add the new candle
        #recent_candles.append(new_candle)
        
        # Use the existing IFVG detector if we have enough candles
        if len(recent_candles) >= 3:
            ifvgs = self.ifvg_detector.scan_candles_for_implied_fvgs(recent_candles, symbol)
            
            # Only process IFVGs that involve the new candle (to avoid duplicates)
            for ifvg in ifvgs['bullish']:
                if ifvg['candle'] == new_candle or ifvg['timestamp'] == new_candle.timestamp:
                    zone = LiquidityZone(
                        zone_type=f"bullish_ifvg_{timeframe}",
                        price_high=ifvg['price_high'],
                        price_low=ifvg['price_low'],
                        timestamp=ifvg['timestamp'],
                        candle=ifvg['candle'],
                        midpoint=ifvg['midpoint'],
                        symbol=symbol
                    )
                    self.bullish_ifvgs.append(zone)
                    
                    if self.logger:
                        self.logger.info(f"🟢 BULLISH IFVG DETECTED!")
                        self.logger.info(f"   Time: {ifvg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                        self.logger.info(f"   Upper: {ifvg['price_high']:.2f}, Lower: {ifvg['price_low']:.2f}")
                        self.logger.info(f"   Midpoint: {ifvg['midpoint']:.2f}")
                        self.logger.info(f"   Symbol: {symbol}")
            
            for ifvg in ifvgs['bearish']:
                if ifvg['candle'] == new_candle or ifvg['timestamp'] == new_candle.timestamp:
                    zone = LiquidityZone(
                        zone_type=f"bearish_ifvg_{timeframe}",
                        price_high=ifvg['price_high'],
                        price_low=ifvg['price_low'],
                        timestamp=ifvg['timestamp'],
                        candle=ifvg['candle'],
                        midpoint=ifvg['midpoint'],
                        symbol=symbol
                    )
                    self.bearish_ifvgs.append(zone)
                    
                    if self.logger:
                        self.logger.info(f"🔴 BEARISH IFVG DETECTED!")
                        self.logger.info(f"   Time: {ifvg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                        self.logger.info(f"   Upper: {ifvg['price_high']:.2f}, Lower: {ifvg['price_low']:.2f}")
                        self.logger.info(f"   Midpoint: {ifvg['midpoint']:.2f}")
                        self.logger.info(f"   Symbol: {symbol}")
    
    def _process_single_candle_for_previous_highs_lows(self, new_candle: Candle, timeframe: str, symbol: str = "Unknown"):
        """
        Process a single new candle for previous highs/lows (always add new candle's high/low)
        
        Args:
            new_candle: The new completed candle
            timeframe: Timeframe string
            symbol: Symbol name for logging
        """
        # Always add the new candle's high and low as previous high/low zones
        
        # Store previous high (for bearish ERL targets)
        zone = LiquidityZone(
            zone_type=f"previous_high_{timeframe}",
            price_high=new_candle.high,
            price_low=new_candle.high - 0.05,  # Small buffer below high
            timestamp=new_candle.timestamp,
            candle=new_candle,
            midpoint=new_candle.high,
            symbol=symbol
        )
        self.previous_highs.append(zone)
        
        # Store previous low (for bullish ERL targets)
        zone = LiquidityZone(
            zone_type=f"previous_low_{timeframe}",
            price_high=new_candle.low + 0.05,  # Small buffer above low
            price_low=new_candle.low,
            timestamp=new_candle.timestamp,
            candle=new_candle,
            midpoint=new_candle.low,
            symbol=symbol
        )
        self.previous_lows.append(zone)
    
    def _process_single_candle_for_swing_highs(self, new_candle: Candle, timeframe: str, symbol: str = "Unknown"):
        """
        Process a single new candle for swing high detection using lookback from history
        
        Args:
            new_candle: The new completed candle
            timeframe: Timeframe string
            symbol: Symbol name for logging
        """
        # Get recent candles from history for swing detection
        recent_candles = []

        recent_candles = list(self.lt_five_min_candles)[-5:]  # Get last 3 from deque
        
        # Remove duplicates and sort by timestamp
        recent_candles = list(set(recent_candles))
        recent_candles.sort(key=lambda x: x.timestamp)
        
        # Add the new candle
        #recent_candles.append(new_candle)
        
        # Check if the new candle is a swing high
        if len(recent_candles) >= (2 * self.swing_look_back + 1):
            new_candle_index = len(recent_candles) - 1  # New candle is the last one
            
            if self._check_swing_high(recent_candles, new_candle_index):
                zone = LiquidityZone(
                    zone_type=f"swing_high_{timeframe}",
                    price_high=new_candle.high,
                    price_low=new_candle.high,
                    timestamp=new_candle.timestamp,
                    candle=new_candle,
                    midpoint=new_candle.high,
                    symbol=symbol
                )
                self.swing_highs.append(zone)
                
                if self.logger:
                    self.logger.info(f"📈 SWING HIGH DETECTED!")
                    self.logger.info(f"   Time: {new_candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.logger.info(f"   High: {new_candle.high:.2f}")
                    self.logger.info(f"   Symbol: {symbol}")
    
    def _process_single_candle_for_swing_lows(self, new_candle: Candle, timeframe: str, symbol: str = "Unknown"):
        """
        Process a single new candle for swing low detection using lookback from history
        
        Args:
            new_candle: The new completed candle
            timeframe: Timeframe string
            symbol: Symbol name for logging
        """
        # Get recent candles from history for swing detection
        recent_candles = []

        recent_candles = list(self.lt_five_min_candles)[-5:]  # Get last 5 from deque
        
        # Remove duplicates and sort by timestamp
        recent_candles = list(set(recent_candles))
        recent_candles.sort(key=lambda x: x.timestamp)
        
        # Add the new candle
        #recent_candles.append(new_candle)
        
        # Check if the new candle is a swing low
        if len(recent_candles) >= (2 * self.swing_look_back + 1):
            new_candle_index = len(recent_candles) - 1  # New candle is the last one
            
            if self._check_swing_low(recent_candles, new_candle_index):
                zone = LiquidityZone(
                    zone_type=f"swing_low_{timeframe}",
                    price_high=new_candle.low,
                    price_low=new_candle.low,
                    timestamp=new_candle.timestamp,
                    candle=new_candle,
                    midpoint=new_candle.low,
                    symbol=symbol
                )
                self.swing_lows.append(zone)
                
                if self.logger:
                    self.logger.info(f"📉 SWING LOW DETECTED!")
                    self.logger.info(f"   Time: {new_candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.logger.info(f"   Low: {new_candle.low:.2f}")
                    self.logger.info(f"   Symbol: {symbol}")
    
    def _process_single_candle_for_1min_swing_lows(self, new_candle: Candle, symbol: str = "Unknown"):
        """
        Process a single 1-minute candle for swing low detection
        
        Args:
            new_candle: The new completed 1-minute candle
            symbol: Symbol name for logging
        """
        # Get recent 1-minute candles for swing detection (need at least 3 candles)
        recent_candles = list(self.lt_one_min_candles)[-5:]  # Get last 5 from deque
        
        # Remove duplicates and sort by timestamp
        recent_candles = list(set(recent_candles))
        recent_candles.sort(key=lambda x: x.timestamp)
        
        # Check if we have enough candles for swing detection (need at least 3)
        if len(recent_candles) >= 3:
            # Evaluate the PREVIOUS candle as the swing candidate (middle candle),
            # since the new candle serves as the 'next' in the three-candle pattern
            candidate_index = len(recent_candles) - 2
            
            # Check if the previous candle is a swing low (lower than previous and next candle)
            if self._check_1min_swing_low(recent_candles, candidate_index):
                candidate_candle = recent_candles[candidate_index]
                zone = LiquidityZone(
                    zone_type="swing_low_1min",
                    price_high=candidate_candle.low,
                    price_low=candidate_candle.low,
                    timestamp=candidate_candle.timestamp,
                    candle=candidate_candle,
                    midpoint=candidate_candle.low,
                    symbol=symbol
                )
                self.swing_lows.append(zone)
                
                if self.logger:
                    self.logger.info(f"📉 1-MIN SWING LOW DETECTED!")
                    self.logger.info(f"   Time: {candidate_candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.logger.info(f"   Low: {candidate_candle.low:.2f}")
                    self.logger.info(f"   Symbol: {symbol}")
    
    def _check_1min_swing_low(self, candles: List[Candle], candle_index):
        """Check if a 1-minute candle at given index is a swing low"""
        if candle_index < 1 or candle_index >= len(candles) - 1:
            return False
        
        current_candle = candles[candle_index]
        prev_candle = candles[candle_index - 1]
        next_candle = candles[candle_index + 1]
        
        # A swing low is when the current candle's low is lower than both previous and next candle's low
        return (current_candle.low < prev_candle.low and 
                current_candle.low < next_candle.low)
