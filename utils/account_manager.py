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
        
        # Session tracking
        self.starting_balance = config.account_start_balance
        self.session_pnl = 0.0
        self.trades_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
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
        
        # Update session tracking
        self.session_pnl += pnl
        self.trades_count += 1
        if pnl > 0:
            self.winning_trades += 1
        elif pnl < 0:
            self.losing_trades += 1
        
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
        
        # Calculate how many lots we can trade based on SL limit
        if max_loss_per_lot <= 0:
            self.logger.warning(f"❌ Trade Rejected: Invalid SL distance")
            return False, 0, 0, 0
        
        max_lots_by_sl = math.floor(self.fixed_sl_amount / max_loss_per_lot)
        
        if max_lots_by_sl <= 0:
            self.logger.warning(f"❌ Trade Rejected: Max loss per lot (₹{max_loss_per_lot:.2f}) > Fixed SL amount (₹{self.fixed_sl_amount:.2f})")
            return False, 0, 0, 0
        
        # Calculate how many lots we can afford with current balance
        investment_per_lot = market_price * self.config.lot_size
        max_lots_by_balance = math.floor(self.current_balance / investment_per_lot)
        
        self.logger.info(f"   Investment per Lot: ₹{investment_per_lot:.2f}")
        self.logger.info(f"   Available Balance: ₹{self.current_balance:.2f}")
        self.logger.info(f"   Max Lots by SL: {max_lots_by_sl}")
        self.logger.info(f"   Max Lots by Balance: {max_lots_by_balance}")
        
        # Take the minimum of both limits
        max_lots = min(max_lots_by_sl, max_lots_by_balance)
        
        if max_lots <= 0:
            if max_lots_by_balance <= 0:
                self.logger.warning(f"❌ Trade Rejected: Insufficient balance. Need ₹{investment_per_lot:.2f} per lot, have ₹{self.current_balance:.2f}")
            else:
                self.logger.warning(f"❌ Trade Rejected: Cannot afford even 1 lot. Need ₹{investment_per_lot:.2f}, have ₹{self.current_balance:.2f}")
            return False, 0, 0, 0
        
        # Calculate actual SL amount for this trade
        actual_sl_amount = max_lots * max_loss_per_lot
        total_investment = max_lots * investment_per_lot
        
        self.logger.info(f"✅ Trade Approved:")
        self.logger.info(f"   Final Lots: {max_lots}")
        self.logger.info(f"   Actual SL Amount: ₹{actual_sl_amount:.2f}")
        self.logger.info(f"   Total Investment: ₹{total_investment:.2f}")
        self.logger.info(f"   Remaining Balance: ₹{self.current_balance - total_investment:.2f}")
        
        # Note: Investment will be deducted when trade is actually placed
        # Don't deduct here as this is just parameter calculation
        
        return True, max_lots, actual_sl_amount, max_loss_per_lot
    
    def deduct_investment(self, investment_amount: float):
        """Deduct investment amount from account balance"""
        old_balance = self.current_balance
        self.current_balance -= investment_amount
        self.logger.info(f"💰 Investment Deducted: ₹{old_balance:,.2f} → ₹{self.current_balance:,.2f} (Investment: ₹{investment_amount:,.2f})")
    
    def add_investment_return(self, investment_amount: float, pnl: float):
        """Add back investment amount plus P&L to account balance"""
        total_return = investment_amount + pnl
        old_balance = self.current_balance
        self.current_balance += total_return
        self.logger.info(f"💰 Investment Returned: ₹{old_balance:,.2f} → ₹{self.current_balance:,.2f} (Return: ₹{total_return:,.2f} = Investment: ₹{investment_amount:,.2f} + P&L: ₹{pnl:,.2f})")
    
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
        
        # Add back investment amount plus P&L
        self.add_investment_return(total_investment, pnl)
    
    def get_session_summary(self) -> dict:
        """Get comprehensive session summary"""
        win_rate = (self.winning_trades / self.trades_count * 100) if self.trades_count > 0 else 0
        return {
            'starting_balance': self.starting_balance,
            'current_balance': self.current_balance,
            'session_pnl': self.session_pnl,
            'trades_count': self.trades_count,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate
        }
    
    def log_session_summary(self):
        """Log comprehensive session summary"""
        summary = self.get_session_summary()
        
        self.logger.info("=" * 60)
        self.logger.info("📊 SESSION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"💰 Starting Balance: ₹{summary['starting_balance']:,.2f}")
        self.logger.info(f"💰 Current Balance: ₹{summary['current_balance']:,.2f}")
        self.logger.info(f"📈 Session P&L: ₹{summary['session_pnl']:,.2f}")
        self.logger.info(f"📊 Total Trades: {summary['trades_count']}")
        self.logger.info(f"✅ Winning Trades: {summary['winning_trades']}")
        self.logger.info(f"❌ Losing Trades: {summary['losing_trades']}")
        self.logger.info(f"🎯 Win Rate: {summary['win_rate']:.1f}%")
        
        if summary['session_pnl'] > 0:
            self.logger.info(f"🎉 PROFITABLE SESSION! +₹{summary['session_pnl']:,.2f}")
        elif summary['session_pnl'] < 0:
            self.logger.info(f"📉 LOSS SESSION: ₹{summary['session_pnl']:,.2f}")
        else:
            self.logger.info("⚖️ BREAKEVEN SESSION")
        
        self.logger.info("=" * 60)
