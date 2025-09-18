"""
Position Manager for handling position tracking, risk management, and order management
"""

import time
from datetime import datetime
from utils.market_utils import round_to_tick

class PositionManager:
    """Manages trading positions, orders, and risk management"""
    
    def __init__(self, broker, account_manager, tick_size=0.05, instruments_df=None):
        self.instruments_df = instruments_df
        self.broker = broker
        self.account_manager = account_manager
        self.tick_size = tick_size
        
        # Position tracking
        self.is_trading = False
        self.current_position = None
        self.active_orders = {}  # Track all active orders
        self.last_order_time = None  # Track last order placement time
        self.current_symbol = None  # Track current trading symbol
        
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
    
    def enter_trade_with_trigger(self, trigger, trigger_type, symbol):
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
            # Store current symbol
            self.current_symbol = symbol
            
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
                instruments_df=self.instruments_df
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
    
    def close_position(self, symbol, current_price=None):
        """Close a specific position by symbol at current market price"""
        try:
            # Get current positions
            positions = self.broker.get_positions()
            
            if symbol not in positions:
                print(f"No position found for symbol: {symbol}")
                return False, None, None
            
            position = positions[symbol]
            quantity = position['quantity']
            
            if quantity == 0:
                print(f"No quantity to close for symbol: {symbol}")
                return False, None, None
            
            # Get current market price if not provided
            if current_price is None:
                try:
                    # Try to get current price from broker
                    if hasattr(self.broker, 'get_current_price'):
                        current_price = self.broker.get_current_price(symbol)
                    else:
                        # Fallback to position average price
                        current_price = position.get('average_price', position.get('price', 0))
                        print(f"⚠️ Using position average price as current price: {current_price}")
                except Exception as e:
                    print(f"⚠️ Could not get current price: {e}")
                    current_price = position.get('average_price', position.get('price', 0))
            
            # Debug: Print position structure
            print(f"DEBUG: Position structure for {symbol}: {position}")
            print(f"Current market price: {current_price}")
            
            # Determine side (BUY to close SELL position, SELL to close BUY position)
            position_side = position.get('side', 'LONG')
            
            # Handle different position side formats
            if position_side in ['BUY', 'LONG']:
                side = "SELL"
            elif position_side in ['SELL', 'SHORT']:
                side = "BUY"
            else:
                # If we can't determine the side, try to infer from quantity
                if quantity > 0:
                    side = "SELL"  # Close long position
                else:
                    side = "BUY"   # Close short position
                print(f"⚠️ Unknown position side '{position_side}', inferred side: {side}")
            
            print(f"Closing position: {symbol} - {quantity} qty @ {side} (Market Price: {current_price})")
            
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
                return True, current_price, abs(quantity)
            else:
                print(f"❌ Failed to place position close order: {symbol}")
                return False, None, None
                
        except Exception as e:
            print(f"Error closing position {symbol}: {e}")
            return False, None, None
    
    def close_all_positions(self, account_manager=None):
        """Close all open positions and calculate P&L"""
        try:
            closed_positions = []
            total_pnl = 0.0
            
            print(f"🔄 Closing all positions...")
            
            # First, check if we have a current position in position manager
            if self.current_position and self.is_trading:
                print(f"📊 Found current position in position manager:")
                print(f"   Symbol: {self.current_symbol or 'Unknown'}")
                print(f"   Entry Price: {self.current_position.get('entry_price', 'Unknown')}")
                print(f"   Quantity: {self.current_position.get('quantity', 'Unknown')}")
                print(f"   Lots: {self.current_position.get('lots', 'Unknown')}")
                
                # Use position manager's current position data
                symbol = self.current_symbol or 'Unknown'
                entry_price = self.current_position.get('entry_price', 0)
                quantity = self.current_position.get('quantity', 0)
                lots = self.current_position.get('lots', 0)
                
                if quantity > 0:
                    print(f"📊 Closing current position: {symbol} - {quantity} qty")
                    
                    # Close the position
                    success, exit_price, closed_qty = self.close_position(symbol)
                    
                    if success and exit_price and closed_qty:
                        # Calculate P&L using position manager data
                        if account_manager:
                            # Determine if it's a buy or sell trade
                            is_buy = True  # Assuming buy trades for now
                            
                            print(f"🔍 P&L Calculation Debug:")
                            print(f"   Entry Price: {entry_price}")
                            print(f"   Exit Price: {exit_price}")
                            print(f"   Closed Qty: {closed_qty}")
                            print(f"   Lot Size: {account_manager.config.lot_size}")
                            print(f"   Calculated Lots: {lots}")
                            print(f"   Is Buy: {is_buy}")
                            
                            pnl = account_manager.calculate_pnl(
                                entry_price=entry_price,
                                exit_price=exit_price,
                                lots=lots,
                                is_buy=is_buy
                            )
                            
                            print(f"   Calculated P&L: {pnl}")
                            total_pnl += pnl
                            
                            print(f"💰 Position P&L: ₹{pnl:.2f} (Entry: {entry_price:.2f} → Exit: {exit_price:.2f})")
                        
                        closed_positions.append({
                            'symbol': symbol,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'quantity': closed_qty,
                            'pnl': pnl if account_manager else 0
                        })
                    else:
                        print(f"❌ Failed to close position: {symbol}")
            else:
                # Fallback to broker positions if no current position
                print(f"ℹ️ No current position in position manager, checking broker positions...")
                positions = self.broker.get_positions()
                
                for symbol, position in positions.items():
                    quantity = position.get('quantity', 0)
                    if quantity != 0:
                        print(f"📊 Found open position: {symbol} - {quantity} qty")
                        
                        # Get entry price for P&L calculation
                        # Try multiple field names for compatibility
                        entry_price = (position.get('average_price') or 
                                     position.get('avgPrice') or 
                                     position.get('price') or 
                                     position.get('avg_price') or 0)
                        
                        print(f"🔍 Position fields: {list(position.keys())}")
                        print(f"🔍 Entry price lookup: average_price={position.get('average_price')}, avgPrice={position.get('avgPrice')}, price={position.get('price')}, avg_price={position.get('avg_price')}")
                        print(f"🔍 Final entry price: {entry_price}")
                        
                        # Close the position
                        success, exit_price, closed_qty = self.close_position(symbol)
                        
                        if success and exit_price and closed_qty:
                            # Calculate P&L
                            if account_manager:
                                # Determine if it's a buy or sell trade
                                position_side = position.get('side', 'LONG')
                                is_buy = position_side in ['BUY', 'LONG'] or quantity > 0
                                
                                lots = closed_qty // account_manager.config.lot_size
                                print(f"🔍 P&L Calculation Debug:")
                                print(f"   Entry Price: {entry_price}")
                                print(f"   Exit Price: {exit_price}")
                                print(f"   Closed Qty: {closed_qty}")
                                print(f"   Lot Size: {account_manager.config.lot_size}")
                                print(f"   Calculated Lots: {lots}")
                                print(f"   Is Buy: {is_buy}")
                                
                                pnl = account_manager.calculate_pnl(
                                    entry_price=entry_price,
                                    exit_price=exit_price,
                                    lots=lots,
                                    is_buy=is_buy
                                )
                                
                                print(f"   Calculated P&L: {pnl}")
                                total_pnl += pnl
                                
                                print(f"💰 Position P&L: ₹{pnl:.2f} (Entry: {entry_price:.2f} → Exit: {exit_price:.2f})")
                            
                            closed_positions.append({
                                'symbol': symbol,
                                'entry_price': entry_price,
                                'exit_price': exit_price,
                                'quantity': closed_qty,
                                'pnl': pnl if account_manager else 0
                            })
                        else:
                            print(f"❌ Failed to close position: {symbol}")
            
            if closed_positions:
                print(f"✅ Closed {len(closed_positions)} positions")
                if account_manager:
                    print(f"💰 Total P&L from forced closure: ₹{total_pnl:.2f}")
                    account_manager.update_balance(total_pnl)
            else:
                print("ℹ️ No open positions to close")
            
            return closed_positions, total_pnl
            
        except Exception as e:
            print(f"Error closing all positions: {e}")
            return [], 0.0
    
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
