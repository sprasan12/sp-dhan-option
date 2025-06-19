import os
import time
import json
import websocket
import threading
import requests
import pandas as pd
import struct
from datetime import datetime, timedelta
from dhanhq import dhanhq
from dotenv import load_dotenv
from collections import deque

# Load environment variables
load_dotenv()

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
        
    def __str__(self):
        return f"Candle[{self.timestamp}] O:{self.open:.2f} H:{self.high:.2f} L:{self.low:.2f} C:{self.close:.2f}"

class DhanTradingBot:
    def __init__(self):
        self.client_id = os.getenv('DHAN_CLIENT_ID')
        self.access_token = os.getenv('DHAN_ACCESS_TOKEN')
        self.dhan = dhanhq(self.client_id, self.access_token)
        self.active_order = None
        self.ws = None
        self.market_data = {}
        self.instruments_df = None
        
        # Strategy parameters
        self.candle_timeframe = 15  # seconds
        self.max_candles = 100
        self.candles = deque(maxlen=self.max_candles)
        self.current_candle = None
        self.last_candle_time = None
        self.is_trading = False
        self.current_position = None
        self.stop_loss = None
        
    def load_instruments(self):
        """Load instruments list from Dhan API"""
        try:
            # Fetch the detailed instrument list
            url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
            self.instruments_df = pd.read_csv(url, low_memory=False)
            
            # Save the CSV locally in the current directory
            try:
                local_path = os.path.join(os.getcwd(), "dhan_instruments.csv")
                self.instruments_df.to_csv(local_path, index=False)
                print(f"Instruments list loaded and saved to {local_path}")
            except Exception as e:
                print(f"Warning: Could not save CSV file: {e}")
                print("Continuing without saving the file...")
            
            # Print some debug information about available options
            options_df = self.instruments_df[
                (self.instruments_df['EXCH_ID'] == 'NSE') & 
                (self.instruments_df['SEGMENT'] == 'D') &
                (self.instruments_df['INSTRUMENT'] == 'OPTIDX')
            ]
            
            print("\nAvailable NSE Options:")
            print("======================")
            print(f"Total number of options: {len(options_df)}")
            print("\nSample of available symbols:")
            print(options_df[['DISPLAY_NAME', 'SECURITY_ID', 'STRIKE_PRICE', 'OPTION_TYPE', 'SM_EXPIRY_DATE']].head(10))
            print("\nUnique underlying symbols:")
            print(options_df['UNDERLYING_SYMBOL'].unique())
            
        except Exception as e:
            print(f"Error loading instruments list: {e}")
            return None

    def get_security_id(self, symbol):
        """Get Security ID for a given symbol"""
        try:
            if self.instruments_df is None:
                self.load_instruments()
            
            # Filter for options in NSE
            options_df = self.instruments_df[
                (self.instruments_df['EXCH_ID'] == 'NSE') & 
                (self.instruments_df['SEGMENT'] == 'D') &
                (self.instruments_df['INSTRUMENT'] == 'OPTIDX')
            ]
            
            # Print debug information about the search
            print(f"\nSearching for symbol: {symbol}")
            print("Available symbols that partially match:")
            matching_symbols = options_df[options_df['DISPLAY_NAME'].str.contains(symbol.split('PUT')[0] if 'PUT' in symbol else symbol.split('CALL')[0], case=False)]
            if not matching_symbols.empty:
                print(matching_symbols[['DISPLAY_NAME', 'SECURITY_ID', 'STRIKE_PRICE', 'OPTION_TYPE', 'SM_EXPIRY_DATE']].head())
            
            # Find the exact matching symbol using DISPLAY_NAME
            matching_instrument = options_df[options_df['DISPLAY_NAME'] == symbol]
            
            if not matching_instrument.empty:
                security_id = int(matching_instrument.iloc[0]['SECURITY_ID'])  # Convert to regular int
                print(f"Found Security ID {security_id} for symbol {symbol}")
                return security_id
            else:
                print(f"No matching instrument found for symbol {symbol}")
                return None
                
        except Exception as e:
            print(f"Error getting security ID: {e}")
            return None
        
    def is_market_hours(self):
        """Check if current time is within market hours (9:15 AM to 3:30 PM IST)"""
        now = datetime.now()
        market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_start <= now <= market_end
        
    def is_trading_ending(self):
        """Check if we're within 5 minutes of market end"""
        now = datetime.now()
        trading_end = now.replace(hour=15, minute=25, second=0, microsecond=0)
        return now >= trading_end
        
    def update_candle(self, price, timestamp):
        """Update or create a new candle based on the current price"""
        if not self.last_candle_time:
            self.last_candle_time = timestamp
            self.current_candle = Candle(timestamp, price, price, price, price)
            print(f"\n🕯️ New Candle Created: {self.current_candle}")
            return
            
        # Check if we need to create a new candle
        time_diff = (timestamp - self.last_candle_time).total_seconds()
        if time_diff >= self.candle_timeframe:
            # Store the completed candle
            self.candles.append(self.current_candle)
            print(f"\n✅ Candle Completed: {self.current_candle}")
            
            # Create new candle
            self.current_candle = Candle(timestamp, price, price, price, price)
            self.last_candle_time = timestamp
            print(f"🕯️ New Candle Created: {self.current_candle}")
        else:
            # Update current candle
            self.current_candle.high = max(self.current_candle.high, price)
            self.current_candle.low = min(self.current_candle.low, price)
            self.current_candle.close = price
            
    def detect_fvg(self):
        """Detect Fair Value Gap in the last 3 candles"""
        if len(self.candles) < 3:
            return None
            
        # Get the last 3 candles
        c1, c2, c3 = list(self.candles)[-3:]
        
        # Check for bullish FVG
        if c3.low > c1.high:
            gap_size = c3.low - c1.high
            if gap_size >= (c2.size() / 2):  # FVG size >= half of expansion candle
                fvg = {
                    'type': 'bullish',
                    'gap_size': gap_size,
                    'entry': c3.low,
                    'stop_loss': c2.low,
                    'candles': [c1, c2, c3]
                }
                
                # Debug information
                print(f"\n=== FVG DETECTED ===")
                print(f"Candle 1: O:{c1.open:.2f} H:{c1.high:.2f} L:{c1.low:.2f} C:{c1.close:.2f}")
                print(f"Candle 2: O:{c2.open:.2f} H:{c2.high:.2f} L:{c2.low:.2f} C:{c2.close:.2f}")
                print(f"Candle 3: O:{c3.open:.2f} H:{c3.high:.2f} L:{c3.low:.2f} C:{c3.close:.2f}")
                print(f"Gap Size: {gap_size:.2f}")
                print(f"Entry: {c3.low:.2f}")
                print(f"Stop Loss: {c2.low:.2f}")
                
                return fvg
        return None
        
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # Process Dhan API format (binary)
            header = message[:8]
            payload = message[8:]
            
            # Extract header information
            feed_code = header[0]
            message_length = struct.unpack('>H', header[1:3])[0]
            exchange_segment = header[3]
            security_id = struct.unpack('>I', header[4:8])[0]
            
            # Process different types of packets
            if feed_code == 2:  # Ticker packet
                # Parse LTP and LTT correctly
                if len(payload) >= 8:
                    # LTP is first 4 bytes, LTT is next 4 bytes
                    ltp_bytes = payload[0:4]
                    ltt_bytes = payload[4:8]
                    
                    # Convert using little-endian (as per Dhan docs)
                    ltp = struct.unpack('<f', ltp_bytes)[0]
                    
                    # Use current system time instead of WebSocket timestamp
                    timestamp = datetime.now()
                    
                    # Print LTP with timestamp
                    print(f"LTP: {ltp:.2f} | Time: {timestamp.strftime('%H:%M:%S')}")
                    
                    # Update market data
                    self.market_data[security_id] = {
                        'ltp': ltp,
                        'timestamp': timestamp
                    }
                    
                    # Update candle data
                    self.update_candle(ltp, timestamp)
                    
                    # Check for FVG and execute trades
                    if not self.is_trading:
                        fvg = self.detect_fvg()
                        if fvg:
                            self.enter_trade(fvg)
                    else:
                        self.update_trailing_stop(ltp)
                else:
                    print(f"Invalid ticker packet length: {len(payload)}")
                
        except Exception as e:
            print(f"Error processing message: {e}")

    def enter_trade(self, fvg):
        """Enter a trade based on FVG"""
        return
        try:
            symbol = os.getenv('SYMBOL')
            quantity = int(os.getenv('QUANTITY', 75))
            
            # Calculate entry, stop loss, and take profit
            entry_price = fvg['entry']
            stop_loss = fvg['stop_loss']
            
            # Calculate risk (entry - stop loss)
            risk = entry_price - stop_loss
            
            # Calculate take profit with 1:1.1 risk:reward ratio
            take_profit = entry_price + (risk * 1.1)
            
            # Place buy order
            print(f"\n=== ENTERING TRADE ===")
            print(f"Entry Price: {entry_price:.2f}")
            print(f"Stop Loss: {stop_loss:.2f}")
            print(f"Take Profit: {take_profit:.2f}")
            print(f"Risk: {risk:.2f}")
            print(f"Reward: {risk * 1.1:.2f}")
            print(f"Risk:Reward = 1:1.1")
            
            buy_order = self.place_order(symbol, quantity, "MARKET", "BUY")
            if not buy_order:
                print("Failed to place buy order")
                return
                
            # Place stop loss order
            sl_order = self.place_order(symbol, quantity, "STOP_LOSS_MARKET", "SELL", price=stop_loss)
            if not sl_order:
                print("Failed to place stop loss order")
                # Cancel buy order if SL fails
                self.cancel_order(buy_order['orderId'])
                return
                
            # Place take profit order
            tp_order = self.place_order(symbol, quantity, "LIMIT", "SELL", price=take_profit)
            if not tp_order:
                print("Failed to place take profit order")
                # Cancel buy and SL orders if TP fails
                self.cancel_order(buy_order['orderId'])
                self.cancel_order(sl_order['orderId'])
                return
                
            self.is_trading = True
            self.current_position = {
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'quantity': quantity,
                'buy_order_id': buy_order['orderId'],
                'sl_order_id': sl_order['orderId'],
                'tp_order_id': tp_order['orderId'],
                'risk': risk,
                'reward': risk * 1.1
            }
            print(f"Trade entered successfully!")
            print(f"Buy Order ID: {buy_order['orderId']}")
            print(f"Stop Loss Order ID: {sl_order['orderId']}")
            print(f"Take Profit Order ID: {tp_order['orderId']}")
            
        except Exception as e:
            print(f"Error entering trade: {e}")
            
    def update_trailing_stop(self, current_price):
        """Update trailing stop loss based on new FVGs"""
        if not self.is_trading or not self.current_position:
            return
            
        # Check for new FVG
        fvg = self.detect_fvg()
        if fvg and fvg['type'] == 'bullish':
            new_stop = fvg['stop_loss']
            if new_stop > self.current_position['stop_loss']:
                # Cancel existing stop loss order
                print(f"\n=== UPDATING TRAILING STOP ===")
                print(f"Old Stop Loss: {self.current_position['stop_loss']:.2f}")
                print(f"New Stop Loss: {new_stop:.2f}")
                
                cancel_sl = self.cancel_order(self.current_position['sl_order_id'])
                if cancel_sl:
                    # Cancel take profit order as well
                    cancel_tp = self.cancel_order(self.current_position['tp_order_id'])
                    if cancel_tp:
                        # Place new stop loss order
                        new_sl_order = self.place_order(
                            os.getenv('SYMBOL'),
                            self.current_position['quantity'],
                            "STOP_LOSS_MARKET",
                            "SELL",
                            price=new_stop
                        )
                        
                        if new_sl_order:
                            # Update position details
                            self.current_position['stop_loss'] = new_stop
                            self.current_position['sl_order_id'] = new_sl_order['orderId']
                            self.current_position['tp_order_id'] = None  # TP is cancelled
                            print(f"Trailing stop updated successfully!")
                            print(f"New Stop Loss Order ID: {new_sl_order['orderId']}")
                            print(f"Take Profit order cancelled")
                        else:
                            print("Failed to place new stop loss order")
                    else:
                        print("Failed to cancel take profit order")
                else:
                    print("Failed to cancel old stop loss order")
                
    def check_market_end(self):
        """Check if we need to close position at market end"""
        if self.is_trading and self.is_trading_ending():
            print("\nMarket ending soon, closing position...")
            self.close_position()
            
    def close_position(self):
        """Close the current position"""
        if not self.is_trading or not self.current_position:
            return
            
        try:
            symbol = os.getenv('SYMBOL')
            quantity = self.current_position['quantity']
            
            print(f"\n=== CLOSING POSITION ===")
            
            # Cancel any existing orders
            if self.current_position.get('sl_order_id'):
                cancel_sl = self.cancel_order(self.current_position['sl_order_id'])
                if cancel_sl:
                    print(f"Stop Loss order cancelled: {self.current_position['sl_order_id']}")
                    
            if self.current_position.get('tp_order_id'):
                cancel_tp = self.cancel_order(self.current_position['tp_order_id'])
                if cancel_tp:
                    print(f"Take Profit order cancelled: {self.current_position['tp_order_id']}")
            
            # Place market sell order to close position
            order = self.place_order(symbol, quantity, "MARKET", "SELL")
            if order:
                print("Position closed successfully")
                print(f"Exit Order ID: {order['orderId']}")
                self.is_trading = False
                self.current_position = None
                
        except Exception as e:
            print(f"Error closing position: {e}")
            
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
        # Don't close the connection on error, let it retry
        pass

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        print(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        # Try to reconnect after a delay
        print("Attempting to reconnect in 10 seconds...")
        time.sleep(10)
        self.connect_websocket()

    def on_open(self, ws):
        print("WebSocket Connection Established")
        # Subscribe to market data
        security_id = self.get_security_id(os.getenv('SYMBOL'))
        if security_id:
            subscribe_message = {
                "RequestCode": 15,
                "InstrumentCount": 1,
                "InstrumentList": [
                    {
                        "ExchangeSegment": "NSE_FNO",
                        "SecurityId": str(security_id)  # Convert to string for JSON
                    }
                ]
            }
            ws.send(json.dumps(subscribe_message))
        else:
            print("Could not subscribe to market data - Security ID not found")

    def connect_websocket(self):
        """Connect to Dhan WebSocket API"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"Attempting to connect to Dhan WebSocket (attempt {retry_count + 1}/{max_retries})...")
                
                # Build WebSocket URL with authentication parameters
                ws_url = f"wss://api-feed.dhan.co?version=2&token={self.access_token}&clientId={self.client_id}&authType=2"
                print(f"Connecting to: {ws_url}")
                
                websocket.enableTrace(False)  # Disable trace for cleaner logs
                self.ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open
                )
                
                # Start WebSocket connection in a separate thread with timeout
                self.ws_thread = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=30, ping_timeout=10))
                self.ws_thread.daemon = True
                self.ws_thread.start()
                
                # Wait for connection to establish
                time.sleep(5)
                
                # Check if connection is established
                if hasattr(self.ws, 'sock') and self.ws.sock:
                    print("WebSocket connection established successfully!")
                    return True
                else:
                    print("WebSocket connection failed to establish")
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"Retrying in 10 seconds...")
                        time.sleep(10)
                    
            except Exception as e:
                print(f"Error connecting to WebSocket (attempt {retry_count + 1}): {e}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"Retrying in 10 seconds...")
                    time.sleep(10)
        
        print("Failed to connect to WebSocket after all retries")
        return False

    def place_order(self, symbol, quantity, order_type="MARKET", side="BUY", price=0):
        """Place an order using Dhan's API structure"""
        try:
            # Get the security ID for the symbol
            security_id = self.get_security_id(symbol)
            if not security_id:
                print(f"Could not find security ID for symbol {symbol}")
                return None

            # Get instrument details
            instrument = self.instruments_df[self.instruments_df['SECURITY_ID'] == security_id].iloc[0]
            
            # Prepare order parameters
            order_params = {
                "security_id": str(security_id),
                "exchange_segment": "NSE_FNO",
                "transaction_type": "BUY" if side == "BUY" else "SELL",
                "quantity": int(quantity),
                "order_type": order_type,
                "product_type": "INTRADAY",
                "price": price,
                "trigger_price": price
            }
            
            print("Placing order with parameters:")
            print(json.dumps(order_params, indent=2))
            
            order_response = self.dhan.place_order(**order_params)
            
            print(f"Order placed: {json.dumps(order_response, indent=2)}")
            
            if order_response.get('status') == 'SUCCESS':
                self.active_order = order_response.get('orderId')
                return order_response
            return None
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

    def cancel_order(self, order_id):
        """Cancel an active order"""
        try:
            cancel_response = self.dhan.cancel_order(order_id)
            print(f"Order cancellation response: {json.dumps(cancel_response, indent=2)}")
            return cancel_response
        except Exception as e:
            print(f"Error cancelling order: {e}")
            return None

    def run_strategy(self, symbol, quantity):
        """Run the trading strategy"""
        try:
            # Get security ID for the symbol
            security_id = self.get_security_id(symbol)
            if not security_id:
                print(f"Could not find security ID for symbol: {symbol}")
                return
                
            print(f"Found security ID: {security_id} for symbol: {symbol}")
            print("Strategy started. Waiting for FVG...")
            
            # Keep checking for market end
            while True:
                self.check_market_end()
                time.sleep(1)
                
        except Exception as e:
            print(f"Error in strategy: {e}")
            if self.ws:
                self.ws.close()

    def run(self):
        """Run the trading bot"""
        try:
            # Connect to WebSocket
            self.connect_websocket()
            
            # Keep the main thread alive
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nShutting down trading bot...")
            if self.ws:
                self.ws.close()
        except Exception as e:
            print(f"Error in main loop: {e}")
            if self.ws:
                self.ws.close()

def main():
    # Initialize the trading bot
    bot = DhanTradingBot()
    
    # Load instruments list
    print("Loading instruments list...")
    bot.load_instruments()
    
    # Get symbol from environment variable
    symbol = os.getenv('SYMBOL')
    if not symbol:
        print("Error: SYMBOL environment variable not set")
        print("Please set SYMBOL in your .env file (e.g., SYMBOL=NIFTY 19 JUN 24900 CALL)")
        return
    
    print(f"Starting trading bot for symbol: {symbol}")
    
    # Start WebSocket connection
    print("Connecting to Dhan WebSocket...")
    connection_success = bot.connect_websocket()
    
    if not connection_success:
        print("Failed to establish WebSocket connection. Please check:")
        print("1. Your internet connection")
        print("2. Dhan API credentials in .env file")
        print("3. Dhan server status")
        print("4. Firewall/proxy settings")
        return
    
    # Wait a bit for connection to establish
    print("Waiting for connection to stabilize...")
    time.sleep(3)
    
    # Run the strategy
    print("Starting FVG strategy...")
    bot.run_strategy(symbol, 75)  # Default quantity of 75
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down trading bot...")
        if bot.ws:
            bot.ws.close()

if __name__ == "__main__":
    main() 