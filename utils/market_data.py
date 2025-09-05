"""
WebSocket module for handling market data connections
"""

import json
import struct
import time
import websocket
import threading
from datetime import datetime
import pytz

class MarketDataWebSocket:
    """WebSocket handler for market data"""
    
    def __init__(self, access_token, client_id, on_message_callback=None, on_error_callback=None, on_close_callback=None):
        self.access_token = access_token
        self.client_id = client_id
        self.on_message_callback = on_message_callback
        self.on_error_callback = on_error_callback
        self.on_close_callback = on_close_callback
        self.ws = None
        self.ws_thread = None
        
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        if self.on_message_callback:
            self.on_message_callback(ws, message)
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
        if self.on_error_callback:
            self.on_error_callback(ws, error)
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        print(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        if self.on_close_callback:
            self.on_close_callback(ws, close_status_code, close_msg)
    
    def on_open(self, ws):
        """Handle WebSocket connection open"""
        print("WebSocket Connection Established")
        # Subscribe to market data
        if hasattr(self, 'security_id') and self.security_id:
            subscribe_message = {
                "RequestCode": 15,
                "InstrumentCount": 1,
                "InstrumentList": [
                    {
                        "ExchangeSegment": "NSE_FNO",
                        "SecurityId": str(self.security_id)
                    }
                ]
            }
            ws.send(json.dumps(subscribe_message))
            print("Subscription message sent successfully")
        else:
            print("Could not subscribe to market data - Security ID not found")
    
    def connect(self, security_id, max_retries=3):
        """Connect to Dhan WebSocket API"""
        self.security_id = security_id
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"Attempting to connect to Dhan WebSocket (attempt {retry_count + 1}/{max_retries})...")
                
                # Build WebSocket URL with authentication parameters
                ws_url = f"wss://api-feed.dhan.co?version=2&token={self.access_token}&clientId={self.client_id}&authType=2"
                print(f"Connecting to: {ws_url}")
                
               # websocket.enableTrace(False)  # Disable trace for cleaner logs
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
    
    def close(self):
        """Close the WebSocket connection"""
        if self.ws:
            self.ws.close()
    
    def is_connected(self):
        """Check if WebSocket is connected"""
        return hasattr(self.ws, 'sock') and self.ws.sock is not None

def process_ticker_data(data, security_id, callback):
    """Process ticker data packet"""
    try:
        if len(data) < 16:
            print(f"Invalid ticker packet length: {len(data)}")
            return
            
        # Check message type - only process ticker data (\x02)
        if len(data) > 0 and data[0] != 0x02:
            return
            
        # Extract LTP and LTT from payload (after 8-byte header)
        payload = data[8:]
        if len(payload) >= 8:
            # LTP is first 4 bytes, LTT is next 4 bytes
            ltp_bytes = payload[0:4]
            ltt_bytes = payload[4:8]
            
            # Convert using little-endian (as per Dhan docs)
            ltp = struct.unpack('<f', ltp_bytes)[0]
            
            # Use current system time with timezone awareness
            timestamp = datetime.now(pytz.timezone('Asia/Kolkata'))
            
            # Print LTP with timestamp
            print(f"LTP: {ltp:.2f} | Time: {timestamp.strftime('%H:%M:%S')}")
            
            # Call the callback function with processed data
            if callback:
                callback(ltp, timestamp, security_id)
        else:
            print(f"Invalid ticker payload length: {len(payload)}")
    except Exception as e:
        print(f"Error processing ticker data: {e}")

def process_quote_data(data, security_id):
    """Process quote data packet"""
    print(f"Quote data received for Security ID: {security_id}")
    # TODO: Implement quote data processing if needed

def process_market_depth(data, security_id):
    """Process market depth packet"""
    print(f"Market depth received for Security ID: {security_id}")
    # TODO: Implement market depth processing if needed
