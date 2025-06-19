#!/usr/bin/env python3
"""
Simple script to run the Dhan Trading Bot
"""

import os
import sys
import time
from trading_bot import DhanTradingBot

def main():
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("Error: .env file not found!")
        print("Please create a .env file with your Dhan credentials:")
        print("DHAN_CLIENT_ID=your_client_id")
        print("DHAN_ACCESS_TOKEN=your_access_token")
        print("SYMBOL=NIFTY 19 JUN 24900 CALL")
        return
    
    # Check required environment variables
    required_vars = ['DHAN_CLIENT_ID', 'DHAN_ACCESS_TOKEN', 'SYMBOL']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Error: Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return
    
    # Initialize and run the bot
    try:
        bot = DhanTradingBot()
        
        # Load instruments list
        print("Loading instruments list...")
        bot.load_instruments()
        
        # Get symbol
        symbol = os.getenv('SYMBOL')
        print(f"Starting trading bot for symbol: {symbol}")
        
        # Start WebSocket connection
        print("Connecting to Dhan WebSocket...")
        connection_success = bot.connect_websocket()
        
        if not connection_success:
            print("\n❌ Failed to establish WebSocket connection!")
            print("\nTroubleshooting steps:")
            print("1. Check your internet connection")
            print("2. Verify Dhan API credentials in .env file")
            print("3. Check if Dhan servers are accessible")
            print("4. Try disabling firewall/proxy temporarily")
            print("5. Check if you're behind a corporate network")
            print("\nYou can also try:")
            print("- Restarting your computer")
            print("- Using a different network")
            print("- Contacting Dhan support")
            return
        
        # Wait for connection to establish
        print("Waiting for connection to establish...")
        time.sleep(3)
        
        # Run the strategy
        print("Starting FVG strategy...")
        bot.run_strategy(symbol, 75)
        
    except KeyboardInterrupt:
        print("\nShutting down trading bot...")
        if 'bot' in locals() and bot.ws:
            bot.ws.close()
    except Exception as e:
        print(f"Error: {e}")
        if 'bot' in locals() and bot.ws:
            bot.ws.close()

if __name__ == "__main__":
    main() 