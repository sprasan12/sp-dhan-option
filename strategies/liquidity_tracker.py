"""
Liquidity Tracker for ERL to IRL Trading Strategy
Manages FVGs, Implied FVGs, and previous highs/lows for liquidity-based trading
"""

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
        
        # Sorted price lists for efficient lookup
        self._bullish_fvg_prices = []
        self._bearish_fvg_prices = []
        self._bullish_ifvg_prices = []
        self._bearish_ifvg_prices = []
        self._previous_high_prices = []
        self._previous_low_prices = []
    
    def add_historical_data(self, candles_5min: List[Candle], candles_15min: List[Candle], symbol: str = "Unknown"):
        """
        Process historical data to identify and store all liquidity zones
        
        Args:
            candles_5min: List of 5-minute candles
            candles_15min: List of 15-minute candles
            symbol: Trading symbol name for logging
        """
        if self.logger:
            self.logger.info(f"Processing historical data for {symbol}: {len(candles_5min)} 5min candles, {len(candles_15min)} 15min candles")
        
        # Process 5-minute candles
        self._process_candles_for_fvgs(candles_5min, "5min", symbol)
        self._process_candles_for_implied_fvgs(candles_5min, "5min", symbol)
        self._process_candles_for_previous_highs_lows(candles_5min, "5min", symbol)
        self._process_candles_for_swing_lows(candles_5min, "5min", symbol)
        self._process_candles_for_swing_highs(candles_5min, "5min", symbol)
        
        # Process 15-minute candles
        self._process_candles_for_fvgs(candles_15min, "15min", symbol)
        self._process_candles_for_implied_fvgs(candles_15min, "15min", symbol)
        self._process_candles_for_previous_highs_lows(candles_15min, "15min", symbol)
        self._process_candles_for_swing_lows(candles_15min, "15min", symbol)
        self._process_candles_for_swing_highs(candles_15min, "15min", symbol)
        
        # Sort all price lists for efficient lookup
        self._sort_price_lists()
        
        if self.logger:
            self.logger.info(f"Liquidity zones identified:")
            self.logger.info(f"  Bullish FVGs: {len(self.bullish_fvgs)}")
            self.logger.info(f"  Bearish FVGs: {len(self.bearish_fvgs)}")
            self.logger.info(f"  Bullish IFVGs: {len(self.bullish_ifvgs)}")
            self.logger.info(f"  Bearish IFVGs: {len(self.bearish_ifvgs)}")
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
                    midpoint=midpoint
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
                    midpoint=midpoint
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
                midpoint=ifvg['midpoint']
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
                midpoint=ifvg['midpoint']
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
            timeframe: Filter by timeframe ('5min' or '15min') or None for all
        
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
            timeframe: Filter by timeframe ('5min' or '15min') or None for all
        
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
            if not zone.mitigated and zone.timestamp < current_candle.timestamp:
                if current_candle.low <= zone.midpoint <= current_candle.high:
                    zone.mitigated = True
                    zone.mitigation_timestamp = current_candle.timestamp
                    mitigated_count += 1
                    
                    if self.logger:
                        self.logger.debug(f"Bullish {zone.zone_type} mitigated at {current_candle.timestamp.strftime('%H:%M:%S')} - Price: {zone.midpoint:.2f}")
        
        # Check bearish FVGs/IFVGs (mitigated if current candle touches their midpoint)
        for zone in self.bearish_fvgs + self.bearish_ifvgs:
            if not zone.mitigated and zone.timestamp < current_candle.timestamp:
                if current_candle.low <= zone.midpoint <= current_candle.high:
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
            'total_active_zones': len([z for z in self.bullish_fvgs + self.bearish_fvgs + self.bullish_ifvgs + self.bearish_ifvgs if not z.mitigated])
        }
