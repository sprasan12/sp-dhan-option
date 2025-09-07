"""
Timezone utilities for consistent datetime handling across the application
"""

from datetime import datetime
from typing import Union, Tuple


def normalize_timezone_awareness(dt1: datetime, dt2: datetime) -> Tuple[datetime, datetime]:
    """
    Normalize two datetime objects to have the same timezone awareness.
    
    Args:
        dt1: First datetime object
        dt2: Second datetime object
        
    Returns:
        Tuple of (normalized_dt1, normalized_dt2) with same timezone awareness
    """
    if dt1.tzinfo is None and dt2.tzinfo is not None:
        # dt1 is naive, dt2 is aware - make dt1 aware
        dt1 = dt1.replace(tzinfo=dt2.tzinfo)
    elif dt1.tzinfo is not None and dt2.tzinfo is None:
        # dt1 is aware, dt2 is naive - make dt2 aware
        dt2 = dt2.replace(tzinfo=dt1.tzinfo)
    
    return dt1, dt2


def ensure_timezone_naive(dt: datetime) -> datetime:
    """
    Ensure a datetime object is timezone-naive.
    
    Args:
        dt: Datetime object
        
    Returns:
        Timezone-naive datetime object
    """
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def ensure_timezone_aware(dt: datetime, tzinfo=None) -> datetime:
    """
    Ensure a datetime object is timezone-aware.
    
    Args:
        dt: Datetime object
        tzinfo: Timezone info to use (if None, uses UTC)
        
    Returns:
        Timezone-aware datetime object
    """
    if dt.tzinfo is None:
        if tzinfo is None:
            from datetime import timezone
            tzinfo = timezone.utc
        return dt.replace(tzinfo=tzinfo)
    return dt


def safe_datetime_compare(dt1: datetime, dt2: datetime, operation: str = "eq") -> bool:
    """
    Safely compare two datetime objects regardless of timezone awareness.
    
    Args:
        dt1: First datetime object
        dt2: Second datetime object
        operation: Comparison operation ("eq", "ne", "lt", "le", "gt", "ge")
        
    Returns:
        Boolean result of the comparison
    """
    # Normalize timezone awareness
    dt1, dt2 = normalize_timezone_awareness(dt1, dt2)
    
    if operation == "eq":
        return dt1 == dt2
    elif operation == "ne":
        return dt1 != dt2
    elif operation == "lt":
        return dt1 < dt2
    elif operation == "le":
        return dt1 <= dt2
    elif operation == "gt":
        return dt1 > dt2
    elif operation == "ge":
        return dt1 >= dt2
    else:
        raise ValueError(f"Unsupported operation: {operation}")


def safe_datetime_arithmetic(dt1: datetime, dt2: Union[datetime, int, float], operation: str = "sub") -> datetime:
    """
    Safely perform datetime arithmetic operations.
    
    Args:
        dt1: First datetime object
        dt2: Second datetime object or numeric value (for timedelta operations)
        operation: Operation ("sub", "add")
        
    Returns:
        Result datetime object
    """
    from datetime import timedelta
    
    if isinstance(dt2, (int, float)):
        # dt2 is a numeric value for timedelta
        if operation == "sub":
            return dt1 - timedelta(seconds=dt2)
        elif operation == "add":
            return dt1 + timedelta(seconds=dt2)
        else:
            raise ValueError(f"Unsupported operation: {operation}")
    else:
        # dt2 is a datetime object
        dt1, dt2 = normalize_timezone_awareness(dt1, dt2)
        
        if operation == "sub":
            return dt1 - dt2
        elif operation == "add":
            return dt1 + dt2
        else:
            raise ValueError(f"Unsupported operation: {operation}")
