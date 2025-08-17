"""
Modular Trading Bot - Main entry point
Uses separate modules for different functionalities
"""

import os
import time
import pandas as pd
import struct
from datetime import datetime
from dotenv import load_dotenv
from collections import deque

# Import our modular components
from models.candle import Candle
from utils.market_utils import is_market_hours, is_trading_ending, round_to_tick
from strategies.candle_strategy import CandleStrategy
from brokers.dhan_broker import DhanBroker
from utils.market_data import MarketDataWebSocket, process_ticker_data
from position.position_manager import PositionManager

# Load environment variables
load_dotenv()

class DhanTradingBot:
    def __init__(self):
        self.client_id = os.getenv('DHAN_CLIENT_ID')
        self.access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        # Initialize components
        self.tick_size = float(os.getenv('TICK_SIZE', 0.05))
        self.broker = DhanBroker(self.client_id, self.access_token, self.tick_size)
        self.position_manager = PositionManager(self.broker, self.tick_size)
        self.strategy = CandleStrategy(self.tick_size)
        self.websocket = None
        
        # Market data
        self.market_data = {}
        self.instruments_df = None
        
        # Legacy candle tracking (for compatibility)
        self.candle_timeframe = int(os.getenv('CANDLE_TIMEFRAME', 15))
        self.max_candles = int(os.getenv('MAX_CANDLES', 100))
        self.candles = deque(maxlen=self.max_candles)
        self.current_candle = None
        self.last_candle_time = None
        
        print(f"Modular Trading Bot Configuration:")
        print(f"  Candle Timeframe: {self.candle_timeframe} minutes")
        print(f"  Max Candles: {self.max_candles}")
        print(f"  Tick Size: {self.tick_size}")
        print(f"  Strategy: 15-minute candle classification with 1-minute sweep detection")
        print(f"  Components: Broker, Position Manager, Strategy, WebSocket")
        
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
        return self.broker.get_security_id(symbol, self.instruments_df)
    
    def update_candle(self, price, timestamp):
        """Update or create a new candle based on the current price (legacy method)"""
        # Round the price to tick size
        price = round_to_tick(price, self.tick_size)
        
        # Get the current market time boundary (configurable intervals starting from 9:15:00)
        current_time = timestamp
        
        # Check if market is open (after 9:15 AM)
        if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 15):
            print(f"Market not open yet. Current time: {current_time.strftime('%H:%M:%S')}")
            return
        
        # Calculate the current period based on configurable timeframe
        total_seconds = (current_time.hour - 9) * 3600 + (current_time.minute - 15) * 60 + current_time.second
        period_number = total_seconds // self.candle_timeframe
        
        # Calculate the start time of this period
        period_start_seconds = period_number * self.candle_timeframe
        
        # Calculate the candle start time by adding seconds to market open time
        from datetime import timedelta
        market_open_time = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
        candle_start_time = market_open_time + timedelta(seconds=period_start_seconds)
        
        # If this is a new candle period, create a new candle
        if not self.current_candle or self.current_candle.timestamp != candle_start_time:
            # Save the previous candle if it exists
            if self.current_candle:
                self.candles.append(self.current_candle)
                print(f"\n✅ Candle Completed: O:{self.current_candle.open:.2f} H:{self.current_candle.high:.2f} L:{self.current_candle.low:.2f} C:{self.current_candle.close:.2f} | Time: {self.current_candle.timestamp.strftime('%H:%M:%S')}")
            
            # Create new candle aligned to market boundary
            self.current_candle = Candle(candle_start_time, price, price, price, price)
            print(f"🕯️ New Candle Started: O:{price:.2f} H:{price:.2f} L:{price:.2f} C:{price:.2f} | Time: {candle_start_time.strftime('%H:%M:%S')}")
        else:
            # Update existing candle
            self.current_candle.high = max(self.current_candle.high, price)
            self.current_candle.low = min(self.current_candle.low, price)
            self.current_candle.close = price
    
    def handle_market_data(self, ltp, timestamp, security_id):
        """Handle incoming market data"""
        # Update market data
        self.market_data[security_id] = {
            'ltp': ltp,
            'timestamp': timestamp
        }
        
        # Update candle data (legacy)
        self.update_candle(ltp, timestamp)
        
        # Update strategy candles
        self.strategy.update_15min_candle(ltp, timestamp)
        self.strategy.update_1min_candle(ltp, timestamp)
        
        # Check for sweep conditions and triggers
        if not self.position_manager.is_trading:
            trigger = self.strategy.check_sweep_conditions(self.strategy.current_1min_candle)
            if trigger:
                # Enter trade based on trigger
                symbol = os.getenv('SYMBOL')
                quantity = int(os.getenv('QUANTITY', 75))
                trigger_type = trigger.get('type', 'UNKNOWN')
                
                success = self.position_manager.enter_trade_with_trigger(
                    trigger, trigger_type, symbol, quantity, self.instruments_df
                )
                
                if success:
                    # Reset sweep detection after entering trade
                    self.strategy.reset_sweep_detection()
        else:
            # Check for target updates if already trading
            self.position_manager.check_and_update_target(ltp)
            
            # Check for trailing stop updates
            fvg = self.strategy.detect_1min_bullish_fvg()
            if fvg and fvg['type'] == 'bullish':
                self.position_manager.update_trailing_stop(ltp, fvg['stop_loss'])
    
    def on_websocket_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # Parse the binary data
            if len(message) < 16:
                print(f"Received incomplete data: {len(message)} bytes")
                return
                
            # Extract header information
            feed_code = message[0]  # 1 byte
            message_length = message[1]  # 1 byte
            exchange = int.from_bytes(message[2:4], byteorder='little')  # 2 bytes
            security_id = int.from_bytes(message[4:8], byteorder='little')  # 4 bytes
            
            # Check if this is data for our subscribed instrument
            expected_security_id = self.get_security_id(os.getenv('SYMBOL'))
            if expected_security_id and security_id != expected_security_id:
                return
            
            # Process different types of packets
            if feed_code == 2:  # Ticker data
                process_ticker_data(message, security_id, self.handle_market_data)
            elif feed_code == 4:  # Quote data
                from utils.market_data import process_quote_data
                process_quote_data(message, security_id)
            elif feed_code == 6:  # Market depth
                from utils.market_data import process_market_depth
                process_market_depth(message, security_id)
            else:
                print(f"Unknown feed code: {feed_code}")
                
        except Exception as e:
            print(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
    
    def on_websocket_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
        # Don't close the connection on error, let it retry
    
    def on_websocket_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        print(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        # Try to reconnect after a delay
        print("Attempting to reconnect in 10 seconds...")
        time.sleep(10)
        self.connect_websocket()
    
    def connect_websocket(self):
        """Connect to Dhan WebSocket API"""
        security_id = self.get_security_id(os.getenv('SYMBOL'))
        if not security_id:
            print("Could not get security ID for symbol")
            return False
        
        self.websocket = MarketDataWebSocket(
            access_token=self.access_token,
            client_id=self.client_id,
            on_message_callback=self.on_websocket_message,
            on_error_callback=self.on_websocket_error,
            on_close_callback=self.on_websocket_close
        )
        
        return self.websocket.connect(security_id)
    
    def check_market_end(self):
        """Check if we need to close position at market end"""
        if self.position_manager.is_trading and is_trading_ending():
            print("\nMarket ending soon, closing position...")
            symbol = os.getenv('SYMBOL')
            self.position_manager.close_position(symbol)
    
    def run_strategy(self, symbol, quantity):
        """Run the new 15-minute candle strategy with 1-minute sweep detection"""
        try:
            # Get security ID for the symbol
            security_id = self.get_security_id(symbol)
            if not security_id:
                print(f"Could not find security ID for symbol: {symbol}")
                return
                
            print(f"Found security ID: {security_id} for symbol: {symbol}")
            print("New 15-minute candle strategy started.")
            print("Waiting for 15-minute candles to complete and analyze...")
            print("Strategy will look for:")
            print("1. Bear/Neutral 15-minute candles")
            print("2. Sweep of their lows in 1-minute timeframe")
            print("3. IMPS (1-minute bullish FVG) or CISD (passing bear candle opens)")
            
            # Keep checking for market end
            while True:
                self.check_market_end()
                time.sleep(1)
                
        except Exception as e:
            print(f"Error in strategy: {e}")
            if self.websocket:
                self.websocket.close()
    
    def display_strategy_status(self):
        """Display current strategy status for monitoring"""
        status = self.strategy.get_strategy_status()
        print(f"\nStrategy Status:")
        print(f"  Waiting for Sweep: {'✅' if status['waiting_for_sweep'] else '❌'}")
        if status['sweep_low']:
            print(f"  Sweep Target Low: {status['sweep_low']:.2f}")
        print(f"  Sweep Detected: {'✅' if status['sweep_detected'] else '❌'}")
        print(f"  15-Min Candles: {status['fifteen_min_candles_count']}")
        print(f"  1-Min Candles: {status['one_min_candles_count']}")
        print(f"  Bear Candles Tracked: {status['bear_candles_tracked']}")
    
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
            if self.websocket:
                self.websocket.close()
        except Exception as e:
            print(f"Error in main loop: {e}")
            if self.websocket:
                self.websocket.close()

def main():
    load_dotenv()
    # Initialize the trading bot
    bot = DhanTradingBot()
    
    # Load instruments list
    print("Loading instruments list...")
    bot.load_instruments()
    
    # Initial cleanup of any orphaned orders
    print("Performing initial order cleanup...")
    bot.position_manager.cleanup_orphaned_orders()
    
    # Get symbol from environment variable
    symbol = os.getenv('SYMBOL')
    if not symbol:
        print("Error: SYMBOL environment variable not set")
        print("Please set SYMBOL in your .env file (e.g., SYMBOL=NIFTY 19 JUN 24900 CALL)")
        return
    
    print(f"Starting modular trading bot for symbol: {symbol}")
    
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
    print("Starting 15-minute candle sweep strategy...")
    bot.run_strategy(symbol, 75)  # Default quantity of 75
    
    # Keep the main thread alive with periodic validation
    validation_counter = 0
    try:
        while True:
            time.sleep(1)
            validation_counter += 1
            
            # Run periodic validation every 5 minutes (300 seconds)
            if validation_counter >= 300:
                bot.position_manager.periodic_order_validation()
                bot.display_strategy_status()
                validation_counter = 0
                
    except KeyboardInterrupt:
        print("\nShutting down trading bot...")
        # Final cleanup before shutdown
        bot.position_manager.cleanup_orphaned_orders()
        if bot.websocket:
            bot.websocket.close()

if __name__ == "__main__":
    main()
