"""
Implied Fair Value Gap (IFVG) Detection
Converts PineScript IFVG logic to Python for liquidity-based trading strategy
"""

from typing import List, Dict, Optional, Tuple, Sequence
import numpy as np
from models.candle import Candle


class ImpliedFVGDetector:
    """Detects Bullish and Bearish Implied Fair Value Gaps"""
    
    def __init__(self, logger=None):
        self.logger = logger
    
    def _body_high(self, o: float, c: float) -> float:
        """Helper function to get body high"""
        return max(o, c)
    
    def _body_low(self, o: float, c: float) -> float:
        """Helper function to get body low"""
        return min(o, c)
    
    def _body_size(self, o: float, c: float) -> float:
        """Helper function to get body size"""
        return abs(c - o)
    
    def detect_bullish_implied_fvg(self, candles: List[Candle], index: int) -> bool:
        """
        Detect Bullish Implied Fair Value Gap at given index
        
        Using correct variable mapping:
        A = candles[index - 2] (oldest)
        B = candles[index - 1] (middle) 
        C = candles[index] (newest)
        
        Returns True if bars [index-2, index-1, index] form a Bullish IMPLIED FVG
        """
        if index < 2 or index >= len(candles):
            return False
        
        # A=index-2, B=index-1, C=index
        A = candles[index - 2]  # Oldest candle
        B = candles[index - 1]  # Middle candle
        C = candles[index]      # Newest candle
        
        oA, hA, lA, cA = A.open, A.high, A.low, A.close
        oB, hB, lB, cB = B.open, B.high, B.low, B.close
        oC, hC, lC, cC = C.open, C.high, C.low, C.close
        
        maxA, minA = self._body_high(oA, cA), self._body_low(oA, cA)
        maxC, minC = self._body_high(oC, cC), self._body_low(oC, cC)
        
        return (
            # 1: C makes higher high than A
            (hC > hA) and
            # 2: A's low is below C's low
            (lA < lC) and
            # 3: Overlap between C's low and A's high
            (lC <= hA) and
            # 4: Upper wick of A > half its body
            (hA - maxA > (maxA - minA) / 2.0) and
            # 5: Lower wick of C > half its body
            (minC - lC > (maxC - minC) / 2.0) and
            # 6: Rising sequence
            (lC > lB) and
            # 7: Midpoint separation
            ((hA + maxA) / 2.0 < (minC + lC) / 2.0) and
            # 8: C makes higher high vs B
            (hC > hB) and
            # 9: B is bullish
            (cB > oB)
        )
    
    def detect_bearish_implied_fvg(self, candles: List[Candle], index: int) -> bool:
        """
        Detect Bearish Implied Fair Value Gap at given index
        
        Using correct variable mapping:
        A = candles[index - 2] (oldest)
        B = candles[index - 1] (middle) 
        C = candles[index] (newest)
        
        Returns True if bars [index-2, index-1, index] form a Bearish IMPLIED FVG
        """
        if index < 2 or index >= len(candles):
            return False
        
        # A=index-2, B=index-1, C=index
        A = candles[index - 2]  # Oldest candle
        B = candles[index - 1]  # Middle candle
        C = candles[index]      # Newest candle
        
        oA, hA, lA, cA = A.open, A.high, A.low, A.close
        oB, hB, lB, cB = B.open, B.high, B.low, B.close
        oC, hC, lC, cC = C.open, C.high, C.low, C.close
        
        maxA, minA = self._body_high(oA, cA), self._body_low(oA, cA)
        maxC, minC = self._body_high(oC, cC), self._body_low(oC, cC)
        
        return (
            # 1: C makes lower low than A
            (lC < lA) and
            # 2: A's high is above C's high
            (hA > hC) and
            # 3: Overlap between C's high and A's low
            (hC >= lA) and
            # 4: Lower wick of A > half its body
            (minA - lA > (maxA - minA) / 2.0) and
            # 5: Upper wick of C > half its body
            (hC - maxC > (maxC - minC) / 2.0) and
            # 6: Falling sequence
            (hC < hB) and
            # 7: Midpoint separation
            ((minA + lA) / 2.0 > (hC + maxC) / 2.0) and
            # 8: C makes lower low vs B
            (lC < lB) and
            # 9: B is bearish
            (cB < oB)
        )
    
    def scan_candles_for_implied_fvgs(self, candles: List[Candle], symbol: str = "Unknown") -> Dict[str, List[Dict]]:
        """
        Scan all candles for Implied FVGs and return them organized by type
        
        Returns:
            {
                'bullish': [{'index': int, 'candle': Candle, 'midpoint': float, 'timestamp': datetime}],
                'bearish': [{'index': int, 'candle': Candle, 'midpoint': float, 'timestamp': datetime}]
            }
        """
        bullish_ifvgs = []
        bearish_ifvgs = []
        
        # Scan from index 2 to len-1 (need at least 3 candles, and index 2 is the first valid position)
        for i in range(2, len(candles)):
            if self.detect_bullish_implied_fvg(candles, i):
                candle = candles[i-2]  # The oldest candle (C)

                price_upper = candles[i].close - (candles[i].close - candles[i].low) * 0.5
                price_lower = candles[i-2].close + (candles[i-2].high - candles[i-2].close) * 0.5
                # Calculate midpoint (target) - for bullish IFVG, use the lower wick area
                midpoint = (price_upper +  price_lower) / 2
                
                bullish_ifvgs.append({
                    'index': i-2,
                    'candle': candle,
                    'price_high': price_upper,
                    'price_low': price_lower,
                    'midpoint': midpoint,
                    'timestamp': candle.timestamp,
                    'type': 'bullish_ifvg'
                })
                
                if self.logger:
                    self.logger.debug(f"Bullish IFVG detected at index {i-2} for {symbol}: {candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - Midpoint: {midpoint:.2f}")
            
            if self.detect_bearish_implied_fvg(candles, i):
                candle = candles[i-2]  # The oldest candle (C)

                price_upper = candles[i-2].close - (candles[i-2].close - candles[i-2].low) * 0.5
                price_lower = candles[i].close + (candles[i ].high - candles[i].close) * 0.5
                # Calculate midpoint (target) - for bullish IFVG, use the lower wick area
                midpoint = (price_upper + price_lower) / 2
                
                bearish_ifvgs.append({
                    'index': i-2,
                    'candle': candle,
                    'price_high': price_upper,
                    'price_low': price_lower,
                    'midpoint': midpoint,
                    'timestamp': candle.timestamp,
                    'type': 'bearish_ifvg'
                })
                
                if self.logger:
                    self.logger.debug(f"Bearish IFVG detected at index {i-2} for {symbol}: {candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - Midpoint: {midpoint:.2f}")
        
        return {
            'bullish': bullish_ifvgs,
            'bearish': bearish_ifvgs
        }
    
    def find_nearest_implied_fvg(self, ifvgs: List[Dict], price: float, direction: str = 'above') -> Optional[Dict]:
        """
        Find the nearest Implied FVG to a given price
        
        Args:
            ifvgs: List of IFVG dictionaries
            price: Current price
            direction: 'above' to find IFVG above price, 'below' to find below price
        
        Returns:
            Nearest IFVG dictionary or None
        """
        if not ifvgs:
            return None
        
        valid_ifvgs = []
        for ifvg in ifvgs:
            ifvg_price = ifvg['midpoint']
            if direction == 'above' and ifvg_price > price:
                valid_ifvgs.append(ifvg)
            elif direction == 'below' and ifvg_price < price:
                valid_ifvgs.append(ifvg)
        
        if not valid_ifvgs:
            return None
        
        # Find the nearest one
        nearest = min(valid_ifvgs, key=lambda x: abs(x['midpoint'] - price))
        return nearest
