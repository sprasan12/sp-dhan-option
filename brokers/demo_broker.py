"""
Demo broker for virtual trading and P&L calculation
"""

import time
import json
from datetime import datetime
from typing import Dict, List, Optional
from utils.market_utils import round_to_tick

class DemoBroker:
    """Demo broker for virtual trading and backtesting"""
    
    def __init__(self, tick_size: float = 0.05, account_manager=None):
        self.tick_size = tick_size
        self.account_manager = account_manager
        
        # Virtual account state - use account manager if provided
        if account_manager:
            self.virtual_balance = account_manager.get_current_balance()
        else:
            self.virtual_balance = 100000  # Fallback starting balance
            
        self.positions = {}  # Current open positions
        self.order_history = []  # All orders placed
        self.trade_history = []  # Completed trades with P&L
        
        # Order tracking
        self.order_id_counter = 0
        
        print(f"Demo Broker initialized with virtual balance: ₹{self.virtual_balance:,.2f}")
    
    def get_security_id(self, symbol: str, instruments_df=None):
        """Get Security ID for a given symbol (demo version)"""
        # In demo mode, we don't need real security IDs
        # Just return a hash of the symbol for consistency
        return hash(symbol) % 1000000
    
    def get_account_balance(self) -> float:
        """Get current virtual account balance"""
        if self.account_manager:
            return self.account_manager.get_current_balance()
        return self.virtual_balance
    
    def place_order(self, symbol: str, quantity: int, order_type: str = "MARKET", 
                   side: str = "BUY", price: float = 0, target_price: float = None, 
                   stop_loss_price: float = None, trailing_jump: float = None, 
                   instruments_df=None) -> Dict:
        """Place a virtual order"""
        try:
            # Generate order ID
            self.order_id_counter += 1
            order_id = f"DEMO_ORDER_{self.order_id_counter}"
            
            # Create order object
            order = {
                "orderId": order_id,
                "symbol": symbol,
                "quantity": quantity,
                "orderType": order_type,
                "side": side,
                "price": round_to_tick(price, self.tick_size) if price > 0 else 0,
                "targetPrice": round_to_tick(target_price, self.tick_size) if target_price else None,
                "stopLossPrice": round_to_tick(stop_loss_price, self.tick_size) if stop_loss_price else None,
                "trailingJump": trailing_jump,
                "status": "PENDING",
                "timestamp": datetime.now(),
                "filledPrice": None,
                "filledQuantity": 0
            }
            
            # Simulate order execution (immediate fill for demo)
            if order_type == "MARKET":
                # For demo, we'll use a placeholder price
                # In real implementation, this would come from current market price
                order["filledPrice"] = order["price"] if order["price"] > 0 else 100.0
                order["filledQuantity"] = quantity
                order["status"] = "FILLED"
                
                # For demo trading, we don't deduct balance on BUY orders
                # The balance will be updated when the position is closed (SELL)
                # This simulates margin trading where you don't need full cash upfront
                
                # Track position
                self._update_position(order)
            
            # Add to order history
            self.order_history.append(order)
            
            print(f"Demo Order Placed: {order_id}")
            print(f"  Symbol: {symbol}")
            print(f"  Side: {side}")
            print(f"  Quantity: {quantity}")
            print(f"  Price: ₹{order['filledPrice']:.2f}")
            print(f"  Order Value: ₹{order['filledPrice'] * quantity:.2f}")
            print(f"  Virtual Balance: ₹{self.get_account_balance():,.2f}")
            
            return {
                "orderId": order_id,
                "status": "SUCCESS",
                "message": "Order placed successfully (Demo)",
                "order": order
            }
            
        except Exception as e:
            print(f"Error placing demo order: {e}")
            return {
                "orderId": None,
                "status": "FAILED",
                "message": str(e)
            }
    
    def _update_position(self, order: Dict):
        """Update virtual position tracking"""
        symbol = order["symbol"]
        side = order["side"]
        quantity = order["filledQuantity"]
        price = order["filledPrice"]
        
        if symbol not in self.positions:
            self.positions[symbol] = {
                "quantity": 0,
                "avgPrice": 0,
                "totalValue": 0
            }
        
        position = self.positions[symbol]
        
        if side == "BUY":
            # Add to position
            new_quantity = position["quantity"] + quantity
            new_value = position["totalValue"] + (quantity * price)
            position["quantity"] = new_quantity
            position["totalValue"] = new_value
            position["avgPrice"] = new_value / new_quantity if new_quantity > 0 else 0
            
        else:  # SELL
            # Reduce position
            if position["quantity"] >= quantity:
                # Calculate P&L for this trade
                pnl = (price - position["avgPrice"]) * quantity
                
                # Update position
                position["quantity"] -= quantity
                position["totalValue"] = position["avgPrice"] * position["quantity"]
                
                # Update account balance with the P&L
                if self.account_manager:
                    self.account_manager.update_balance(pnl)
                else:
                    self.virtual_balance += pnl
                
                # Record trade
                trade = {
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "entryPrice": position["avgPrice"],
                    "exitPrice": price,
                    "pnl": pnl,
                    "timestamp": order["timestamp"]
                }
                self.trade_history.append(trade)
                
                print(f"Demo Trade Closed: P&L = ₹{pnl:,.2f}")
                print(f"  Entry Price: ₹{position['avgPrice']:.2f}")
                print(f"  Exit Price: ₹{price:.2f}")
                print(f"  Quantity: {quantity}")
                print(f"  Updated Balance: ₹{self.get_account_balance():,.2f}")
                
                # If position is closed, remove it
                if position["quantity"] == 0:
                    del self.positions[symbol]
    
    def modify_target(self, order_id: str, new_target: float) -> Dict:
        """Modify target price for an order"""
        # Find the order
        for order in self.order_history:
            if order["orderId"] == order_id:
                order["targetPrice"] = round_to_tick(new_target, self.tick_size)
                print(f"Demo Order Modified: {order_id} - New Target: {new_target}")
                return {"status": "SUCCESS", "message": "Target modified successfully"}
        
        return {"status": "FAILED", "message": "Order not found"}
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        # Find the order
        for order in self.order_history:
            if order["orderId"] == order_id and order["status"] == "PENDING":
                order["status"] = "CANCELLED"
                print(f"Demo Order Cancelled: {order_id}")
                return {"status": "SUCCESS", "message": "Order cancelled successfully"}
        
        return {"status": "FAILED", "message": "Order not found or already filled"}
    
    def get_positions(self) -> Dict:
        """Get current positions"""
        return self.positions.copy()
    
    def get_trade_history(self) -> List[Dict]:
        """Get trade history"""
        return self.trade_history.copy()
    
    def get_order_history(self) -> List[Dict]:
        """Get order history"""
        return self.order_history.copy()
    
    def get_account_summary(self) -> Dict:
        """Get account summary with P&L"""
        total_pnl = sum(trade["pnl"] for trade in self.trade_history)
        unrealized_pnl = 0
        
        # Calculate unrealized P&L for open positions
        for symbol, position in self.positions.items():
            # This would need current market price
            # For demo, we'll use a placeholder
            current_price = position["avgPrice"]  # Placeholder
            unrealized_pnl += (current_price - position["avgPrice"]) * position["quantity"]
        
        # Use account manager balance if available
        current_balance = self.get_account_balance()
        
        return {
            "virtualBalance": current_balance,
            "totalPnl": total_pnl,
            "unrealizedPnl": unrealized_pnl,
            "totalTrades": len(self.trade_history),
            "openPositions": len(self.positions),
            "winningTrades": len([t for t in self.trade_history if t["pnl"] > 0]),
            "losingTrades": len([t for t in self.trade_history if t["pnl"] < 0])
        }
    
    def print_account_summary(self):
        """Print account summary"""
        summary = self.get_account_summary()
        
        print("\n=== Demo Account Summary ===")
        print(f"Virtual Balance: ₹{summary['virtualBalance']:,.2f}")
        print(f"Total P&L: ₹{summary['totalPnl']:,.2f}")
        print(f"Unrealized P&L: ₹{summary['unrealizedPnl']:,.2f}")
        print(f"Total Trades: {summary['totalTrades']}")
        print(f"Open Positions: {summary['openPositions']}")
        print(f"Winning Trades: {summary['winningTrades']}")
        print(f"Losing Trades: {summary['losingTrades']}")
        
        if summary['totalTrades'] > 0:
            win_rate = (summary['winningTrades'] / summary['totalTrades']) * 100
            print(f"Win Rate: {win_rate:.1f}%")
        
        print("=" * 30)
