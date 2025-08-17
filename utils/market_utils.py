"""
Market utility functions for time checking, price rounding, and market operations
"""

from datetime import datetime

def is_market_hours():
    """Check if current time is within market hours (9:15 AM to 3:30 PM IST)"""
    now = datetime.now()
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_start <= now <= market_end

def is_trading_ending():
    """Check if we're within 5 minutes of market end"""
    now = datetime.now()
    trading_end = now.replace(hour=15, minute=23, second=0, microsecond=0)
    return now >= trading_end

def round_to_tick(price, tick_size=0.05):
    """Round price to the nearest tick size (default 0.05 INR)"""
    return round(price / tick_size) * tick_size

def get_market_boundary_time(current_time, timeframe_minutes):
    """
    Get the market boundary time for a given timeframe
    
    Args:
        current_time: Current datetime
        timeframe_minutes: Timeframe in minutes (1, 5, 15, etc.)
    
    Returns:
        datetime: Start time of the current period
    """
    # Check if market is open (after 9:15 AM)
    if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 15):
        return None
    
    # Calculate the current period based on configurable timeframe
    total_minutes = (current_time.hour - 9) * 60 + (current_time.minute - 15)
    period_number = total_minutes // timeframe_minutes
    
    # Calculate the start time of this period
    period_start_minutes = period_number * timeframe_minutes
    
    # Calculate the candle start time by adding minutes to market open time
    market_open_time = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
    candle_start_time = market_open_time.replace(minute=market_open_time.minute + period_start_minutes)
    
    return candle_start_time
