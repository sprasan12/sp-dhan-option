#!/usr/bin/env python3
"""
Run the trading bot with DEBUG logging enabled
This script sets the LOG_LEVEL environment variable to DEBUG and runs the bot
"""

import os
import sys
from dotenv import load_dotenv

# Set DEBUG logging before importing other modules
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['LOG_TO_FILE'] = 'true'
os.environ['LOG_DIR'] = 'logs'

# Set demo mode and symbols for dual trading
os.environ['TRADING_MODE'] = 'demo'
os.environ['DEMO_SYMBOL'] = 'NIFTY 09 SEP 24800 CALL'
os.environ['DEMO_SYMBOL2'] = 'NIFTY 09 SEP 24800 PUT'

# Set other demo settings
os.environ['DEMO_START_DATE'] = '2025-09-01'
os.environ['DEMO_STREAM_INTERVAL_SECONDS'] = '2.0'
os.environ['DEMO_SERVER_PORT'] = '8080'

# Load any existing .env file
load_dotenv()

print("🚀 Starting Trading Bot with DEBUG Logging")
print("=" * 60)
print("Configuration:")
print(f"  LOG_LEVEL: {os.environ.get('LOG_LEVEL', 'INFO')}")
print(f"  LOG_TO_FILE: {os.environ.get('LOG_TO_FILE', 'false')}")
print(f"  LOG_DIR: {os.environ.get('LOG_DIR', 'logs')}")
print(f"  TRADING_MODE: {os.environ.get('TRADING_MODE', 'demo')}")
print(f"  DEMO_SYMBOL: {os.environ.get('DEMO_SYMBOL', 'Not set')}")
print(f"  DEMO_SYMBOL2: {os.environ.get('DEMO_SYMBOL2', 'Not set')}")
print("=" * 60)
print("All console output will be saved to log files in the 'logs' directory")
print("Press Ctrl+C to stop the bot")
print("=" * 60)

# Import and run the trading bot
try:
    from trading_bot_dual_mode import DualModeTradingBot
    
    # Create and run the bot
    bot = DualModeTradingBot()
    bot.run()
    
except KeyboardInterrupt:
    print("\n🛑 Bot stopped by user")
except Exception as e:
    print(f"\n❌ Error running bot: {e}")
    import traceback
    traceback.print_exc()
