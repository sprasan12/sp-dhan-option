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
        self.security_ids = {}
        
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
        print(f"DEBUG: on_open() - hasattr security_ids: {hasattr(self, 'security_ids')}")
        print(f"DEBUG: on_open() - security_ids: {getattr(self, 'security_ids', 'NOT_FOUND')}")
        # Subscribe to market data for all security IDs
        if hasattr(self, 'security_ids') and self.security_ids:
            instrument_list = []
            for symbol, security_id in self.security_ids.items():
                # For options, use NSE_FNO as you specified
                exchange_segment = "NSE_FNO"
                    
                instrument_list.append({
                    "ExchangeSegment": exchange_segment,
                    "SecurityId": str(security_id)
                })
            
            subscribe_message = {
                "RequestCode": 15,
                "InstrumentCount": len(instrument_list),
                "InstrumentList": instrument_list
            }
            print(f"DEBUG: Sending subscription message: {json.dumps(subscribe_message, indent=2)}")
            ws.send(json.dumps(subscribe_message))
            print(f"Subscription message sent successfully for {len(instrument_list)} instruments")
        else:
            print("Could not subscribe to market data - Security IDs not found")
    
    def connect(self, security_ids, max_retries=3):
        """Connect to Dhan WebSocket API"""
        # Store security_ids for subscription
        if isinstance(security_ids, dict):
            self.security_ids = security_ids
        elif isinstance(security_ids, list):
            # Convert list to dict with index as key if needed
            self.security_ids = {f"symbol_{i}": sid for i, sid in enumerate(security_ids)}
        else:
            # Single security_id case for backward compatibility
            self.security_ids = {"symbol": security_ids}
        
        print(f"DEBUG: Stored security_ids: {self.security_ids}")
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

def parse_websocket_message_header(data):
    """Parse WebSocket message header to extract metadata"""
    try:
        if len(data) < 8:
            return None
            
        # Extract header information
        feed_code = data[0]  # 1 byte
        message_length = data[1]  # 1 byte
        exchange = int.from_bytes(data[2:4], byteorder='little')  # 2 bytes
        security_id = int.from_bytes(data[4:8], byteorder='little')  # 4 bytes
        
        return {
            'feed_code': feed_code,
            'message_length': message_length,
            'exchange': exchange,
            'security_id': security_id
        }
    except Exception as e:
        print(f"Error parsing message header: {e}")
        return None

def process_ticker_data(data, security_id=None, callback=None):
    """Process ticker data packet for multiple tickers"""
    try:
        if len(data) < 16:
            print(f"Invalid ticker packet length: {len(data)}")
            return None
            
        # Parse message header to extract security_id if not provided
        header = parse_websocket_message_header(data)
        if not header:
            return None
            
        # Use provided security_id or extract from message
        actual_security_id = security_id if security_id is not None else header['security_id']
        
        # Check message type - only process ticker data (\x02)
        if header['feed_code'] != 0x02:
            return None
            
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
            
            # Print LTP with timestamp and security_id
            print(f"Security ID: {actual_security_id} | LTP: {ltp:.2f} | Time: {timestamp.strftime('%H:%M:%S')}")
            
            # Call the callback function with processed data
            if callback:
                callback(ltp, timestamp, actual_security_id)
            
            # Return the processed data
            return {
                'last_price': ltp,
                'timestamp': timestamp,
                'security_id': actual_security_id
            }
        else:
            print(f"Invalid ticker payload length: {len(payload)}")
            return None
    except Exception as e:
        print(f"Error processing ticker data: {e}")
        return None

def process_quote_data(data, security_id=None):
    """Process quote data packet for multiple tickers"""
    try:
        # Parse message header to extract security_id if not provided
        header = parse_websocket_message_header(data)
        if not header:
            return
            
        # Use provided security_id or extract from message
        actual_security_id = security_id if security_id is not None else header['security_id']
        
        # Check message type - only process quote data (\x04)
        if header['feed_code'] != 0x04:
            return
            
        print(f"Quote data received for Security ID: {actual_security_id}")
        # TODO: Implement quote data processing if needed
    except Exception as e:
        print(f"Error processing quote data: {e}")

def process_market_depth(data, security_id=None):
    """Process market depth packet for multiple tickers"""
    try:
        # Parse message header to extract security_id if not provided
        header = parse_websocket_message_header(data)
        if not header:
            return
            
        # Use provided security_id or extract from message
        actual_security_id = security_id if security_id is not None else header['security_id']
        
        # Check message type - only process market depth data (\x06)
        if header['feed_code'] != 0x06:
            return
            
        print(f"Market depth received for Security ID: {actual_security_id}")
        # TODO: Implement market depth processing if needed
    except Exception as e:
        print(f"Error processing market depth: {e}")
