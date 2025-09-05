"""
15-Minute Candle Strategy implementation
Contains the logic for candle classification, sweep detection, and entry triggers
"""

from collections import deque
from datetime import timedelta
from models.candle import Candle
from utils.market_utils import get_market_boundary_time, round_to_tick

class CandleStrategy:
    """15-minute candle strategy with 1-minute sweep detection"""
    
    def __init__(self, tick_size=0.05, swing_look_back=2, logger=None, exit_callback=None, entry_callback=None):
        self.tick_size = tick_size
        self.swing_look_back = swing_look_back
        self.logger = logger
        self.exit_callback = exit_callback  # Callback to notify when trade exits
        self.entry_callback = entry_callback  # Callback to notify when trade entry is triggered
        
        # Strategy parameters
        self.fifteen_min_candles = deque(maxlen=50)  # Store 15-minute candles
        self.one_min_candles = deque(maxlen=100)     # Store 1-minute candles for sweep detection
        self.current_15min_candle = None
        self.current_1min_candle = None
        self.sweep_detected = False
        self.sweep_low = None
        self.waiting_for_sweep = False
        self.sweep_target_set_time = None  # Track when the target was set
        self.recovery_low = None  # Track the lowest point after sweep
        self.last_bear_candles = deque(maxlen=10)  # Track bear candles for CISD
        
        # Trade management parameters
        self.in_trade = False
        self.entry_price = None
        self.current_stop_loss = None
        self.current_target = None
        self.initial_stop_loss = None  # Store initial SL for RR calculations
        self.initial_target = None     # Store initial target for profit level checks
        self.swing_lows = deque(maxlen=50)  # Track swing lows for SL movement
        
        # Target movement tracking
        self.target_moved_to_rr4 = False  # Track if target moved to RR=4
        self.target_removed = False       # Track if target removed for trailing
        
        # Target invalidation tracking
        self.target_invalidation_count = 0  # Count total 15m candles closing below target (not necessarily consecutive)
        self.last_target_invalidation_time = None  # Track when target was last invalidated
    
    def update_15min_candle(self, price, timestamp):
        """Update or create a new 15-minute candle"""
        # Round the price to tick size
        price = round_to_tick(price, self.tick_size)
        
        # Get the current market time boundary (15-minute intervals starting from 9:15:00)
        current_time = timestamp
        
        # Check if market is open (after 9:15 AM)
        if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 15):
            return
        
        # Calculate the current 15-minute period correctly
        # Market opens at 9:15, so periods are:
        # Period 0: 9:15-9:29 (minutes 0-14)
        # Period 1: 9:30-9:44 (minutes 15-29)
        # Period 2: 9:45-9:59 (minutes 30-44)
        # etc.
        minutes_since_market_open = (current_time.hour - 9) * 60 + (current_time.minute - 15)
        period_number = minutes_since_market_open // 15
        
        # Debug period calculation
        print(f"DEBUG: Period calc - hour:{current_time.hour}, minute:{current_time.minute}, minutes_since_open:{minutes_since_market_open}, period:{period_number}")
        
        # Calculate the start time of this 15-minute period
        period_start_minutes = period_number * 15
        
        # Calculate the candle start time
        market_open_time = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
        candle_start_time = market_open_time + timedelta(minutes=period_start_minutes)
        
        # Debug: Print time calculations
        print(f"DEBUG: Current time: {current_time}, Period: {period_number}, Candle start: {candle_start_time}")
        if self.current_15min_candle:
            print(f"DEBUG: Current candle timestamp: {self.current_15min_candle.timestamp}")
            print(f"DEBUG: Timestamps match: {self.current_15min_candle.timestamp == candle_start_time}")
            print(f"DEBUG: Current 15min candle - O:{self.current_15min_candle.open:.2f} H:{self.current_15min_candle.high:.2f} L:{self.current_15min_candle.low:.2f} C:{self.current_15min_candle.close:.2f}")
        print(f"DEBUG: New price: {price:.2f}")
        
        # If this is a new 15-minute candle period, create a new candle
        if not self.current_15min_candle or self.current_15min_candle.timestamp != candle_start_time:
            # Save the previous 15-minute candle if it exists
            if self.current_15min_candle:
                self.fifteen_min_candles.append(self.current_15min_candle)
                self.classify_and_analyze_15min_candle(self.current_15min_candle)
                
                if self.logger:
                    self.logger.log_15min_candle_completion(self.current_15min_candle)
                else:
                    print(f"\n🕯️ 15-Min Candle Completed: {self.current_15min_candle}")
                    print(f"   Body: {self.current_15min_candle.body_size():.2f} ({self.current_15min_candle.body_percentage():.1f}%)")
                    print(f"   Type: {self.get_candle_type(self.current_15min_candle)}")
            
            # Create new 15-minute candle
            self.current_15min_candle = Candle(candle_start_time, price, price, price, price)
            print(f"🕯️ New 15-Min Candle Started: O:{price:.2f} | Time: {candle_start_time.strftime('%H:%M')}")
        else:
            # Update existing 15-minute candle with current price
            old_low = self.current_15min_candle.low
            old_high = self.current_15min_candle.high
            self.current_15min_candle.high = max(self.current_15min_candle.high, price)
            self.current_15min_candle.low = min(self.current_15min_candle.low, price)
            self.current_15min_candle.close = price
            
            # Print if low or high changed
            if self.current_15min_candle.low < old_low:
                print(f"📉 15-Min Low Updated: {candle_start_time.strftime('%H:%M:%S')} - Old Low: {old_low:.2f} → New Low: {self.current_15min_candle.low:.2f} (Price: {price:.2f})")
            elif self.current_15min_candle.high > old_high:
                print(f"📈 15-Min High Updated: {candle_start_time.strftime('%H:%M:%S')} - Old High: {old_high:.2f} → New High: {self.current_15min_candle.high:.2f} (Price: {price:.2f})")
            else:
                print(f"📊 15-Min Update: {candle_start_time.strftime('%H:%M:%S')} - H:{self.current_15min_candle.high:.2f} L:{self.current_15min_candle.low:.2f} C:{self.current_15min_candle.close:.2f}")
            
            # Check for target invalidation during 15-minute candle formation
            if self.waiting_for_sweep and self.sweep_low and self.current_15min_candle.close < self.sweep_low:
                print(f"⚠️  Target invalidation check: Current close ({self.current_15min_candle.close:.2f}) < Target ({self.sweep_low:.2f})")
                print(f"🔄 Target will be invalidated when this 15-min candle completes")
    
    def update_15min_candle_from_1min(self, one_min_candle):
        """Update 15-minute candle with 1-minute candle data (for proper OHLC aggregation)"""
        if not one_min_candle:
            return
            
        # Get the 15-minute period for this 1-minute candle
        current_time = one_min_candle.timestamp
        
        # Check if market is open (after 9:15 AM)
        if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 15):
            return
        
        # Calculate the current 15-minute period
        minutes_since_market_open = (current_time.hour - 9) * 60 + (current_time.minute - 15)
        period_number = minutes_since_market_open // 15
        
        # Calculate the start time of this 15-minute period
        period_start_minutes = period_number * 15
        market_open_time = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
        candle_start_time = market_open_time + timedelta(minutes=period_start_minutes)
        
        # If this is a new 15-minute candle period, create a new candle
        if not self.current_15min_candle or self.current_15min_candle.timestamp != candle_start_time:
            # Save the previous 15-minute candle if it exists
            if self.current_15min_candle:
                self.fifteen_min_candles.append(self.current_15min_candle)
                self.classify_and_analyze_15min_candle(self.current_15min_candle)
                
                if self.logger:
                    self.logger.log_15min_candle_completion(self.current_15min_candle)
                else:
                    print(f"\n🕯️ 15-Min Candle Completed: {self.current_15min_candle}")
                    print(f"   Body: {self.current_15min_candle.body_size():.2f} ({self.current_15min_candle.body_percentage():.1f}%)")
                    print(f"   Type: {self.get_candle_type(self.current_15min_candle)}")
            
            # Create new 15-minute candle with 1-minute candle data
            self.current_15min_candle = Candle(candle_start_time, one_min_candle.open, one_min_candle.high, one_min_candle.low, one_min_candle.close)
            print(f"🕯️ New 15-Min Candle Started: O:{one_min_candle.open:.2f} H:{one_min_candle.high:.2f} L:{one_min_candle.low:.2f} C:{one_min_candle.close:.2f} | Time: {candle_start_time.strftime('%H:%M')}")
        else:
            # Update existing 15-minute candle with 1-minute candle data
            old_low = self.current_15min_candle.low
            old_high = self.current_15min_candle.high
            self.current_15min_candle.high = max(self.current_15min_candle.high, one_min_candle.high)
            self.current_15min_candle.low = min(self.current_15min_candle.low, one_min_candle.low)
            self.current_15min_candle.close = one_min_candle.close
            
            # Print if low or high changed
            if self.current_15min_candle.low < old_low:
                print(f"📉 15-Min Low Updated from 1min: {candle_start_time.strftime('%H:%M:%S')} - Old Low: {old_low:.2f} → New Low: {self.current_15min_candle.low:.2f} (1min Low: {one_min_candle.low:.2f})")
            elif self.current_15min_candle.high > old_high:
                print(f"📈 15-Min High Updated from 1min: {candle_start_time.strftime('%H:%M:%S')} - Old High: {old_high:.2f} → New High: {self.current_15min_candle.high:.2f} (1min High: {one_min_candle.high:.2f})")
            else:
                print(f"📊 15-Min Update from 1min: {candle_start_time.strftime('%H:%M:%S')} - H:{self.current_15min_candle.high:.2f} L:{self.current_15min_candle.low:.2f} C:{self.current_15min_candle.close:.2f}")
            
            # Check for target invalidation during 15-minute candle formation
            if self.waiting_for_sweep and self.sweep_low and self.current_15min_candle.close < self.sweep_low:
                print(f"⚠️  Target invalidation check: Current close ({self.current_15min_candle.close:.2f}) < Target ({self.sweep_low:.2f})")
                print(f"🔄 Target will be invalidated when this 15-min candle completes")
    
    def update_1min_candle(self, price, timestamp):
        """Update or create a new 1-minute candle for sweep detection (live mode)"""
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
        if not self.current_1min_candle or self.current_1min_candle.timestamp != candle_start_time:
            # Save the previous 1-minute candle if it exists
            if self.current_1min_candle:
                self.one_min_candles.append(self.current_1min_candle)
                
                if self.logger:
                    self.logger.log_1min_candle_completion(self.current_1min_candle)
                else:
                    print(f"📊 1-Min Candle Completed: {self.current_1min_candle.timestamp.strftime('%H:%M:%S')} - O:{self.current_1min_candle.open:.2f} H:{self.current_1min_candle.high:.2f} L:{self.current_1min_candle.low:.2f} C:{self.current_1min_candle.close:.2f}")
                
                # Update 15-minute candle with this completed 1-minute candle
                self.update_15min_candle_from_1min(self.current_1min_candle)
                
                # If in trade, only update swing lows and check exit conditions
                if self.in_trade:
                    self.update_swing_lows()
                else:
                    # Only check sweep conditions if not in trade
                    self.check_sweep_conditions(self.current_1min_candle)
            
            # Create new 1-minute candle
            self.current_1min_candle = Candle(candle_start_time, price, price, price, price)
            print(f"🕯️ New 1min candle at {candle_start_time.strftime('%H:%M:%S')} - O:{price:.2f}")
        else:
            # Update existing 1-minute candle
            old_low = self.current_1min_candle.low
            old_high = self.current_1min_candle.high
            self.current_1min_candle.high = max(self.current_1min_candle.high, price)
            self.current_1min_candle.low = min(self.current_1min_candle.low, price)
            self.current_1min_candle.close = price
            
            # Check for target/SL hits during candle formation (if in trade)
            if self.in_trade:
                # Check if target was hit (high >= target)
                if self.current_1min_candle.high >= self.current_target:
                    print(f"🎯 TARGET HIT during candle formation! High: {self.current_1min_candle.high:.2f} >= Target: {self.current_target:.2f}")
                    self.exit_trade(self.current_target, "target_hit", None)
                    return
                
                # Check if stop loss was hit (low <= stop_loss)
                if self.current_1min_candle.low <= self.current_stop_loss:
                    print(f"🛑 STOP LOSS HIT during candle formation! Low: {self.current_1min_candle.low:.2f} <= SL: {self.current_stop_loss:.2f}")
                    self.exit_trade(self.current_stop_loss, "stop_loss_hit", None)
                    return
            
            # Print if low or high changed
            if self.current_1min_candle.low < old_low:
                print(f"📉 1-Min Low Updated: {candle_start_time.strftime('%H:%M:%S')} - Old Low: {old_low:.2f} → New Low: {self.current_1min_candle.low:.2f} (Price: {price:.2f})")
            elif self.current_1min_candle.high > old_high:
                print(f"📈 1-Min High Updated: {candle_start_time.strftime('%H:%M:%S')} - Old High: {old_high:.2f} → New High: {self.current_1min_candle.high:.2f} (Price: {price:.2f})")
            else:
                print(f"📊 1-Min Update: {candle_start_time.strftime('%H:%M:%S')} - H:{self.current_1min_candle.high:.2f} L:{self.current_1min_candle.low:.2f} C:{self.current_1min_candle.close:.2f}")
    
    def update_1min_candle_with_data(self, candle_data, timestamp):
        """Update or create a new 1-minute candle with complete OHLC data (demo mode)"""
        # Extract OHLC data from candle_data
        open_price = round_to_tick(float(candle_data["open"]), self.tick_size)
        high_price = round_to_tick(float(candle_data["high"]), self.tick_size)
        low_price = round_to_tick(float(candle_data["low"]), self.tick_size)
        close_price = round_to_tick(float(candle_data["close"]), self.tick_size)
        
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
        if not self.current_1min_candle or self.current_1min_candle.timestamp != candle_start_time:
            # Save the previous 1-minute candle if it exists
            if self.current_1min_candle:
                self.one_min_candles.append(self.current_1min_candle)
                
                if self.logger:
                    self.logger.log_1min_candle_completion(self.current_1min_candle)
                else:
                    print(f"📊 1-Min Candle Completed: {self.current_1min_candle.timestamp.strftime('%H:%M:%S')} - O:{self.current_1min_candle.open:.2f} H:{self.current_1min_candle.high:.2f} L:{self.current_1min_candle.low:.2f} C:{self.current_1min_candle.close:.2f}")
                
                # Update 15-minute candle with this completed 1-minute candle
                self.update_15min_candle_from_1min(self.current_1min_candle)
                
                # If in trade, only update swing lows and check exit conditions
                if self.in_trade:
                    self.update_swing_lows()
                else:
                    # Only check sweep conditions if not in trade
                    self.check_sweep_conditions(self.current_1min_candle)
            
            # Create new 1-minute candle with complete OHLC data
            self.current_1min_candle = Candle(candle_start_time, open_price, high_price, low_price, close_price)
            print(f"🕯️ New 1min candle at {candle_start_time.strftime('%H:%M:%S')} - O:{open_price:.2f} H:{high_price:.2f} L:{low_price:.2f} C:{close_price:.2f}")
        else:
            # Update existing 1-minute candle with complete OHLC data
            old_low = self.current_1min_candle.low
            old_high = self.current_1min_candle.high
            self.current_1min_candle.open = open_price
            self.current_1min_candle.high = high_price
            self.current_1min_candle.low = low_price
            self.current_1min_candle.close = close_price
            
            # Check for target/SL hits during candle formation (if in trade)
            if self.in_trade:
                # Check if target was hit (high >= target)
                if self.current_1min_candle.high >= self.current_target:
                    print(f"🎯 TARGET HIT during candle formation! High: {self.current_1min_candle.high:.2f} >= Target: {self.current_target:.2f}")
                    self.exit_trade(self.current_target, "target_hit", None)
                    return
                
                # Check if stop loss was hit (low <= stop_loss)
                if self.current_1min_candle.low <= self.current_stop_loss:
                    print(f"🛑 STOP LOSS HIT during candle formation! Low: {self.current_1min_candle.low:.2f} <= SL: {self.current_stop_loss:.2f}")
                    self.exit_trade(self.current_stop_loss, "stop_loss_hit", None)
                    return
            
            # Print if low or high changed
            if self.current_1min_candle.low < old_low:
                print(f"📉 1-Min Low Updated: {candle_start_time.strftime('%H:%M:%S')} - Old Low: {old_low:.2f} → New Low: {self.current_1min_candle.low:.2f} (Low: {low_price:.2f})")
            elif self.current_1min_candle.high > old_high:
                print(f"📈 1-Min High Updated: {candle_start_time.strftime('%H:%M:%S')} - Old High: {old_high:.2f} → New High: {self.current_1min_candle.high:.2f} (High: {high_price:.2f})")
            else:
                print(f"📊 1-Min Update: {candle_start_time.strftime('%H:%M:%S')} - H:{self.current_1min_candle.high:.2f} L:{self.current_1min_candle.low:.2f} C:{self.current_1min_candle.close:.2f}")
    
    def get_candle_type(self, candle):
        """Get the type of candle (Bull, Bear, or Neutral)"""
        if candle.is_bull_candle():
            return "BULL"
        elif candle.is_bear_candle():
            return "BEAR"
        else:
            return "NEUTRAL"
    
    def classify_and_analyze_15min_candle(self, candle):
        """Classify 15-minute candle and prepare for sweep detection"""
        candle_type = self.get_candle_type(candle)
        
        print(f"\n📊 15-Min Candle Analysis:")
        print(f"   Type: {candle_type}")
        print(f"   Open: {candle.open:.2f}, Close: {candle.close:.2f}")
        print(f"   High: {candle.high:.2f}, Low: {candle.low:.2f}")
        print(f"   Body: {candle.body_size():.2f} ({candle.body_percentage():.1f}%)")
        
        # Check if current 15-min candle closes below existing target (target invalidation)
        if self.waiting_for_sweep and self.sweep_low and candle.close < self.sweep_low:
            print(f"❌ Target invalidated! Current candle close ({candle.close:.2f}) < Target ({self.sweep_low:.2f})")
            print(f"🔄 Setting new target: {candle.low:.2f}")
            self.sweep_low = candle.low
            self.sweep_detected = False  # Reset sweep detection for new target
            self.recovery_low = None  # Reset recovery low
            self.waiting_for_sweep = True
        
        # If it's a bear or neutral candle, prepare for sweep detection
        if candle_type in ["BEAR", "NEUTRAL"]:
            # Only set new target if we don't already have one or if current candle is better
            if not self.waiting_for_sweep or not self.sweep_low or candle.low < self.sweep_low:
                self.waiting_for_sweep = True
                self.sweep_low = candle.low
                self.sweep_detected = False  # Reset sweep detection for new target
                self.recovery_low = None  # Reset recovery low
                self.sweep_target_set_time = candle.timestamp  # Record when target was set
                print(f"🎯 New target set: {self.sweep_low:.2f} at {candle.timestamp.strftime('%H:%M:%S')}")
                
                # Track bear candles for CISD
                if candle_type == "BEAR":
                    self.last_bear_candles.append(candle)
                    print(f"📝 Added bear candle to CISD tracking")
        else:
            # For bull candles, don't reset target - keep existing target active
            target_str = f"{self.sweep_low:.2f}" if self.sweep_low is not None else "None"
            print(f"📈 Bull candle - keeping existing target: {target_str}")
        
        # Check for 15m FVG and invalidate target regardless of invalidation count
        if self.waiting_for_sweep and self.sweep_low:
            fvg_15min = self.detect_15min_bullish_fvg()
            if fvg_15min:
                print(f"❌ Target invalidated! 15m FVG detected")
                print(f"🔄 Setting new target: {candle.low:.2f}")
                self.sweep_low = candle.low
                self.sweep_detected = False  # Reset sweep detection for new target
                self.recovery_low = None  # Reset recovery low
                self.waiting_for_sweep = True
                self.target_invalidation_count = 0  # Reset counter
                self.last_target_invalidation_time = candle.timestamp
    
    def check_sweep_conditions(self, one_min_candle):
        """Check if 1-minute candle sweeps the low and look for IMPS/CISD"""
        if not self.waiting_for_sweep or not self.sweep_low:
            return None
        
        # Only check for sweep in candles that come AFTER the target was set
        if self.sweep_target_set_time and one_min_candle.timestamp <= self.sweep_target_set_time:
            return None
        
        # Debug sweep checking
        print(f"DEBUG: Checking sweep - 1min low: {one_min_candle.low:.2f}, target: {self.sweep_low:.2f}, sweep: {one_min_candle.low < self.sweep_low}")
        
        # Check if this 1-minute candle sweeps the low
        if one_min_candle.low < self.sweep_low:
            if not self.sweep_detected:  # First time sweep is detected
                self.sweep_detected = True
                self.recovery_low = one_min_candle.low  # Initialize recovery low with sweep low
                
                if self.logger:
                    candle_data = {
                        'open': one_min_candle.open,
                        'high': one_min_candle.high,
                        'low': one_min_candle.low,
                        'close': one_min_candle.close
                    }
                    self.logger.log_sweep_detection(
                        self.sweep_low, one_min_candle.low, self.recovery_low, one_min_candle.timestamp, candle_data
                    )
                else:
                    print(f"\n🎯 SWEEP DETECTED!")
                    print(f"   1-Min Candle Low: {one_min_candle.low:.2f}")
                    print(f"   Target Low: {self.sweep_low:.2f}")
                    print(f"   Recovery Low: {self.recovery_low:.2f}")
                    print(f"   Sweep Time: {one_min_candle.timestamp.strftime('%H:%M:%S')}")
                    print(f"   🔍 Looking for IMPS/CISD...")
            else:
                # Update recovery low if this candle goes lower
                if one_min_candle.low < self.recovery_low:
                    self.recovery_low = one_min_candle.low
                    print(f"📉 Recovery Low Updated: {one_min_candle.low:.2f}")
        
        # Look for IMPS/CISD if we have detected a sweep and close >= recovery low
        if self.sweep_detected and one_min_candle.close >= self.recovery_low:
            print(f"🔍 Checking for IMPS/CISD - Close: {one_min_candle.close:.2f} >= Recovery Low: {self.recovery_low:.2f}")
            
            # Look for IMPS (1-minute bullish FVG)
            imps_fvg = self.detect_1min_bullish_fvg()
            if imps_fvg:
                print(f"✅ IMPS (1-Min Bullish FVG) Found!")
                print(f"   Entry: {imps_fvg['entry']:.2f}")
                print(f"   Stop Loss: {imps_fvg['stop_loss']:.2f}")
                return imps_fvg
            
            # Look for CISD (passing open of bear candles)
            cisd_trigger = self.detect_cisd()
            if cisd_trigger:
                print(f"✅ CISD (Bear Candle Open) Found!")
                print(f"   Entry: {cisd_trigger['entry']:.2f}")
                print(f"   Stop Loss: {cisd_trigger['stop_loss']:.2f}")
                return cisd_trigger
        elif self.sweep_detected:
            print(f"   ⏳ Waiting for close >= recovery low ({self.recovery_low:.2f}). Current close: {one_min_candle.close:.2f}")
        
        return None
    
    def detect_1min_bullish_fvg(self):
        """Detect 1-minute bullish Fair Value Gap"""
        if len(self.one_min_candles) < 3:
            print(f"DEBUG: Not enough 1min candles for FVG: {len(self.one_min_candles)}")
            return None
        
        # Get the last 3 1-minute candles
        c1, c2, c3 = list(self.one_min_candles)[-3:]
        print(f"DEBUG: FVG check - C1: O:{c1.open:.2f} H:{c1.high:.2f} L:{c1.low:.2f} C:{c1.close:.2f}")
        print(f"DEBUG: FVG check - C2: O:{c2.open:.2f} H:{c2.high:.2f} L:{c2.low:.2f} C:{c2.close:.2f}")
        print(f"DEBUG: FVG check - C3: O:{c3.open:.2f} H:{c3.high:.2f} L:{c3.low:.2f} C:{c3.close:.2f}")
        print(f"DEBUG: FVG condition - C3.low ({c3.low:.2f}) > C1.high ({c1.high:.2f}) = {c3.low > c1.high}")
        
        # Check for bullish FVG (c3.low > c1.high)
        if c3.low > c1.high:
            gap_size = c3.low - c1.high
            fvg = {
                'type': 'bullish',
                'gap_size': gap_size,
                'entry': c3.close,
                'stop_loss': self.recovery_low,  # Stop loss is the lowest point (recovery low)
                'candles': [c1, c2, c3]
            }
            
            if self.logger:
                self.logger.log_fvg_detection(gap_size, c3.close, self.recovery_low, [c1, c2, c3])
            else:
                print(f"   FVG Gap Size: {gap_size:.2f}")
                print(f"   Stop Loss (Recovery Low): {self.recovery_low:.2f}")
            
            return fvg
        else:
            print(f"   ❌ No FVG - C3.low ({c3.low:.2f}) <= C1.high ({c1.high:.2f})")
        
        return None
    
    def detect_15min_bullish_fvg(self):
        """Detect 15-minute bullish Fair Value Gap"""
        if len(self.fifteen_min_candles) < 3:
            print(f"DEBUG: Not enough 15min candles for FVG: {len(self.fifteen_min_candles)}")
            return None
        
        # Get the last 3 15-minute candles
        c1, c2, c3 = list(self.fifteen_min_candles)[-3:]
        print(f"DEBUG: 15min FVG check - C1: O:{c1.open:.2f} H:{c1.high:.2f} L:{c1.low:.2f} C:{c1.close:.2f}")
        print(f"DEBUG: 15min FVG check - C2: O:{c2.open:.2f} H:{c2.high:.2f} L:{c2.low:.2f} C:{c2.close:.2f}")
        print(f"DEBUG: 15min FVG check - C3: O:{c3.open:.2f} H:{c3.high:.2f} L:{c3.low:.2f} C:{c3.close:.2f}")
        print(f"DEBUG: 15min FVG condition - C3.low ({c3.low:.2f}) > C1.high ({c1.high:.2f}) = {c3.low > c1.high}")
        
        # Check for bullish FVG (c3.low > c1.high)
        if c3.low > c1.high:
            gap_size = c3.low - c1.high
            fvg = {
                'type': '15min_bullish',
                'gap_size': gap_size,
                'entry': c3.close,
                'stop_loss': c3.low,  # Stop loss is the low of the third candle
                'candles': [c1, c2, c3]
            }
            
            if self.logger:
                self.logger.log_fvg_detection(gap_size, c3.close, c3.low, [c1, c2, c3])
            else:
                print(f"   15min FVG Gap Size: {gap_size:.2f}")
                print(f"   Stop Loss (C3 Low): {c3.low:.2f}")
            
            return fvg
        else:
            print(f"   ❌ No 15min FVG - C3.low ({c3.low:.2f}) <= C1.high ({c1.high:.2f})")
        
        return None
    
    def detect_cisd(self):
        """Detect CISD - Change in State of Delivery"""
        if not self.last_bear_candles:
            return None
        
        # Get current price (use the latest 1-minute candle close)
        if not self.current_1min_candle:
            return None
        
        current_price = self.current_1min_candle.close
        
        # Check if current price passes the open of any bear candle
        for bear_candle in reversed(self.last_bear_candles):  # Check most recent first
            if current_price > bear_candle.open:
                # Find the lowest low among all tracked bear candles
                lowest_bear_low = min([candle.low for candle in self.last_bear_candles])
                
                cisd_trigger = {
                    'type': 'CISD',
                    'entry': current_price,
                    'stop_loss': lowest_bear_low,  # Stop loss is low of lowest tracked bear candle
                    'bear_candle': bear_candle,
                    'lowest_bear_low': lowest_bear_low
                }
                
                print(f"   CISD: Price {current_price:.2f} > Bear Open {bear_candle.open:.2f}")
                print(f"   Stop Loss (Lowest Bear Low): {lowest_bear_low:.2f}")
                
                if self.logger:
                    self.logger.log_cisd_detection(current_price, lowest_bear_low, bear_candle.open, bear_candle)
                
                return cisd_trigger
        
        return None
    
    def reset_sweep_detection(self):
        """Reset sweep detection after entering trade"""
        self.waiting_for_sweep = False
        self.sweep_detected = False
        self.sweep_low = None
        self.recovery_low = None
        self.sweep_target_set_time = None
    
    def get_strategy_status(self):
        """Get current strategy status for monitoring"""
        return {
            'waiting_for_sweep': self.waiting_for_sweep,
            'sweep_low': self.sweep_low,
            'recovery_low': self.recovery_low,
            'sweep_detected': self.sweep_detected,
            'fifteen_min_candles_count': len(self.fifteen_min_candles),
            'one_min_candles_count': len(self.one_min_candles),
            'bear_candles_tracked': len(self.last_bear_candles),
            'in_trade': self.in_trade,
            'entry_price': self.entry_price,
            'current_stop_loss': self.current_stop_loss,
            'current_target': self.current_target,
            'swing_lows_count': len(self.swing_lows)
        }
    
    def enter_trade(self, entry_price, stop_loss, target):
        """Enter a trade and set initial parameters"""
        self.in_trade = True
        self.entry_price = entry_price
        self.current_stop_loss = stop_loss
        self.current_target = target
        
        if self.logger:
            self.logger.log_trade_entry(
                entry_price, stop_loss, target,
                "STRATEGY", "N/A"
            )
        else:
            print(f"🎯 TRADE ENTERED!")
            print(f"   Entry: {entry_price:.2f}")
            print(f"   Stop Loss: {stop_loss:.2f}")
            print(f"   Target: {target:.2f}")
            print(f"   Risk: {entry_price - stop_loss:.2f}")
            print(f"   Reward: {target - entry_price:.2f}")
            print(f"   RR Ratio: {(target - entry_price) / (entry_price - stop_loss):.2f}")
    
    def exit_trade(self, exit_price, reason, account_balance=None):
        """Exit a trade and reset parameters"""
        if self.in_trade:
            pnl = exit_price - self.entry_price
            
            if self.logger:
                self.logger.log_trade_exit(exit_price, reason, self.entry_price, pnl, account_balance)
            else:
                print(f"🚪 TRADE EXITED - {reason}")
                print(f"   Entry: {self.entry_price:.2f}")
                print(f"   Exit: {exit_price:.2f}")
                print(f"   P&L: {pnl:.2f}")
                if account_balance is not None:
                    print(f"   Account Balance: ₹{account_balance:.2f}")
            
            # Reset trade parameters
            self.in_trade = False
            self.entry_price = None
            self.current_stop_loss = None
            self.current_target = None
            self.swing_lows.clear()
            
            # Reset sweep detection for next trade
            self.reset_sweep_detection()
            
            # Notify callback if provided
            if self.exit_callback:
                self.exit_callback(exit_price, reason)
    
    def detect_swing_low(self, candle_index):
        """Detect if a candle at given index is a swing low"""
        if len(self.one_min_candles) < (2 * self.swing_look_back + 1):
            return False
        
        current_candle = list(self.one_min_candles)[candle_index]
        current_low = current_candle.low
        
        # Check if current low is lower than previous N candles
        for i in range(1, self.swing_look_back + 1):
            if candle_index - i < 0:
                return False
            prev_candle = list(self.one_min_candles)[candle_index - i]
            if current_low >= prev_candle.low:
                return False
        
        # Check if current low is lower than next N candles
        for i in range(1, self.swing_look_back + 1):
            if candle_index + i >= len(self.one_min_candles):
                return False
            next_candle = list(self.one_min_candles)[candle_index + i]
            if current_low >= next_candle.low:
                return False
        
        return True
    
    def update_swing_lows(self):
        """Update swing lows list when in trade"""
        if not self.in_trade or len(self.one_min_candles) < (2 * self.swing_look_back + 1):
            return
        
        # Check the most recent completed candle for swing low
        recent_index = len(self.one_min_candles) - self.swing_look_back - 1
        if recent_index >= 0 and self.detect_swing_low(recent_index):
            swing_low_candle = list(self.one_min_candles)[recent_index]
            self.swing_lows.append({
                'price': swing_low_candle.low,
                'timestamp': swing_low_candle.timestamp
            })
            
            if self.logger:
                self.logger.log_swing_low_detection(swing_low_candle.low, swing_low_candle.timestamp)
            else:
                print(f"📉 Swing Low Detected: {swing_low_candle.low:.2f} at {swing_low_candle.timestamp.strftime('%H:%M:%S')}")
    
    def should_move_stop_loss(self, current_price):
        """Check if stop loss should be moved based on 50% profit rule"""
        if not self.in_trade or not self.entry_price or not self.current_stop_loss:
            return False
        
        # Calculate profit percentage
        profit = current_price - self.entry_price
        risk = self.entry_price - self.current_stop_loss
        profit_percentage = profit / risk if risk > 0 else 0
        
        return profit_percentage >= 0.5  # 50% profit
    
    def should_move_stop_loss_continuously(self):
        """Check if stop loss should be moved continuously to new swing lows"""
        if not self.in_trade or not self.swing_lows:
            return False
        
        # Always move SL to latest swing low if it's higher than current SL
        latest_swing_low = self.swing_lows[-1]['price']
        return latest_swing_low > self.current_stop_loss
    
    def move_stop_loss_to_swing_low(self):
        """Move stop loss to the latest swing low"""
        if not self.in_trade or not self.swing_lows:
            return False
        
        latest_swing_low = self.swing_lows[-1]['price']
        if latest_swing_low > self.current_stop_loss:
            old_stop_loss = self.current_stop_loss
            self.current_stop_loss = latest_swing_low
            
            if self.logger:
                self.logger.log_stop_loss_movement(old_stop_loss, self.current_stop_loss, "swing_low")
            else:
                print(f"🔄 Stop Loss Moved: {old_stop_loss:.2f} → {self.current_stop_loss:.2f}")
            
            return True
        
        return False
    
    def check_trade_exit(self, current_price):
        """Check if trade should be exited (stop loss or target hit)"""
        if not self.in_trade:
            return None
        
        # Check stop loss
        if current_price <= self.current_stop_loss:
            return {'action': 'exit', 'reason': 'stop_loss', 'price': self.current_stop_loss}
        
        # Check target
        if current_price >= self.current_target:
            return {'action': 'exit', 'reason': 'target', 'price': self.current_target}
        
        return None
