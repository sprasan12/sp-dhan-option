"""
Candle model for representing OHLC data with classification methods
"""

class Candle:
    def __init__(self, timestamp, open_price, high, low, close):
        self.timestamp = timestamp
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        
    def size(self):
        """Calculate the size of the candle (high - low)"""
        return self.high - self.low
    
    def body_size(self):
        """Calculate the body size of the candle (|close - open|)"""
        return abs(self.close - self.open)
    
    def body_percentage(self):
        """Calculate body as percentage of total candle size"""
        total_size = self.size()
        if total_size == 0:
            return 0
        return (self.body_size() / total_size) * 100
    
    def is_bull_candle(self):
        """Check if this is a bull candle (Close > Open and body >= 50% of total size)"""
        return self.close > self.open and self.body_percentage() >= 50
    
    def is_bear_candle(self):
        """Check if this is a bear candle (Open > Close and body >= 50% of total size)"""
        return self.open > self.close and self.body_percentage() >= 50
    
    def is_neutral_candle(self):
        """Check if this is a neutral candle (body < 50% of total size)"""
        return self.body_percentage() < 50
        
    def __str__(self):
        return f"Candle[{self.timestamp}] O:{self.open:.2f} H:{self.high:.2f} L:{self.low:.2f} C:{self.close:.2f}"
