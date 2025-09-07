"""
Rate limiter for API calls to respect Dhan API limits
"""

import time
from typing import Callable, Any
from functools import wraps

class RateLimiter:
    """Rate limiter to ensure we don't exceed API rate limits"""
    
    def __init__(self, max_requests: int = 10, time_window: float = 1.0):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def wait_if_needed(self):
        """Wait if we need to respect rate limits"""
        now = time.time()
        
        # Remove old requests outside the time window
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
        
        # If we're at the limit, wait
        if len(self.requests) >= self.max_requests:
            # Calculate how long to wait
            oldest_request = min(self.requests)
            wait_time = self.time_window - (now - oldest_request)
            
            if wait_time > 0:
                print(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                time.sleep(wait_time)
        
        # Record this request
        self.requests.append(now)

# Global rate limiter instance
# Conservative settings: 5 requests per second (well below the 10 req/sec limit)
api_rate_limiter = RateLimiter(max_requests=5, time_window=1.0)

def rate_limit(func: Callable) -> Callable:
    """
    Decorator to add rate limiting to API functions
    
    Args:
        func: Function to rate limit
    
    Returns:
        Wrapped function with rate limiting
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        api_rate_limiter.wait_if_needed()
        return func(*args, **kwargs)
    return wrapper

def make_rate_limited_request(method: str, url: str, **kwargs) -> Any:
    """
    Make a rate-limited HTTP request
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        **kwargs: Additional arguments for requests
    
    Returns:
        Response object
    """
    import requests
    
    # Apply rate limiting
    api_rate_limiter.wait_if_needed()
    
    # Make the request
    if method.upper() == 'GET':
        return requests.get(url, **kwargs)
    elif method.upper() == 'POST':
        return requests.post(url, **kwargs)
    elif method.upper() == 'PUT':
        return requests.put(url, **kwargs)
    elif method.upper() == 'DELETE':
        return requests.delete(url, **kwargs)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")

def add_delay_between_requests(delay_seconds: float = 0.2):
    """
    Add a delay between requests to be extra safe
    
    Args:
        delay_seconds: Delay in seconds
    """
    time.sleep(delay_seconds)
