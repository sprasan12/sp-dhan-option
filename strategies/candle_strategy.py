"""
Clean CandleStrategy Base Class
Simple, extensible base class for all trading strategies
Only tracks 5m and 1m timeframes - no 15m complexity
"""

from collections import deque
from datetime import timedelta
from models.candle import Candle
from utils.market_utils import get_market_boundary_time, round_to_tick
from utils.timezone_utils import safe_datetime_compare, ensure_timezone_naive

class CandleStrategy:
    """Clean base strategy class with 5m and 1m timeframe tracking"""
    
    def __init__(self, tick_size=0.05, swing_look_back=2, logger=None, exit_callback=None, entry_callback=None):
        self.tick_size = tick_size
        self.swing_look_back = swing_look_back
        self.logger = logger
        self.exit_callback = exit_callback
        self.entry_callback = entry_callback
        
        # Candle storage - only 5m and 1m
        self.five_min_candles = deque(maxlen=300)   # Store 5-minute candles
        self.one_min_candles = deque(maxlen=1500)   # Store 1-minute candles
        
        # Current candles
        self.current_5min_candle = None
        self.current_1min_candle = None
        
        # Sweep detection (5m timeframe)
        self.sweep_detected = False
        self.sweep_low = None
        self.waiting_for_sweep = False
        self.sweep_target_set_time = None
        self.recovery_low = None
        
        # Session tracking
        self.session_high = None
        self.session_low = None
        self.session_high_time = None
        self.session_low_time = None
        self.days_low_swept = False
        
        # Trade management
        self.in_trade = False
        self.entry_price = None
        self.stop_loss = None
        self.target = None
        self.current_target_ratio = None
        
        # Bear candle tracking for CISD
        self.last_bear_candles = deque(maxlen=10)
        
        # FVG tracking
        self.fvg_invalidation_count = 0
        self.last_fvg_invalidation_time = None
        
        # Target invalidation tracking
        self.target_invalidation_count = 0
        self.last_target_invalidation_time = None
        
        # Time tracking
        self.last_5min_candle_time = None
        self.last_1min_candle_time = None
    
    def update_1min_candle(self, price, timestamp):
        """Update 1-minute candle with price data"""
        timestamp = ensure_timezone_naive(timestamp)
        
        # Check if we need to start a new 1-minute candle
        if not self.current_1min_candle or not safe_datetime_compare(self.current_1min_candle.timestamp, timestamp, "eq"):
            # Save previous candle if it exists
            if self.current_1min_candle:
                self.one_min_candles.append(self.current_1min_candle)
                if self.logger:
                    self.logger.info(f"1-Min Candle: O:{self.current_1min_candle.open:.2f} H:{self.current_1min_candle.high:.2f} L:{self.current_1min_candle.low:.2f} C:{self.current_1min_candle.close:.2f}")
            
            # Start new 1-minute candle
            self.current_1min_candle = Candle(
                timestamp=timestamp,
                open_price=price,
                high=price,
                low=price,
                close=price
            )
            self.last_1min_candle_time = timestamp
        else:
            # Update existing 1-minute candle
            self.current_1min_candle.update_price(price)
        
        # Update 5-minute candle
        self._update_5min_candle(price, timestamp)
        
        # Run strategy logic
        if not self.in_trade:
            self._run_strategy_logic(price, timestamp)
    
    def update_1min_candle_with_data(self, candle_data, timestamp):
        """Update 1-minute candle with complete OHLC data"""
        timestamp = ensure_timezone_naive(timestamp)
        
        # Create new 1-minute candle
        candle = Candle(
            timestamp=timestamp,
            open_price=candle_data['open'],
            high=candle_data['high'],
            low=candle_data['low'],
            close=candle_data['close']
        )
        
        # Save previous candle if it exists
        if self.current_1min_candle:
            self.one_min_candles.append(self.current_1min_candle)
        
        # Set new current candle
        self.current_1min_candle = candle
        self.last_1min_candle_time = timestamp
        
        # Update 5-minute candle
        self._update_5min_candle(candle_data['close'], timestamp)
        
        # Run strategy logic
        if not self.in_trade:
            self._run_strategy_logic(candle_data['close'], timestamp)
    
    def _update_5min_candle(self, price, timestamp):
        """Update 5-minute candle"""
        # Calculate 5-minute boundary
        minute = timestamp.minute
        five_min_boundary = (minute // 5) * 5
        candle_start_time = timestamp.replace(minute=five_min_boundary, second=0, microsecond=0)
        
        # Check if we need to start a new 5-minute candle
        if not self.current_5min_candle or not safe_datetime_compare(self.current_5min_candle.timestamp, candle_start_time, "eq"):
            # Save previous 5-minute candle if it exists
            if self.current_5min_candle:
                self.five_min_candles.append(self.current_5min_candle)
                self._classify_and_analyze_5min_candle(self.current_5min_candle)
                if self.logger:
                    self.logger.info(f"5-Min Candle: O:{self.current_5min_candle.open:.2f} H:{self.current_5min_candle.high:.2f} L:{self.current_5min_candle.low:.2f} C:{self.current_5min_candle.close:.2f}")
            
            # Start new 5-minute candle
            self.current_5min_candle = Candle(
                timestamp=candle_start_time,
                open_price=price,
                high=price,
                low=price,
                close=price
            )
            self.last_5min_candle_time = candle_start_time
        else:
            # Update existing 5-minute candle
            self.current_5min_candle.update_price(price)
    
    def _classify_and_analyze_5min_candle(self, candle):
        """Classify 5-minute candle and prepare for sweep detection"""
        candle_type = self.get_candle_type(candle)
        
        if self.logger:
            self.logger.info(f"5-Min Candle Analysis: {candle_type} - O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
        
        # Check if current 5-min candle closes below existing target (target invalidation)
        if self.waiting_for_sweep and self.sweep_low and candle.close < self.sweep_low:
            if self.logger:
                self.logger.info(f"Target invalidated! Current candle close ({candle.close:.2f}) < Target ({self.sweep_low:.2f})")
            self.sweep_low = candle.low
            self.sweep_detected = False
            self.recovery_low = None
            self.waiting_for_sweep = True
        
        # If it's a bear or neutral candle, prepare for sweep detection
        if candle_type in ["BEAR", "NEUTRAL"]:
            # Only set new target if we don't already have one or if current candle is better
            if not self.waiting_for_sweep or not self.sweep_low or candle.low < self.sweep_low:
                self.waiting_for_sweep = True
                self.sweep_low = candle.low
                self.sweep_detected = False
                self.recovery_low = None
                self.sweep_target_set_time = candle.timestamp
                if self.logger:
                    self.logger.info(f"New target set: {self.sweep_low:.2f} at {candle.timestamp.strftime('%H:%M:%S')}")
                
                # Track bear candles for CISD
                if candle_type == "BEAR":
                    self.last_bear_candles.append(candle)
        else:
            # For bull candles, don't reset target - keep existing target active
            target_str = f"{self.sweep_low:.2f}" if self.sweep_low is not None else "None"
            if self.logger:
                self.logger.info(f"Bull candle - keeping existing target: {target_str}")
    
    def _run_strategy_logic(self, price, timestamp):
        """Run the main strategy logic - to be overridden by subclasses"""
        # Check sweep conditions
        if self.current_1min_candle:
            sweep_trigger = self._check_sweep_conditions(self.current_1min_candle)
            if sweep_trigger:
                self._handle_sweep_trigger(sweep_trigger, price, timestamp)
    
    def _check_sweep_conditions(self, one_min_candle):
        """Check if 1-minute candle sweeps the 5m low"""
        if not self.waiting_for_sweep or not self.sweep_low:
            return None
        
        # Only check for sweep in candles that come AFTER the target was set
        if self.sweep_target_set_time and one_min_candle.timestamp <= self.sweep_target_set_time:
            return None
        
        # Check if this 1-minute candle sweeps the 5m low
        if one_min_candle.low < self.sweep_low:
            if not self.sweep_detected:
                self.sweep_detected = True
                self.recovery_low = one_min_candle.low
                
                if self.logger:
                    self.logger.info(f"SWEEP DETECTED! 1min low: {one_min_candle.low:.2f} < 5m target: {self.sweep_low:.2f}")
                
                # Check if this is a day's low sweep
                is_days_low = self._is_days_low_sweep(one_min_candle.low)
                if is_days_low:
                    self.days_low_swept = True
                
                # Calculate target ratio
                target_ratio = self._calculate_target_ratio(one_min_candle.low, is_days_low)
                self.current_target_ratio = target_ratio
                
                if self.logger:
                    self.logger.info(f"Day's Low Sweep: {'✅' if is_days_low else '❌'}")
                    self.logger.info(f"Target Ratio: {target_ratio:.1f}:1")
                    self.logger.info(f"Looking for IMPS/CISD...")
            else:
                # Update recovery low if this candle goes lower
                if one_min_candle.low < self.recovery_low:
                    self.recovery_low = one_min_candle.low
                    if self.logger:
                        self.logger.info(f"Recovery Low Updated: {one_min_candle.low:.2f}")
        
        # Look for IMPS/CISD if we have detected a sweep and close >= recovery low
        if self.sweep_detected and one_min_candle.close >= self.recovery_low:
            if self.logger:
                self.logger.info(f"Checking for IMPS/CISD - Close: {one_min_candle.close:.2f} >= Recovery Low: {self.recovery_low:.2f}")
            
            # Look for IMPS (1-minute bullish FVG)
            imps_fvg = self._detect_1min_bullish_fvg()
            if imps_fvg:
                if self.logger:
                    self.logger.info(f"IMPS (1-Min Bullish FVG) Found! Entry: {imps_fvg['entry']:.2f}, Stop: {imps_fvg['stop_loss']:.2f}")
                return imps_fvg
            
            # Look for CISD (passing open of bear candles)
            cisd_trigger = self._detect_cisd()
            if cisd_trigger:
                if self.logger:
                    self.logger.info(f"CISD (Bear Candle Open) Found! Entry: {cisd_trigger['entry']:.2f}, Stop: {cisd_trigger['stop_loss']:.2f}")
                return cisd_trigger
        elif self.sweep_detected:
            if self.logger:
                self.logger.info(f"Waiting for close >= recovery low ({self.recovery_low:.2f}). Current close: {one_min_candle.close:.2f}")
        
        return None
    
    def _handle_sweep_trigger(self, sweep_trigger, price, timestamp):
        """Handle sweep trigger - to be overridden by subclasses"""
        if self.entry_callback:
            self.entry_callback(sweep_trigger)
    
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
    
    def _is_days_low_sweep(self, price):
        """Check if this is a day's low sweep"""
        if not self.session_low:
            return False
        return abs(price - self.session_low) < self.tick_size
    
    def _calculate_target_ratio(self, entry_price, is_days_low):
        """Calculate target ratio based on entry conditions"""
        if is_days_low:
            return 3.0  # Higher target for day's low
        else:
            return 2.0  # Standard target
    
    def _detect_1min_bullish_fvg(self):
        """Detect 1-minute bullish Fair Value Gap"""
        if len(self.one_min_candles) < 3:
            return None
        
        # Get last 3 candles
        last_three = list(self.one_min_candles)[-3:]
        
        # Check for bullish FVG pattern
        if (last_three[0].close < last_three[1].open and 
            last_three[1].close > last_three[2].open):
            
            # Calculate FVG levels
            fvg_high = min(last_three[0].close, last_three[2].open)
            fvg_low = max(last_three[0].close, last_three[2].open)
            
            if fvg_high > fvg_low:
                entry = fvg_high
                stop_loss = fvg_low
                target = entry + (entry - stop_loss) * self.current_target_ratio
                
                return {
                    'type': 'IMPS',
                    'entry': round_to_tick(entry, self.tick_size),
                    'stop_loss': round_to_tick(stop_loss, self.tick_size),
                    'target': round_to_tick(target, self.tick_size)
                }
        
        return None
    
    def _detect_cisd(self):
        """Detect CISD (passing open of bear candles)"""
        if not self.last_bear_candles or not self.current_1min_candle:
            return None
        
        # Check if current candle passes the open of any bear candle
        for bear_candle in self.last_bear_candles:
            if self.current_1min_candle.close > bear_candle.open:
                entry = bear_candle.open
                stop_loss = bear_candle.low
                target = entry + (entry - stop_loss) * self.current_target_ratio
                
                return {
                    'type': 'CISD',
                    'entry': round_to_tick(entry, self.tick_size),
                    'stop_loss': round_to_tick(stop_loss, self.tick_size),
                    'target': round_to_tick(target, self.tick_size)
                }
        
        return None
    
    def enter_trade(self, entry_price, stop_loss, target):
        """Enter a trade"""
        self.in_trade = True
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.target = target
        
        if self.logger:
            self.logger.info(f"Trade Entered - Entry: {entry_price:.2f}, Stop: {stop_loss:.2f}, Target: {target:.2f}")
    
    def exit_trade(self, exit_price, reason):
        """Exit a trade"""
        self.in_trade = False
        self.entry_price = None
        self.stop_loss = None
        self.target = None
        
        if self.logger:
            self.logger.info(f"Trade Exited - Price: {exit_price:.2f}, Reason: {reason}")
        
        # Reset sweep detection
        self.reset_sweep_detection()
        
        if self.exit_callback:
            self.exit_callback(exit_price, reason)
    
    def reset_sweep_detection(self):
        """Reset sweep detection after entering trade"""
        self.waiting_for_sweep = False
        self.sweep_detected = False
        self.sweep_low = None
        self.recovery_low = None
        self.sweep_target_set_time = None
    
    def set_initial_5min_candle(self, candle):
        """Set the initial 5-minute candle for proper tracking"""
        if candle:
            self.current_5min_candle = candle
            self.last_5min_candle_time = candle.timestamp
            if self.logger:
                self.logger.info(f"Set initial 5-minute candle: {candle.timestamp.strftime('%H:%M:%S')} - O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
    
    def should_move_target(self, current_price):
        """Check if target should be moved based on profit levels"""
        if not self.in_trade or not self.entry_price or not self.target:
            return False
        
        # Calculate current profit
        profit = current_price - self.entry_price
        profit_percentage = (profit / self.entry_price) * 100
        
        # Move target to breakeven if profit is 50% of target
        if profit_percentage >= 0.5:
            self.target = self.entry_price
            if self.logger:
                self.logger.info(f"Target moved to breakeven: {self.target:.2f}")
            return True
        
        return False
