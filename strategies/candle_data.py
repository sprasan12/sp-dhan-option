"""
CandleData - Central candle management and utility methods
Manages 1m and 5m candles, provides utility methods for CISD, IMPS, Sweep, Sting detection
"""

from collections import deque
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from models.candle import Candle
from utils.market_utils import round_to_tick
from utils.timezone_utils import safe_datetime_compare, ensure_timezone_naive


class CandleData:
    """
    Central candle data management class
    Handles 1m and 5m candle storage, updates, and provides utility methods
    Integrates with StrategyManager for trade detection
    """
    
    def __init__(self, tick_size=0.05, logger=None, strategy_manager=None):
        self.tick_size = tick_size
        self.logger = logger
        self.on_5min_candle_complete = None  # Callback for 5-minute candle completion
        
        # Candle storage - only 5m and 1m
        self.five_min_candles = deque(maxlen=300)   # Store 5-minute candles
        self.one_min_candles = deque(maxlen=1500)   # Store 1-minute candles
        
        # Current candles
        self.current_5min_candle = None
        self.current_1min_candle = None
        
        # Time tracking
        self.last_5min_candle_time = None
        self.last_1min_candle_time = None
        
        # Session tracking
        self.session_high = None
        self.session_low = None
        self.session_high_time = None
        self.session_low_time = None

        self.sweep_target = None
        self.sweep_set_time = None
        self.target_swept = False
        self.sweep_target_invalidated = False
        self.two_CR_valid = False
        self.count_five_min_close_below_sweep = 0
        self.deepest_sweep_candle = None # candle that swept max depth into target
        
        # Bear candle tracking for CISD
        self.last_consecutive_bear_candles = deque(maxlen=10)
        
        if self.logger:
            self.logger.info("CandleData initialized")

    
    def set_5min_candle_callback(self, callback):
        """Set callback function for 5-minute candle completion"""
        self.on_5min_candle_complete = callback
    
    def update_1min_candle(self, price, timestamp):

        # Round the price to tick size
        price = round_to_tick(price, self.tick_size)

        # Get the current market time boundary (1-minute intervals starting from 9:15:00)
        current_time = timestamp

        # Check if market is open (after 9:15 AM)
        if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 15):
            return

        # Calculate the current 1-minute period correctly
        # Market opens at 9:15, so first period is 9:15-9:16, second is 9:16-9:17, etc.
        minutes_since_market_open = (current_time.hour - 9) * 60 + (current_time.minute - 15)
        period_number = minutes_since_market_open // 1

        # Calculate the start time of this 1-minute period
        period_start_minutes = period_number * 1

        # Calculate the candle start time
        market_open_time = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
        candle_start_time = market_open_time + timedelta(minutes=period_start_minutes)

        # If this is a new 1-minute candle period, create a new candle
        # Use safe datetime comparison
        timestamp_match = False
        if self.current_1min_candle:
            timestamp_match = safe_datetime_compare(self.current_1min_candle.timestamp, candle_start_time, "eq")

        if not self.current_1min_candle or not timestamp_match:
            completed_candle = None
            if self.current_1min_candle:
                self.last_1min_candle_time = timestamp
                # Update 5-minute candle based on the candle that just completed
                self._update_5min_candle(self.current_1min_candle.close, timestamp)
                # Persist the completed 1m candle and run analysis on it
                self.one_min_candles.append(self.current_1min_candle)
                self._classify_and_analyze_1min_candle(self.current_1min_candle)
                completed_candle = self.current_1min_candle
                if self.sweep_target is None:
                    # check last 5 min candle, if BEAR/Neutral, then last 5min low as sweep target
                    prev_5min_candle = self.five_min_candles[-1] if self.five_min_candles else None
                    if self.logger:
                        self.logger.info(f"🔍 SWEEP TARGET CHECK:")
                        self.logger.info(f"   Current sweep target: {self.sweep_target}")
                        self.logger.info(f"   Previous 5m candle: {'EXISTS' if prev_5min_candle else 'NONE'}")
                        if prev_5min_candle:
                            self.logger.info(f"   Prev 5m candle time: {prev_5min_candle.timestamp.strftime('%H:%M:%S')}")
                            self.logger.info(f"   Prev 5m candle OHLC: O:{prev_5min_candle.open:.2f} H:{prev_5min_candle.high:.2f} L:{prev_5min_candle.low:.2f} C:{prev_5min_candle.close:.2f}")
                    
                    if prev_5min_candle:
                        candle_type = self.get_candle_type(prev_5min_candle)
                        if self.logger:
                            self.logger.info(f"   Prev 5m candle type: {candle_type}")
                        
                        if candle_type in ["BEAR", "NEUTRAL"]:
                            self.sweep_target = prev_5min_candle.low
                            self.sweep_set_time = self.current_1min_candle.timestamp
                            self.target_swept = False
                            self.sweep_target_invalidated = False
                            self.two_CR_valid = True
                            self.count_five_min_close_below_sweep = 0
                            if self.logger:
                                self.logger.info(f"🎯 SWEEP TARGET SET!")
                                self.logger.info(f"   Target Price: {self.sweep_target:.2f}")
                                self.logger.info(f"   Set Time: {self.sweep_set_time.strftime('%H:%M:%S')}")
                                self.logger.info(f"   From 5m Candle: {candle_type} at {prev_5min_candle.timestamp.strftime('%H:%M:%S')}")
                                self.logger.info(f"   Target Swept: {self.target_swept}")
                                self.logger.info(f"   Two CR Valid: {self.two_CR_valid}")
                        else:
                            if self.logger:
                                self.logger.info(f"ℹ️ SWEEP TARGET: Not set - prev 5m candle is {candle_type} (need BEAR/NEUTRAL)")
                    else:
                        if self.logger:
                            self.logger.info(f"ℹ️ SWEEP TARGET: Not set - no previous 5m candle available")

                # Log completed 1m candle
                if self.logger:
                    candle_type = self.get_candle_type(self.current_1min_candle)
                    candle_symbol = self.get_candle_symbol(self.current_1min_candle)
                    body_size = self.current_1min_candle.body_size()
                    total_range = self.current_1min_candle.high - self.current_1min_candle.low
                    body_percentage = (body_size / total_range * 100) if total_range > 0 else 0

                    self.logger.info(f"📊 1-MINUTE CANDLE COMPLETED")
                    self.logger.info(f"   Time: {self.current_1min_candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.logger.info(
                        f"   OHLC: O:{self.current_1min_candle.open:.2f} H:{self.current_1min_candle.high:.2f} L:{self.current_1min_candle.low:.2f} C:{self.current_1min_candle.close:.2f}")
                    self.logger.info(f"   Body: {body_size:.2f} ({body_percentage:.1f}%)")
                    self.logger.info(f"   Type: {candle_type}")
                    self.logger.info(f"   --------------------------------------------------")


            # Create new 1-minute candle for the next period
            self.current_1min_candle = Candle(candle_start_time, price, price, price, price)
            if self.logger:
                self.logger.info(f"🕯️ New 1min candle at {candle_start_time.strftime('%H:%M:%S')} - O:{price:.2f}")
            else:
                print(f"🕯️ New 1min candle at {candle_start_time.strftime('%H:%M:%S')} - O:{price:.2f}")
            self.last_1min_candle_time = candle_start_time
            # Return the completed candle (if any). Strategies should run only on completed candles
            return completed_candle
        else:
            # Update existing 1-minute candle
            self.current_1min_candle.update_price(price)
        return None
    
    def update_1min_candle_with_data(self, candle_data, timestamp):
        """Update 1-minute candle with complete OHLC data and process through strategy manager"""
        timestamp = ensure_timezone_naive(timestamp)
        

        # Create new 1-minute candle
        candle = Candle(
            timestamp=timestamp,
            open_price=candle_data['open'],
            high=candle_data['high'],
            low=candle_data['low'],
            close=candle_data['close']
        )
        # Set new current candle
        self.current_1min_candle = candle
        self.last_1min_candle_time = timestamp
        # Log completed 1m candle
        self._log_1m_completion()

        self.one_min_candles.append(self.current_1min_candle)
        self._classify_and_analyze_1min_candle(self.current_1min_candle)
        if self.sweep_target is None:
            #check last 5 min candle, if BEAR/Neutral, then last 5min low as sweep target
            prev_5min_candle = self.five_min_candles[-1] if self.five_min_candles else None
            if self.logger:
                self.logger.info(f"🔍 SWEEP TARGET CHECK (1m candle completion):")
                self.logger.info(f"   Current sweep target: {self.sweep_target}")
                self.logger.info(f"   Previous 5m candle: {'EXISTS' if prev_5min_candle else 'NONE'}")
                if prev_5min_candle:
                    self.logger.info(f"   Prev 5m candle time: {prev_5min_candle.timestamp.strftime('%H:%M:%S')}")
                    self.logger.info(f"   Prev 5m candle OHLC: O:{prev_5min_candle.open:.2f} H:{prev_5min_candle.high:.2f} L:{prev_5min_candle.low:.2f} C:{prev_5min_candle.close:.2f}")

            if prev_5min_candle:
                candle_type = self.get_candle_type(prev_5min_candle)
                if self.logger:
                    self.logger.info(f"   Prev 5m candle type: {candle_type}")

                if candle_type in ["BEAR", "NEUTRAL"]:
                    self.sweep_target = prev_5min_candle.low
                    self.sweep_set_time = self.current_1min_candle.timestamp
                    self.target_swept = False
                    self.sweep_target_invalidated = False
                    self.two_CR_valid = True
                    self.count_five_min_close_below_sweep = 0
                    if self.logger:
                        self.logger.info(f"🎯 SWEEP TARGET SET (1m completion)!")
                        self.logger.info(f"   Target Price: {self.sweep_target:.2f}")
                        self.logger.info(f"   Set Time: {self.sweep_set_time.strftime('%H:%M:%S')}")
                        self.logger.info(f"   From 5m Candle: {candle_type} at {prev_5min_candle.timestamp.strftime('%H:%M:%S')}")
                        self.logger.info(f"   Target Swept: {self.target_swept}")
                        self.logger.info(f"   Two CR Valid: {self.two_CR_valid}")
                else:
                    if self.logger:
                        self.logger.info(f"ℹ️ SWEEP TARGET: Not set - prev 5m candle is {candle_type} (need BEAR/NEUTRAL)")
            else:
                if self.logger:
                    self.logger.info(f"ℹ️ SWEEP TARGET: Not set - no previous 5m candle available")


        # Update 5-minute candle
        self._update_5min_candle(candle_data['close'], timestamp)

        return None

    def _log_1m_completion(self):
        # Log completed 1m candle
        if self.logger:
            candle_type = self.get_candle_type(self.current_1min_candle)
            candle_symbol = self.get_candle_symbol(self.current_1min_candle)
            body_size = self.current_1min_candle.body_size()
            total_range = self.current_1min_candle.high - self.current_1min_candle.low
            body_percentage = (body_size / total_range * 100) if total_range > 0 else 0

            self.logger.info(f"📊 1-MINUTE CANDLE COMPLETED")
            self.logger.info(f"   Time: {self.current_1min_candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(
                f"   OHLC: O:{self.current_1min_candle.open:.2f} H:{self.current_1min_candle.high:.2f} L:{self.current_1min_candle.low:.2f} C:{self.current_1min_candle.close:.2f}")
            self.logger.info(f"   Body: {body_size:.2f} ({body_percentage:.1f}%)")
            self.logger.info(f"   Type: {candle_type}")
            self.logger.info(f"   --------------------------------------------------")

    def _log_5m_completion(self):
        # Log completed 5m candle
        if self.logger:
            candle_type = self.get_candle_type(self.current_5min_candle)
            candle_symbol = self.get_candle_symbol(self.current_5min_candle)
            body_size = self.current_5min_candle.body_size()
            total_range = self.current_5min_candle.high - self.current_5min_candle.low
            body_percentage = (body_size / total_range * 100) if total_range > 0 else 0

            self.logger.info(f"🕯️ 5-MINUTE CANDLE COMPLETED")
            self.logger.info(f"   Time: {self.current_5min_candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(
                f"   OHLC: O:{self.current_5min_candle.open:.2f} H:{self.current_5min_candle.high:.2f} L:{self.current_5min_candle.low:.2f} C:{self.current_5min_candle.close:.2f}")
            self.logger.info(f"   Body: {body_size:.2f} ({body_percentage:.1f}%)")
            self.logger.info(f"   Type: {candle_type}")
            self.logger.info(f"   --------------------------------------------------")

    def _start_new_5m_candle(self, price, candle_start_time):
        # Start new 5-minute candle with proper OHLC from 1m candle
        if hasattr(self, 'current_1min_candle') and self.current_1min_candle:
            # Use the 1m candle's OHLC data for the 5m candle
            self.current_5min_candle = Candle(
                timestamp=candle_start_time,
                open_price=self.current_1min_candle.open,
                high=self.current_1min_candle.high,
                low=self.current_1min_candle.low,
                close=self.current_1min_candle.close
            )
        else:
            # Fallback to price if no 1m candle available
            self.current_5min_candle = Candle(
                timestamp=candle_start_time,
                open_price=price,
                high=price,
                low=price,
                close=price
            )
        self.last_5min_candle_time = candle_start_time

        # Log new 5m candle start
        if self.logger:
            self.logger.info(f"🆕 5-MINUTE CANDLE STARTED")
            self.logger.info(f"   Time: {candle_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"   Open: {self.current_5min_candle.open:.2f}")

    def _update_5min_candle(self, price, timestamp):
        """Update 5-minute candle - properly aggregate 1m candles into 5m candles"""
        # Calculate 5-minute boundary (e.g., 09:16:00 -> 09:15:00, 09:20:00 -> 09:20:00)
        minute = timestamp.minute
        five_min_boundary = (minute // 5) * 5
        candle_start_time = timestamp.replace(minute=five_min_boundary, second=0, microsecond=0)
        

        # Check if we need to start a new 5-minute candle
        prev_5min_candle = self.five_min_candles[-1] if self.five_min_candles else None
        if safe_datetime_compare(timestamp, candle_start_time, "eq"):
            # Save previous 5-minute candle if it exists ( This would always be the case after initial setup)
            self.five_min_candles.append(self.current_5min_candle)
            self._classify_and_analyze_5min_candle(self.current_5min_candle)
            self._log_5m_completion()

            # Handle sweep target invalidation/adjustment on completed 5m candle
            if self.sweep_target:
                # If target already swept, we look for two consecutive 5m closes below target to invalidate
                if self.target_swept:
                    if self.current_5min_candle.close < self.sweep_target:
                        self.count_five_min_close_below_sweep += 1
                        if self.count_five_min_close_below_sweep >= 2:
                            self.sweep_target_invalidated = True
                            self.two_CR_valid = False
                            old_target = self.sweep_target
                            self.sweep_target = None
                            self.count_five_min_close_below_sweep = 0
                            if self.logger:
                                old_target_str = f"{old_target:.2f}" if old_target is not None else "NONE"
                                self.logger.warning(f"⚠️ SWEEP TARGET INVALIDATED after {self.count_five_min_close_below_sweep} 5m closes below target")
                                self.logger.warning(f"   Invalidated Target: {old_target_str}")
                    else:
                        pass
                else:
                    # Before sweep: allow target refinement on BEAR/NEUTRAL 5m candles
                    candle_type = self.get_candle_type(self.current_5min_candle)
                    if candle_type in ("BEAR", "NEUTRAL"):
                        old_target = self.sweep_target
                        self.sweep_target = self.current_5min_candle.low
                        self.sweep_set_time = self.current_5min_candle.timestamp + timedelta(minutes=5)
                        self.count_five_min_close_below_sweep = 0
                        if self.logger:
                            self.logger.info(f"🎯 SWEEP TARGET ADJUSTED (5m candle completion)!")
                            old_target_str = f"{old_target:.2f}" if old_target else "NONE"
                            self.logger.info(f"   Old Target: {old_target_str}")
                            self.logger.info(f"   New Target: {self.sweep_target:.2f}")
                            self.logger.info(f"   Set Time: {self.sweep_set_time.strftime('%H:%M:%S')}")
                            self.logger.info(f"   From 5m Candle: {candle_type} at {self.current_5min_candle.timestamp.strftime('%H:%M:%S')}")
                            self.logger.info(f"   5m Candle OHLC: O:{self.current_5min_candle.open:.2f} H:{self.current_5min_candle.high:.2f} L:{self.current_5min_candle.low:.2f} C:{self.current_5min_candle.close:.2f}")
                            self.logger.info(f"   Reset close count: {self.count_five_min_close_below_sweep}")
                    else:
                        if self.logger:
                            self.logger.info(f"ℹ️ SWEEP TARGET: Not adjusted - 5m candle is {candle_type} (need BEAR/NEUTRAL)")

            self._start_new_5m_candle(price, candle_start_time)
        else:
            # Update existing 5-minute candle with proper OHLC aggregation
            if hasattr(self, 'current_1min_candle') and self.current_1min_candle:
                # Update OHLC properly: O stays same, H=max(H,new_high), L=min(L,new_low), C=new_close
                self.current_5min_candle.high = max(self.current_5min_candle.high, self.current_1min_candle.high)
                self.current_5min_candle.low = min(self.current_5min_candle.low, self.current_1min_candle.low)
                self.current_5min_candle.close = self.current_1min_candle.close
            else:
                # Fallback to simple price update
                self.current_5min_candle.update_price(price)
            
            if self.logger:
                self.logger.debug(f"   Updated existing 5m candle: O:{self.current_5min_candle.open:.2f} H:{self.current_5min_candle.high:.2f} L:{self.current_5min_candle.low:.2f} C:{self.current_5min_candle.close:.2f}")
    
    def _classify_and_analyze_1min_candle(self, candle):
        """Classify 1-minute candle and update session data"""
        candle_type = self.get_candle_type(candle)
        
        # Update session high/low
        if self.session_high is None or candle.high > self.session_high:
            self.session_high = candle.high
            self.session_high_time = candle.timestamp
        
        if self.session_low is None or candle.low < self.session_low:
            self.session_low = candle.low
            self.session_low_time = candle.timestamp
        
        # Track bear candles for CISD
        if candle_type == "BEAR" or candle_type == "NEUTRAL":
            self.last_consecutive_bear_candles.append(candle)
        elif candle_type == "BULL":
            self.last_consecutive_bear_candles.clear()
        
        if self.logger:
            self.logger.debug(f"1-Min Candle Analysis: {candle_type} - Session High: {self.session_high:.2f}, Session Low: {self.session_low:.2f}")
    
    def _classify_and_analyze_5min_candle(self, candle):
        """Classify 5-minute candle and notify strategy manager"""
        candle_type = self.get_candle_type(candle)
        
        if self.logger:
            self.logger.debug(f"5-Min Candle Analysis: {candle_type} - O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
        
        # Notify strategy manager about completed 5-minute candle
        if self.on_5min_candle_complete:
            try:
                self.on_5min_candle_complete(candle)
                if self.logger:
                    self.logger.debug(f"Notified strategy manager of completed 5-minute candle: {candle.timestamp.strftime('%H:%M:%S')}")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error in 5-minute candle callback: {e}")
    
    def get_candle_type(self, candle):
        """Determine candle type based on body size"""
        body_size = candle.body_size()
        total_range = candle.high - candle.low
        
        if total_range == 0:
            return "NEUTRAL"
        
        body_percentage = (body_size / total_range) * 100
        
        if body_percentage >= 70:
            return "BULL" if candle.close > candle.open else "BEAR"
        else:
            return "NEUTRAL"
    
    def get_candle_symbol(self, candle):
        """Get visual symbol for candle type"""
        candle_type = self.get_candle_type(candle)
        
        if candle_type == "BULL":
            return "🟢"  # Green circle for bullish
        elif candle_type == "BEAR":
            return "🔴"  # Red circle for bearish
        else:
            return "⚪"  # White circle for neutral
    
    def set_initial_5min_candle(self, candle):
        """Set the initial 5-minute candle for proper tracking"""
        if candle:
            self.current_5min_candle = candle
            self.last_5min_candle_time = candle.timestamp
            self.sweep_target = candle.low
            self.sweep_set_time = candle.timestamp + timedelta(minutes=5)  # Set slightly after candle time
            self.target_swept = False
            self.sweep_target_invalidated = False
            self.two_CR_valid = True
            self.count_five_min_close_below_sweep = 0
            if self.logger:
                self.logger.info(f"🎯 INITIAL SWEEP TARGET SET!")
                self.logger.info(f"   From initial 5-minute candle: {candle.timestamp.strftime('%H:%M:%S')}")
                self.logger.info(f"   OHLC: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
                self.logger.info(f"   Sweep Target: {self.sweep_target:.2f}")
                self.logger.info(f"   Set Time: {self.sweep_set_time.strftime('%H:%M:%S')}")
                self.logger.info(f"   Target Swept: {self.target_swept}")
                self.logger.info(f"   Two CR Valid: {self.two_CR_valid}")
    
    def set_initial_1min_candle(self, candle):
        """Set the initial 1-minute candle for proper tracking"""
        if candle:
            self.current_1min_candle = candle
            self.last_1min_candle_time = candle.timestamp
            if self.logger:
                self.logger.info(f"Set initial 1-minute candle: {candle.timestamp.strftime('%H:%M:%S')} - O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
    
    # ==================== UTILITY METHODS ====================
    
    def check_for_sweep(self, candle_time: datetime) -> bool:
        """
        Check if current 1m candle sweeps the target price
        
        Args:
            candle_time: Timestamp of the candle to check
        
        Returns:
            True if sweep detected, False otherwise
        """
        # Enhanced logging for live trading debugging
        if self.logger:
            self.logger.info(f"🔍 SWEEP CHECK DEBUG:")
            candle_time_str = candle_time.strftime('%Y-%m-%d %H:%M:%S') if candle_time else 'None'
            self.logger.info(f"   Candle Time: {candle_time_str}")
            self.logger.info(f"   Current 1m Candle: {'EXISTS' if self.current_1min_candle else 'NONE'}")
            if self.current_1min_candle:
                self.logger.info(f"   1m Candle Time: {self.current_1min_candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"   1m Candle OHLC: O:{self.current_1min_candle.open:.2f} H:{self.current_1min_candle.high:.2f} L:{self.current_1min_candle.low:.2f} C:{self.current_1min_candle.close:.2f}")
            sweep_target_str = f"{self.sweep_target:.2f}" if self.sweep_target else "NONE"
            self.logger.info(f"   Sweep Target: {sweep_target_str}")
            self.logger.info(f"   Target Swept: {self.target_swept}")
            self.logger.info(f"   Target Invalidated: {self.sweep_target_invalidated}")
            self.logger.info(f"   Two CR Valid: {self.two_CR_valid}")
            sweep_set_time_str = self.sweep_set_time.strftime('%Y-%m-%d %H:%M:%S') if self.sweep_set_time else 'NONE'
            self.logger.info(f"   Sweep Set Time: {sweep_set_time_str}")
        
        # Check if we have a current 1-minute candle
        if not self.current_1min_candle:
            if self.logger:
                self.logger.warning(f"❌ SWEEP CHECK: No current 1-minute candle available")
            return False
        
        # Only check for sweep in candles that come AFTER the target was set
        if candle_time and self.current_1min_candle.timestamp < candle_time:
            if self.logger:
                self.logger.info(f"⏭️ SWEEP CHECK: Skipping - candle time {self.current_1min_candle.timestamp.strftime('%H:%M:%S')} < check time {candle_time.strftime('%H:%M:%S')}")
            return False

        # If target already swept, continue tracking for deepest sweep.
        # Preserve deepest_sweep_candle while the current 1m is forming; only update on completed 1m analysis
        if self.target_swept:
            if self.logger:
                self.logger.info(f"✅ SWEEP CHECK: Target already swept, tracking for deepest sweep")
            # Do not mutate deepest_sweep_candle here to avoid clearing during forming candles
            return True

        # Check if we have a sweep target set
        if not self.sweep_target:
            if self.logger:
                self.logger.info(f"ℹ️ SWEEP CHECK: No sweep target set")
            return False
        
        # Check if target is invalidated
        if self.sweep_target_invalidated:
            if self.logger:
                self.logger.info(f"❌ SWEEP CHECK: Sweep target invalidated")
            return False
        
        # Check if two CR is not valid
        if not self.two_CR_valid:
            if self.logger:
                self.logger.info(f"❌ SWEEP CHECK: Two CR not valid")
            return False
        
        # Check if this 1-minute candle sweeps the target
        candle_low = self.current_1min_candle.low
        if candle_low < self.sweep_target:
            self.target_swept = True
            candle_type = self.get_candle_type(self.current_1min_candle)
            
            if self.logger:
                self.logger.info(f"🎯 SWEEP DETECTED!")
                self.logger.info(f"   Sweep Target: {self.sweep_target:.2f}")
                self.logger.info(f"   Candle Low: {candle_low:.2f}")
                self.logger.info(f"   Sweep Depth: {self.sweep_target - candle_low:.2f}")
                self.logger.info(f"   Candle Type: {candle_type}")
                self.logger.info(f"   Candle Time: {self.current_1min_candle.timestamp.strftime('%H:%M:%S')}")
            
            # Do not update/clear deepest_sweep_candle here; defer to 1m completion classification
            if not self.deepest_sweep_candle:
                self.deepest_sweep_candle = self.current_1min_candle
            else:
                if candle_low < self.deepest_sweep_candle.low:
                    self.deepest_sweep_candle = self.current_1min_candle
            return True
        else:
            if self.logger:
                self.logger.info(f"ℹ️ SWEEP CHECK: No sweep - candle low {candle_low:.2f} >= target {self.sweep_target:.2f}")
        
        return False

    def check_for_sweep_on_candle(self, candle: Candle) -> bool:
        """
        Check if the provided 1m candle sweeps the target price.

        This is used when strategy logic needs to evaluate the sweep condition
        against a specific completed 1m candle rather than the currently forming candle.
        """
        if not candle:
            return False

        if self.logger:
            self.logger.info("🔍 SWEEP CHECK (ON PROVIDED CANDLE):")
            self.logger.info(f"   Candle Time: {candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"   Candle OHLC: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
            target_str = f"{self.sweep_target:.2f}" if self.sweep_target is not None else "NONE"
            self.logger.info(f"   Sweep Target: {target_str}")
            self.logger.info(f"   Target Swept: {self.target_swept}")
            self.logger.info(f"   Target Invalidated: {self.sweep_target_invalidated}")
            self.logger.info(f"   Two CR Valid: {self.two_CR_valid}")

        if not self.sweep_target or self.sweep_target_invalidated or not self.two_CR_valid:
            return False

        if candle.low < self.sweep_target:
            self.target_swept = True
            if self.logger:
                self.logger.info("🎯 SWEEP DETECTED (ON PROVIDED CANDLE)!")
                self.logger.info(f"   Sweep Target: {self.sweep_target:.2f}")
                self.logger.info(f"   Candle Low: {candle.low:.2f}")
                self.logger.info(f"   Sweep Depth: {self.sweep_target - candle.low:.2f}")
                self.logger.info(f"   Candle Type: {self.get_candle_type(candle)}")
                self.logger.info(f"   Candle Time: {candle.timestamp.strftime('%H:%M:%S')}")
            # Defer deepest_sweep_candle updates to completion flow
            return True

        if self.logger:
            self.logger.info(f"ℹ️ SWEEP CHECK (ON PROVIDED CANDLE): No sweep - candle low {candle.low:.2f} >= target {self.sweep_target:.2f}")
        return False
    
    def detect_imps(self, target_ratio: float = 2.0) -> Optional[Dict]:
        """
        Detect IMPS (1-minute bullish Fair Value Gap)
        
        Args:
            target_ratio: Risk-reward ratio for target calculation
        
        Returns:
            Dictionary with trade details if IMPS found, None otherwise
        """
        if len(self.one_min_candles) < 3:
            return None
        
        # Get last 3 candles
        last_three = list(self.one_min_candles)[-3:]
        
        # Check for bullish FVG pattern (c3.low > c1.high)
        if (last_three[0].close < last_three[1].open and 
            last_three[1].close > last_three[2].open):
            
            # Calculate FVG levels
            fvg_high = min(last_three[0].close, last_three[2].open)
            fvg_low = max(last_three[0].close, last_three[2].open)
            
            if fvg_high > fvg_low:
                entry = fvg_high
                stop_loss = fvg_low
                target = entry + (entry - stop_loss) * target_ratio
                
                return {
                    'type': 'IMPS',
                    'entry': round_to_tick(entry, self.tick_size),
                    'stop_loss': round_to_tick(stop_loss, self.tick_size),
                    'target': round_to_tick(target, self.tick_size),
                    'fvg_high': fvg_high,
                    'fvg_low': fvg_low,
                    'candles': last_three
                }
        
        return None
    
    def detect_cisd(self, target_ratio: float = 4.0) -> Optional[Dict]:
        """
        Detect CISD (current close passing the open of the earliest candle in the
        most recent consecutive bear run), with a fallback using the deepest-sweep candle.
        
        Args:
            target_ratio: Risk-reward ratio for target calculation
        
        Returns:
            Dictionary with trade details if CISD found, None otherwise
        """
        # Must have a current 1m candle
        if not self.current_1min_candle:
            return None


        # 1) Consecutive-bear run condition
        if self.last_consecutive_bear_candles and len(self.last_consecutive_bear_candles) > 0:
            # deque is in chronological order (older -> newer)
            first_bear_candle = self.last_consecutive_bear_candles[0]   # earliest in the run
            last_bear_candle = self.last_consecutive_bear_candles[-1]   # most recent in the run

            # Trigger when current close passes the open of the earliest bear in the run
            if self.current_1min_candle.close >= first_bear_candle.open:
                entry = first_bear_candle.open
                stop_loss = last_bear_candle.low
                target = entry + (entry - stop_loss) * target_ratio

                return {
                    'type': 'CISD',
                    'entry': round_to_tick(entry, self.tick_size),
                    'stop_loss': round_to_tick(stop_loss, self.tick_size),
                    'target': round_to_tick(target, self.tick_size),
                    'entry_candle': self.current_1min_candle
                }

        # 2) Fallback: use deepest sweep candle if available
        if self.deepest_sweep_candle:
            if self.current_1min_candle.close >= self.deepest_sweep_candle.close:
                entry = self.deepest_sweep_candle.close
                stop_loss = self.deepest_sweep_candle.low
                target = entry + (entry - stop_loss) * target_ratio

                return {
                    'type': 'CISD',
                    'entry': round_to_tick(entry, self.tick_size),
                    'stop_loss': round_to_tick(stop_loss, self.tick_size),
                    'target': round_to_tick(target, self.tick_size),
                    'entry_candle': self.current_1min_candle
                }

        return None

    def detect_cisd_on_candle(self, candle: Candle, target_ratio: float = 4.0) -> Optional[Dict]:
        """
        CISD using the provided completed 1m candle.
        Primary: current close >= earliest bear-run open
        Fallback: current close >= deepest_sweep_candle.close
        """
        if not candle:
            return None

        # Consecutive-bear run primary condition
        if self.last_consecutive_bear_candles and len(self.last_consecutive_bear_candles) > 0:
            first_bear_candle = self.last_consecutive_bear_candles[0]
            last_bear_candle = self.last_consecutive_bear_candles[-1]
            if candle.close >= first_bear_candle.open:
                entry = first_bear_candle.open
                stop_loss = last_bear_candle.low
                target = entry + (entry - stop_loss) * target_ratio
                return {
                    'type': 'CISD',
                    'entry': round_to_tick(entry, self.tick_size),
                    'stop_loss': round_to_tick(stop_loss, self.tick_size),
                    'target': round_to_tick(target, self.tick_size),
                    'entry_candle': candle
                }

        # Fallback using deepest sweep candle
        if self.deepest_sweep_candle and candle.close >= self.deepest_sweep_candle.close:
            entry = self.deepest_sweep_candle.close
            stop_loss = self.deepest_sweep_candle.low
            target = entry + (entry - stop_loss) * target_ratio
            return {
                'type': 'CISD',
                'entry': round_to_tick(entry, self.tick_size),
                'stop_loss': round_to_tick(stop_loss, self.tick_size),
                'target': round_to_tick(target, self.tick_size),
                'entry_candle': candle
            }

        return None
    
    def check_for_sting(self, bullish_zones: List[Dict]) -> Optional[Dict]:
        """
        Detect if current 1m candle stings into bullish FVG/IFVG zones
        
        Args:
            bullish_zones: List of bullish FVG/IFVG zones to check against
        
        Returns:
            Dictionary with sting details if found, None otherwise
        """
        if not self.current_1min_candle or not bullish_zones:
            return None
        
        # Check against bullish FVGs/IFVGs - candle stings INTO the zone
        for zone in bullish_zones:
            # Sting condition: candle low is within the zone range
            if zone['lower'] <= self.current_1min_candle.low <= zone['upper']:
                return {
                    'type': 'STING',
                    'stung_zone': zone,
                    'candle_low': self.current_1min_candle.low,
                    'zone_upper': zone['upper'],
                    'zone_lower': zone['lower'],
                    'candle': self.current_1min_candle
                }
        
        return None
    
    def is_days_low_sweep(self, price: float) -> bool:
        """Check if this is a day's low sweep"""
        if not self.session_low:
            return False
        return abs(price - self.session_low) < self.tick_size
    
    def calculate_target_ratio(self, is_days_low: bool) -> float:
        """Calculate target ratio based on entry conditions"""
        if is_days_low:
            return 3.0  # Higher target for day's low
        else:
            return 2.0  # Standard target
    
    def get_recent_5min_low(self, lookback: int = 5) -> Optional[float]:
        """Get the lowest low from recent 5-minute candles"""
        if len(self.five_min_candles) < lookback:
            return None
        
        recent_candles = list(self.five_min_candles)[-lookback:]
        return min(candle.low for candle in recent_candles)
    
    def get_recent_5min_high(self, lookback: int = 5) -> Optional[float]:
        """Get the highest high from recent 5-minute candles"""
        if len(self.five_min_candles) < lookback:
            return None
        
        recent_candles = list(self.five_min_candles)[-lookback:]
        return max(candle.high for candle in recent_candles)
    
    def get_candle_summary(self) -> Dict:
        """Get summary of current candle data"""
        return {
            'current_1min_candle': {
                'timestamp': self.current_1min_candle.timestamp.isoformat() if self.current_1min_candle else None,
                'open': self.current_1min_candle.open if self.current_1min_candle else None,
                'high': self.current_1min_candle.high if self.current_1min_candle else None,
                'low': self.current_1min_candle.low if self.current_1min_candle else None,
                'close': self.current_1min_candle.close if self.current_1min_candle else None
            },
            'current_5min_candle': {
                'timestamp': self.current_5min_candle.timestamp.isoformat() if self.current_5min_candle else None,
                'open': self.current_5min_candle.open if self.current_5min_candle else None,
                'high': self.current_5min_candle.high if self.current_5min_candle else None,
                'low': self.current_5min_candle.low if self.current_5min_candle else None,
                'close': self.current_5min_candle.close if self.current_5min_candle else None
            },
            'session_high': self.session_high,
            'session_low': self.session_low,
            'total_1min_candles': len(self.one_min_candles),
            'total_5min_candles': len(self.five_min_candles),
            'bear_candles_count': len(self.last_consecutive_bear_candles)
        }
