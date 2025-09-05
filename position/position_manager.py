"""
Position Manager for handling position tracking, risk management, and order management
"""

import time
from datetime import datetime
from utils.market_utils import round_to_tick

class PositionManager:
    """Manages trading positions, orders, and risk management"""
    
    def __init__(self, broker, account_manager, tick_size=0.05):
        self.broker = broker
        self.account_manager = account_manager
        self.tick_size = tick_size
        
        # Position tracking
        self.is_trading = False
        self.current_position = None
        self.active_orders = {}  # Track all active orders
        self.last_order_time = None  # Track last order placement time
        
        # Risk management parameters
        self.initial_risk_reward = 1.0  # default 1:1
        self.target_update_50_percent = 0.5  # 50% move
        self.target_update_100_percent = 1.0  # 100% move
    
    def check_existing_orders(self):
        """Check if there are any existing active orders"""
        return len(self.active_orders) > 0 or self.is_trading
    
    def validate_order_state(self):
        """Validate that order state is consistent"""
        # Check if we have active orders but not trading flag
        if len(self.active_orders) > 0 and not self.is_trading:
            print("⚠️ WARNING: Active orders found but trading flag is False")
            return False
            
        # Check if we have trading flag but no active orders
        if self.is_trading and len(self.active_orders) == 0:
            print("⚠️ WARNING: Trading flag is True but no active orders")
            return False
            
        # Check if we have multiple active orders
        if len(self.active_orders) > 1:
            print(f"⚠️ WARNING: Multiple active orders detected: {len(self.active_orders)}")
            return False
            
        return True
    
    def cleanup_orphaned_orders(self):
        """Clean up any orphaned orders that might exist"""
        if len(self.active_orders) > 0:
            print(f"🧹 Cleaning up {len(self.active_orders)} orphaned orders...")
            for order_id in list(self.active_orders.keys()):
                try:
                    cancel_result = self.broker.cancel_order(order_id)
                    if cancel_result:
                        print(f"✅ Cancelled orphaned order: {order_id}")
                    else:
                        print(f"❌ Failed to cancel orphaned order: {order_id}")
                except Exception as e:
                    print(f"❌ Error cancelling orphaned order {order_id}: {e}")
                    
            # Reset state
            self.active_orders.clear()
            self.is_trading = False
            self.current_position = None
            print("✅ Order cleanup completed")
    
    def enter_trade_with_trigger(self, trigger, trigger_type, symbol, instruments_df):
        """Enter trade based on IMPS or CISD trigger with account manager integration"""
        # Check if we're already trading
        if self.is_trading:
            print("🚫 Already in a trade, skipping new entry")
            return False
        
        # Check for existing orders
        if self.check_existing_orders():
            print("🚫 Existing orders detected, skipping new entry")
            return False
        
        # Validate order state
        if not self.validate_order_state():
            print("🚫 Invalid order state detected, cleaning up...")
            self.cleanup_orphaned_orders()
            return False
        
        # Check if enough time has passed since last order (prevent rapid orders)
        current_time = time.time()
        if (self.last_order_time and 
            current_time - self.last_order_time < 5):  # 5 second cooldown
            print("🚫 Order cooldown period, skipping new entry")
            return False
        
        try:
            # Calculate entry, stop loss, and take profit with price rounding
            entry_price = round_to_tick(trigger['entry'], self.tick_size)
            stop_loss = round_to_tick(trigger['stop_loss'], self.tick_size)
            
            # Use account manager to calculate trade parameters
            can_trade, lots, actual_sl_amount, max_loss_per_lot = self.account_manager.calculate_trade_parameters(
                entry_price, stop_loss
            )
            
            if not can_trade:
                print("❌ Trade rejected by account manager")
                return False
            
            # Calculate quantity based on lots
            quantity = lots * self.account_manager.config.lot_size
            
            # Calculate risk (entry - stop loss)
            risk = entry_price - stop_loss
            
            # Calculate take profit with 2:1 risk:reward ratio for IMPS and CISD
            target_rr = 2.0  # Fixed 2:1 risk:reward for both IMPS and CISD
            take_profit = round_to_tick(entry_price + (risk * target_rr), self.tick_size)
            
            # Deduct the investment amount from account balance
            total_investment = quantity * entry_price
            self.account_manager.deduct_investment(total_investment)
            
            # Place buy order with target and stop loss
            print(f"\n=== ENTERING TRADE ({trigger_type}) ===")
            print(f"Trigger Type: {trigger_type}")
            print(f"Entry Price: ₹{entry_price:.2f}")
            print(f"Stop Loss: ₹{stop_loss:.2f}")
            print(f"Take Profit: ₹{take_profit:.2f}")
            print(f"Lots: {lots}")
            print(f"Quantity: {quantity}")
            print(f"Risk per Lot: ₹{max_loss_per_lot:.2f}")
            print(f"Total Risk: ₹{actual_sl_amount:.2f}")
            print(f"Total Investment: ₹{quantity * entry_price:.2f}")
            print(f"Risk: {risk:.2f}")
            print(f"Reward: {risk * target_rr:.2f}")
            print(f"Risk:Reward = 1:{target_rr}")
            
            # Place order with target and stop loss in a single call
            buy_order = self.broker.place_order(
                symbol=symbol, 
                quantity=quantity, 
                order_type="MARKET", 
                side="BUY",
                target_price=take_profit,
                stop_loss_price=stop_loss,
                instruments_df=instruments_df
            )
            
            if not buy_order:
                print("❌ Failed to place buy order")
                return False
            
            # Update order tracking
            order_id = buy_order.get('orderId')
            if order_id:
                self.active_orders[order_id] = {
                    'type': 'BUY',
                    'symbol': symbol,
                    'quantity': quantity,
                    'lots': lots,
                    'entry_price': entry_price,
                    'target_price': take_profit,
                    'stop_loss_price': stop_loss,
                    'status': 'PLACED',
                    'timestamp': current_time,
                    'trigger_type': trigger_type
                }
            
            self.is_trading = True
            self.last_order_time = current_time
            self.current_position = {
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'quantity': quantity,
                'lots': lots,
                'buy_order_id': order_id,
                'risk': risk,
                'reward': risk * target_rr,
                'current_risk_reward': target_rr,
                'target_updated_50': False,
                'target_updated_100': False,
                'max_price_reached': entry_price,
                'trigger_type': trigger_type,
                'actual_sl_amount': actual_sl_amount,
                'max_loss_per_lot': max_loss_per_lot
            }
            
            print(f"✅ Trade entered successfully!")
            print(f"Buy Order ID: {order_id}")
            print(f"Target Price: ₹{take_profit:.2f}")
            print(f"Stop Loss Price: ₹{stop_loss:.2f}")
            print(f"Active Orders: {len(self.active_orders)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error entering trade: {e}")
            # Reset state on error
            self.is_trading = False
            self.current_position = None
            return False
    
    def check_and_update_target(self, current_price):
        """Check if price has moved enough to update target (50% and 100% moves)"""
        if not self.is_trading or not self.current_position:
            return
        
        # Round current price to tick size
        current_price = round_to_tick(current_price, self.tick_size)
        
        # Update max price reached
        if current_price > self.current_position['max_price_reached']:
            self.current_position['max_price_reached'] = current_price
        
        entry_price = self.current_position['entry_price']
        risk = self.current_position['risk']
        
        # Calculate how much price has moved in our favor
        price_move = current_price - entry_price
        price_move_percent = float(price_move / risk) if risk > 0 else 0
        
        # Check for 50% move (0.5 * risk)
        if (price_move_percent >= self.target_update_50_percent and 
            not self.current_position['target_updated_50']):
            
            # Update target to 1:2 risk:reward
            new_target = round_to_tick(entry_price + (risk * 2.0), self.tick_size)
            print(f"\n=== TARGET UPDATE: 50% MOVE DETECTED ===")
            print(f"Current Price: ₹{current_price:.2f}")
            print(f"Price Move: ₹{price_move:.2f} ({price_move_percent:.1%} of risk)")
            print(f"Old Target: ₹{self.current_position['take_profit']:.2f} (1:{self.current_position['current_risk_reward']:.1f})")
            print(f"New Target: ₹{new_target:.2f} (1:2.0)")
            
            # Modify the order target
            modify_response = self.broker.modify_target(
                self.current_position['buy_order_id'],
                new_target
            )
            
            if modify_response:
                self.current_position['take_profit'] = new_target
                self.current_position['current_risk_reward'] = 2.0
                self.current_position['target_updated_50'] = True
                print(f"✅ Target updated to 1:2.0 successfully!")
            else:
                print(f"❌ Failed to update target to 1:2.0")
        
        # Check for 100% move (1.0 * risk)
        elif (price_move_percent >= self.target_update_100_percent and 
              not self.current_position['target_updated_100']):
            
            # Update target to 1:4 risk:reward
            new_target = round_to_tick(entry_price + (risk * 4.0), self.tick_size)
            print(f"\n=== TARGET UPDATE: 100% MOVE DETECTED ===")
            print(f"Current Price: ₹{current_price:.2f}")
            print(f"Price Move: ₹{price_move:.2f} ({price_move_percent:.1%} of risk)")
            print(f"Old Target: ₹{self.current_position['take_profit']:.2f} (1:{self.current_position['current_risk_reward']:.1f})")
            print(f"New Target: ₹{new_target:.2f} (1:4.0)")
            
            # Modify the order target
            modify_response = self.broker.modify_target(
                self.current_position['buy_order_id'],
                new_target
            )
            
            if modify_response:
                self.current_position['take_profit'] = new_target
                self.current_position['current_risk_reward'] = 4.0
                self.current_position['target_updated_100'] = True
                print(f"✅ Target updated to 1:4.0 successfully!")
            else:
                print(f"❌ Failed to update target to 1:4.0")
    
    def update_trailing_stop(self, current_price, new_stop_loss):
        """Update trailing stop loss based on new FVGs"""
        if not self.is_trading or not self.current_position:
            return
        
        if new_stop_loss > self.current_position['stop_loss']:
            # Update the stop loss using modify_stop_loss
            print(f"\n=== UPDATING TRAILING STOP ===")
            print(f"Old Stop Loss: ₹{self.current_position['stop_loss']:.2f}")
            print(f"New Stop Loss: ₹{new_stop_loss:.2f}")
            
            # Modify the existing order with new stop loss
            modify_response = self.broker.modify_stop_loss(
                self.current_position['buy_order_id'],
                new_stop_loss
            )
            
            if modify_response:
                # Update position details
                self.current_position['stop_loss'] = new_stop_loss
                print(f"Trailing stop updated successfully!")
                print(f"New Stop Loss: ₹{new_stop_loss:.2f}")
            else:
                print("Failed to update trailing stop")
    
    def handle_trade_exit(self, exit_price, exit_reason):
        """Handle automatic trade exit (stop loss or target hit) with account manager integration"""
        if not self.is_trading or not self.current_position:
            return True
        
        print(f"\n=== TRADE EXIT DETECTED ===")
        print(f"Exit Reason: {exit_reason}")
        print(f"Exit Price: ₹{exit_price:.2f}")
        print(f"Entry Price: ₹{self.current_position['entry_price']:.2f}")
        
        # Calculate P&L using account manager
        entry_price = self.current_position['entry_price']
        lots = self.current_position['lots']
        pnl = self.account_manager.calculate_pnl(entry_price, exit_price, lots)
        
        print(f"P&L: ₹{pnl:.2f}")
        
        # Log comprehensive trade summary using account manager
        self.account_manager.log_trade_summary(
            entry_price=entry_price,
            exit_price=exit_price,
            lots=lots,
            stop_loss=self.current_position['stop_loss'],
            target=self.current_position['take_profit'],
            reason=exit_reason
        )
        
        # Clean up all state
        self.is_trading = False
        self.current_position = None
        self.active_orders.clear()
        
        print(f"✅ Position manager state reset. Active Orders: {len(self.active_orders)}")
        return True
    
    def close_position(self, symbol):
        """Close a specific position by symbol"""
        try:
            # Get current positions
            positions = self.broker.get_positions()
            
            if symbol not in positions:
                print(f"No position found for symbol: {symbol}")
                return False
            
            position = positions[symbol]
            quantity = position['quantity']
            
            if quantity == 0:
                print(f"No quantity to close for symbol: {symbol}")
                return False
            
            # Determine side (BUY to close SELL position, SELL to close BUY position)
            side = "SELL" if position['side'] == "BUY" else "BUY"
            
            print(f"Closing position: {symbol} - {quantity} qty @ {side}")
            
            # Place closing order
            order_result = self.broker.place_order(
                symbol=symbol,
                quantity=abs(quantity),
                order_type="MARKET",
                side=side,
                instruments_df=getattr(self.broker, 'instruments_df', None)
            )
            
            if order_result:
                print(f"✅ Position close order placed successfully: {symbol}")
                return True
            else:
                print(f"❌ Failed to place position close order: {symbol}")
                return False
                
        except Exception as e:
            print(f"Error closing position {symbol}: {e}")
            return False
    
    def display_order_status(self):
        """Display current order status for monitoring"""
        print(f"\n📊 ORDER STATUS REPORT")
        print(f"{'='*50}")
        print(f"Trading Flag: {'✅ ACTIVE' if self.is_trading else '❌ INACTIVE'}")
        print(f"Active Orders: {len(self.active_orders)}")
        print(f"Current Position: {'✅ EXISTS' if self.current_position else '❌ NONE'}")
        print(f"Account Balance: ₹{self.account_manager.get_current_balance():,.2f}")
        
        if self.active_orders:
            print(f"\nActive Orders Details:")
            for order_id, order_info in self.active_orders.items():
                print(f"  Order ID: {order_id}")
                print(f"    Type: {order_info.get('type', 'UNKNOWN')}")
                print(f"    Symbol: {order_info.get('symbol', 'UNKNOWN')}")
                print(f"    Quantity: {order_info.get('quantity', 'UNKNOWN')}")
                print(f"    Lots: {order_info.get('lots', 'UNKNOWN')}")
                print(f"    Status: {order_info.get('status', 'UNKNOWN')}")
                print(f"    Timestamp: {datetime.fromtimestamp(order_info.get('timestamp', 0)).strftime('%H:%M:%S')}")
                
        if self.current_position:
            print(f"\nCurrent Position Details:")
            print(f"  Entry Price: ₹{self.current_position.get('entry_price', 'UNKNOWN'):.2f}")
            print(f"  Stop Loss: ₹{self.current_position.get('stop_loss', 'UNKNOWN'):.2f}")
            print(f"  Take Profit: ₹{self.current_position.get('take_profit', 'UNKNOWN'):.2f}")
            print(f"  Lots: {self.current_position.get('lots', 'UNKNOWN')}")
            print(f"  Quantity: {self.current_position.get('quantity', 'UNKNOWN')}")
            print(f"  Risk:Reward: 1:{self.current_position.get('current_risk_reward', 'UNKNOWN'):.1f}")
            print(f"  Target Updated 50%: {'✅' if self.current_position.get('target_updated_50', False) else '❌'}")
            print(f"  Target Updated 100%: {'✅' if self.current_position.get('target_updated_100', False) else '❌'}")
            print(f"  Max Price Reached: ₹{self.current_position.get('max_price_reached', 'UNKNOWN'):.2f}")
            print(f"  Trigger Type: {self.current_position.get('trigger_type', 'UNKNOWN')}")
            print(f"  Actual SL Amount: ₹{self.current_position.get('actual_sl_amount', 'UNKNOWN'):.2f}")
            print(f"  Max Loss per Lot: ₹{self.current_position.get('max_loss_per_lot', 'UNKNOWN'):.2f}")
            
        print(f"{'='*50}")
    
    def periodic_order_validation(self):
        """Periodically validate order state and clean up if needed"""
        try:
            # Display current status
            self.display_order_status()
            
            # Validate order state
            if not self.validate_order_state():
                print("🔄 Periodic validation: Invalid order state detected, cleaning up...")
                self.cleanup_orphaned_orders()
                return
                
            # Check for stale orders (older than 30 minutes)
            current_time = time.time()
            stale_orders = []
            
            for order_id, order_info in self.active_orders.items():
                if current_time - order_info.get('timestamp', 0) > 1800:  # 30 minutes
                    stale_orders.append(order_id)
                        
            if stale_orders:
                print(f"🔄 Periodic validation: Found {len(stale_orders)} stale orders, cleaning up...")
                for order_id in stale_orders:
                    try:
                        cancel_result = self.broker.cancel_order(order_id)
                        if cancel_result:
                            print(f"✅ Cancelled stale order: {order_id}")
                            if order_id in self.active_orders:
                                del self.active_orders[order_id]
                        else:
                            print(f"❌ Failed to cancel stale order: {order_id}")
                    except Exception as e:
                        print(f"❌ Error cancelling stale order {order_id}: {e}")
            else:
                print("✅ Periodic validation: All orders are valid")
                        
        except Exception as e:
            print(f"❌ Error in periodic order validation: {e}")
