"""
Account management module for tracking balance and calculating trade parameters
"""

import math
from typing import Tuple, Optional
from utils.config import TradingConfig
from utils.logger import TradingLogger

class AccountManager:
    """Manages account balance and trade risk calculations"""
    
    def __init__(self, config: TradingConfig, logger: TradingLogger):
        self.config = config
        self.logger = logger
        self.current_balance = config.account_start_balance
        self.fixed_sl_amount = config.get_fixed_sl_amount()
        
        self.logger.info(f"💰 Account Manager Initialized")
        self.logger.info(f"   Starting Balance: ₹{self.current_balance:,.2f}")
        self.logger.info(f"   Fixed SL Amount: ₹{self.fixed_sl_amount:,.2f}")
        self.logger.info(f"   Lot Size: {self.config.lot_size}")
        self.logger.info(f"   Max SL % of Price: {self.config.max_sl_percentage_of_price}%")
    
    def get_current_balance(self) -> float:
        """Get current account balance"""
        return self.current_balance
    
    def update_balance(self, pnl: float):
        """Update account balance after trade"""
        old_balance = self.current_balance
        self.current_balance += pnl
        self.logger.info(f"💰 Balance Updated: ₹{old_balance:,.2f} → ₹{self.current_balance:,.2f} (P&L: ₹{pnl:,.2f})")
    
    def calculate_trade_parameters(self, market_price: float, stop_loss_price: float) -> Tuple[bool, int, float, float]:
        """
        Calculate trade parameters based on risk management rules
        
        Returns:
            Tuple[can_trade, lots, actual_sl, max_loss_per_lot]
        """
        # Calculate SL distance from market price
        sl_distance = abs(market_price - stop_loss_price)
        sl_percentage_of_price = (sl_distance / market_price) * 100
        
        self.logger.info(f"🔍 Trade Risk Analysis:")
        self.logger.info(f"   Market Price: ₹{market_price:.2f}")
        self.logger.info(f"   Stop Loss Price: ₹{stop_loss_price:.2f}")
        self.logger.info(f"   SL Distance: ₹{sl_distance:.2f}")
        self.logger.info(f"   SL % of Price: {sl_percentage_of_price:.2f}%")
        
        # Check if SL is too high (>= 15% of market price)
        if sl_percentage_of_price >= self.config.max_sl_percentage_of_price:
            self.logger.warning(f"❌ Trade Rejected: SL {sl_percentage_of_price:.2f}% >= Max {self.config.max_sl_percentage_of_price}%")
            return False, 0, 0, 0
        
        # Calculate max loss per lot
        max_loss_per_lot = sl_distance * self.config.lot_size
        
        self.logger.info(f"   Max Loss per Lot: ₹{max_loss_per_lot:.2f}")
        self.logger.info(f"   Fixed SL Amount: ₹{self.fixed_sl_amount:.2f}")
        
        # Calculate how many lots we can trade
        if max_loss_per_lot <= 0:
            self.logger.warning(f"❌ Trade Rejected: Invalid SL distance")
            return False, 0, 0, 0
        
        max_lots = math.floor(self.fixed_sl_amount / max_loss_per_lot)
        
        if max_lots <= 0:
            self.logger.warning(f"❌ Trade Rejected: Max loss per lot (₹{max_loss_per_lot:.2f}) > Fixed SL amount (₹{self.fixed_sl_amount:.2f})")
            return False, 0, 0, 0
        
        # Calculate actual SL amount for this trade
        actual_sl_amount = max_lots * max_loss_per_lot
        
        self.logger.info(f"✅ Trade Approved:")
        self.logger.info(f"   Max Lots Possible: {max_lots}")
        self.logger.info(f"   Actual SL Amount: ₹{actual_sl_amount:.2f}")
        self.logger.info(f"   Total Investment: ₹{max_lots * self.config.lot_size * market_price:.2f}")
        
        return True, max_lots, actual_sl_amount, max_loss_per_lot
    
    def calculate_pnl(self, entry_price: float, exit_price: float, lots: int, is_buy: bool = True) -> float:
        """
        Calculate P&L for a trade
        
        Args:
            entry_price: Entry price per unit
            exit_price: Exit price per unit
            lots: Number of lots traded
            is_buy: True if buy trade, False if sell trade
        
        Returns:
            P&L amount (positive for profit, negative for loss)
        """
        quantity = lots * self.config.lot_size
        
        if is_buy:
            # Buy trade: profit when exit_price > entry_price
            pnl = (exit_price - entry_price) * quantity
        else:
            # Sell trade: profit when entry_price > exit_price
            pnl = (entry_price - exit_price) * quantity
        
        return pnl
    
    def log_trade_summary(self, entry_price: float, exit_price: float, lots: int, 
                         stop_loss: float, target: float, reason: str):
        """Log comprehensive trade summary"""
        quantity = lots * self.config.lot_size
        total_investment = quantity * entry_price
        pnl = self.calculate_pnl(entry_price, exit_price, lots)
        
        self.logger.info(f"📊 Trade Summary:")
        self.logger.info(f"   Entry Price: ₹{entry_price:.2f}")
        self.logger.info(f"   Exit Price: ₹{exit_price:.2f}")
        self.logger.info(f"   Lots: {lots} (Quantity: {quantity})")
        self.logger.info(f"   Total Investment: ₹{total_investment:.2f}")
        self.logger.info(f"   Stop Loss: ₹{stop_loss:.2f}")
        self.logger.info(f"   Target: ₹{target:.2f}")
        self.logger.info(f"   Exit Reason: {reason}")
        self.logger.info(f"   P&L: ₹{pnl:.2f}")
        self.logger.info(f"   Account Balance: ₹{self.current_balance:.2f}")
        
        # Update balance
        self.update_balance(pnl)
