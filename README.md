# Dhan Trading Bot

A Python-based trading bot for options trading on NSE using the Dhan API. The bot implements a Fair Value Gap (FVG) strategy for automated trading.

## Features

- **Real-time Market Data**: Connects to Dhan WebSocket API for live market data
- **FVG Strategy**: Detects Fair Value Gaps and executes trades automatically
- **Trailing Stop Loss**: Updates stop loss based on new FVGs
- **Market End Management**: Automatically closes positions 5 minutes before market end
- **Options Trading**: Specifically designed for NSE options trading

## Strategy Details

The bot implements a Fair Value Gap (FVG) strategy:

1. **Candle Formation**: Creates 15-second candles from ticker data
2. **FVG Detection**: Identifies bullish FVGs when C3 low > C1 high
3. **Trade Entry**: Enters long positions immediately upon FVG detection
4. **Initial Orders**: Places three orders simultaneously:
   - **Buy Order**: Market order to enter the position
   - **Stop Loss Order**: At C2 low (candle 2 low)
   - **Take Profit Order**: With 1:1.1 risk:reward ratio
5. **Trailing Stop**: When new FVGs form:
   - Cancels existing stop loss and take profit orders
   - Places new stop loss at the bottom of the latest FVG
   - No new take profit order (lets the trade run)
6. **Position Closure**: Closes positions 5 minutes before market end

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd DhanTrade
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Create a `.env` file in the project root:
```env
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
SYMBOL=NIFTY 19 JUN 24900 CALL
```

2. Replace the values with your actual Dhan API credentials and desired trading symbol.

## Usage

### Method 1: Using the run script
```bash
python run_bot.py
```

### Method 2: Direct execution
```bash
python trading_bot.py
```

## Trading Parameters

- **Candle Timeframe**: 15 seconds
- **Max Candles**: 100 (for FVG detection)
- **Default Quantity**: 75 lots
- **Market Hours**: 9:15 AM to 3:30 PM IST
- **Position Closure**: 5 minutes before market end

## Important Notes

⚠️ **Risk Warning**: This is a live trading bot. Use at your own risk and ensure you understand the strategy before deploying with real money.

⚠️ **Testing**: Always test with small quantities first and monitor the bot's performance.

⚠️ **Market Hours**: The bot only trades during market hours (9:15 AM to 3:30 PM IST).

## File Structure

```
DhanTrade/
├── trading_bot.py      # Main trading bot implementation
├── run_bot.py          # Simple run script
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── .env               # Environment variables (create this)
└── dhan_instruments.csv # Downloaded instruments list
```

## Dependencies

- `dhanhq==2.0.0` - Dhan API client
- `websocket-client==1.6.4` - WebSocket client
- `python-dotenv==1.0.0` - Environment variable management
- `pandas==2.0.3` - Data manipulation
- `numpy==1.24.3` - Numerical operations
- `requests==2.31.0` - HTTP requests

## Troubleshooting

1. **Connection Issues**: Ensure your internet connection is stable
2. **API Credentials**: Verify your Dhan API credentials are correct
3. **Symbol Format**: Use the exact symbol format from Dhan's instrument list
4. **Market Hours**: The bot only works during market hours

## Support

For issues or questions, please check the Dhan API documentation or contact support. 