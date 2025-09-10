"""
Simple Ticker Logger - Connect to Dhan WebSocket and log ticker data
This script focuses only on connecting to Dhan and logging ticker data without any processing.

IMPORTANT: Before running this script, update the credentials below:
- self.client_id = "YOUR_CLIENT_ID_HERE"
- self.access_token = "YOUR_ACCESS_TOKEN_HERE"
"""

import os
import time
import signal
import sys
from datetime import datetime
import pytz
import pandas as pd

# Import required components
from brokers.dhan_broker import DhanBroker
from utils.market_data import MarketDataWebSocket, process_ticker_data
import logging

class SimpleTickerLogger:
    """Simple ticker logger that connects to Dhan and logs ticker data"""
    
    def __init__(self):
        # Hardcoded configuration - UPDATE THESE VALUES
        self.client_id = "1100580284"  # Replace with your actual client ID
        self.access_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzU3OTM0MjUyLCJ0b2tlbkNvbnN1bWVyVHlwZSI6IlNFTEYiLCJ3ZWJob29rVXJsIjoiIiwiZGhhbkNsaWVudElkIjoiMTEwMDU4MDI4NCJ9.gpGIlcYIpkPsi359AQ1W-N_azCrD7kk1s8z8IpMEimRbm73EWrUf0xdjHbhQ1sM9b7PV1JSfSMiKfA-X5rr3wQ"
  # Replace with your actual access token
     
        
        # Initialize broker
        self.broker = DhanBroker(
            client_id=self.client_id,
            access_token=self.access_token
        )
        
        # Load instruments
        self.instruments_df = self.load_instruments()
        print(f"Loaded {len(self.instruments_df)} instruments")
        
        # Security IDs for symbols we want to track
        self.security_ids = {}
        
        # WebSocket connection
        self.websocket = None
        
        # Message counter
        self.message_count = 0
        
        # Setup logging
        self.setup_logging()
        
        # Signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def load_instruments(self):
        """Load instruments from Dhan API"""
        try:
            # Fetch the detailed instrument list
            url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
            instruments_df = pd.read_csv(url, low_memory=False)
            
            # Save the CSV locally in the current directory
            try:
                local_path = os.path.join(os.getcwd(), "dhan_instruments.csv")
                instruments_df.to_csv(local_path, index=False)
                print(f"Instruments list loaded and saved to {local_path}")
            except Exception as e:
                print(f"Warning: Could not save CSV file: {e}")
                print("Continuing without saving the file...")
            
            return instruments_df
            
        except Exception as e:
            print(f"Error loading instruments: {e}")
            return None
        
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(f'ticker_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        self.stop()
        sys.exit(0)
        
    def add_symbol(self, symbol):
        """Add a symbol to track"""
        if self.instruments_df is None:
            print("ERROR: Instruments data not loaded")
            return False
            
        security_id = self.broker.get_security_id(symbol, self.instruments_df)
        if security_id:
            self.security_ids[symbol] = security_id
            print(f"Added symbol: {symbol} -> Security ID: {security_id}")
            return True
        else:
            print(f"Could not find security ID for symbol: {symbol}")
            # Let's check what symbols are available
            print("Available NSE Index symbols (first 10):")
            try:
                index_df = self.instruments_df[
                    (self.instruments_df['EXCH_ID'] == 'NSE') & 
                    (self.instruments_df['SEGMENT'] == 'D') &
                    (self.instruments_df['INSTRUMENT'] == 'IDX')
                ]
                print(index_df['DISPLAY_NAME'].head(10).tolist())
                
                print("Available NSE Options (first 10):")
                options_df = self.instruments_df[
                    (self.instruments_df['EXCH_ID'] == 'NSE') & 
                    (self.instruments_df['SEGMENT'] == 'D') &
                    (self.instruments_df['INSTRUMENT'] == 'OPTIDX')
                ]
                print(options_df['DISPLAY_NAME'].head(10).tolist())
            except Exception as e:
                print(f"Error showing available symbols: {e}")
            return False
            
    def connect_websocket(self):
        """Connect to Dhan WebSocket"""
        if not self.security_ids:
            print("No symbols added. Please add symbols first.")
            return False
            
        print(f"Connecting to WebSocket for {len(self.security_ids)} symbols...")
        
        # Create WebSocket
        self.websocket = MarketDataWebSocket(
            access_token=self.access_token,
            client_id=self.client_id,
            on_message_callback=self._on_websocket_message,
            on_error_callback=self._on_websocket_error,
            on_close_callback=self._on_websocket_close
        )
        
        # Connect with all security IDs
        print(f"DEBUG: About to connect with security_ids: {self.security_ids}")
        if self.websocket.connect(self.security_ids):
            print(f"WebSocket connected successfully for {len(self.security_ids)} symbols")
            return True
        else:
            print("Failed to connect to WebSocket")
            return False
            
    def _on_websocket_message(self, ws, message):
        """Handle WebSocket messages"""
        try:
            self.message_count += 1
            print(f"DEBUG: Received WebSocket message #{self.message_count} of length: {len(message)} bytes")
            print(f"DEBUG: First few bytes: {message[:10] if len(message) >= 10 else message}")
            
            # Process ticker data - this will automatically extract security_id from message
            process_ticker_data(message, callback=self._on_ticker_data)
        except Exception as e:
            print(f"Error processing WebSocket message: {e}")
            import traceback
            traceback.print_exc()
            
    def _on_ticker_data(self, ltp, timestamp, security_id):
        """Handle ticker data callback"""
        # Find which symbol this security_id belongs to
        symbol = self._get_symbol_from_security_id(security_id)
        
        # Log the ticker data
        log_message = f"TICKER | Symbol: {symbol} | Security ID: {security_id} | LTP: {ltp:.2f} | Time: {timestamp.strftime('%H:%M:%S')}"
        print(log_message)
        self.logger.info(log_message)
        
    def _get_symbol_from_security_id(self, security_id):
        """Get symbol from security ID"""
        for symbol, sid in self.security_ids.items():
            if sid == security_id:
                return symbol
        return f"Unknown_{security_id}"
        
    def _on_websocket_error(self, ws, error):
        """Handle WebSocket errors"""
        error_message = f"WebSocket error: {error}"
        print(error_message)
        self.logger.error(error_message)
        
    def _on_websocket_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        close_message = f"WebSocket closed: {close_status_code} - {close_msg}"
        print(close_message)
        self.logger.info(close_message)
        
    def run(self):
        """Run the ticker logger"""
        print("Starting Simple Ticker Logger...")
        print("=" * 50)
        
        # Add symbols to track (you can modify these)
        # Use the exact symbols that were working before
        symbols_to_track = [
            "NIFTY 16 SEP 25000 CALL",  # Example option
            "NIFTY 16 SEP 25000 PUT",   # Example option
        ]
        
        # Add symbols
        for symbol in symbols_to_track:
            success = self.add_symbol(symbol)
            if not success:
                print(f"WARNING: Could not add symbol {symbol}")
        
        # Check if we have any valid symbols
        if not self.security_ids:
            print("ERROR: No valid symbols found. Please check the symbol names.")
            return
            
        # Connect to WebSocket
        if not self.connect_websocket():
            print("Failed to connect to WebSocket. Exiting...")
            return
            
        print("=" * 50)
        print("Ticker Logger is running. Press Ctrl+C to stop.")
        print("=" * 50)
        
        # Check market hours
        current_time = datetime.now(pytz.timezone('Asia/Kolkata'))
        print(f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S IST')}")
        
        # Check if market is open (9:15 AM to 3:30 PM IST)
        current_hour = current_time.hour
        current_minute = current_time.minute
        current_time_minutes = current_hour * 60 + current_minute
        
        market_open_minutes = 9 * 60 + 15  # 9:15 AM
        market_close_minutes = 15 * 60 + 30  # 3:30 PM
        
        if market_open_minutes <= current_time_minutes <= market_close_minutes:
            print("✅ Market is OPEN")
        else:
            print("❌ Market is CLOSED - You may not receive live data")
            print(f"Market hours: 09:15 AM - 03:30 PM IST")
        
        # Keep the script running with periodic status updates
        try:
            self.message_count = 0
            last_status_time = time.time()
            
            while True:
                time.sleep(1)
                
                # Show status every 30 seconds
                current_time_sec = time.time()
                if current_time_sec - last_status_time >= 30:
                    print(f"Status: Running for {int((current_time_sec - last_status_time) / 60)} minutes, received {self.message_count} messages")
                    last_status_time = current_time_sec
                    
        except KeyboardInterrupt:
            print("\nStopping ticker logger...")
            self.stop()
            
    def stop(self):
        """Stop the ticker logger"""
        if self.websocket:
            self.websocket.close()
            print("WebSocket connection closed")

def main():
    """Main function"""
    try:
        logger = SimpleTickerLogger()
        logger.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
