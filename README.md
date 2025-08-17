# Dhan Options Trading Bot

A Python-based options trading bot for NSE using Dhan broker's API (DhanHQ API v2). The bot implements a **15-minute candle strategy with 1-minute sweep detection** featuring IMPS (Fair Value Gap) and CISD (Change in State of Delivery) triggers.

## 🚀 New Modular Architecture

The bot has been refactored into a clean, modular architecture for better maintainability and extensibility. See `MODULAR_README.md` for detailed documentation.

## Features

- **15-Minute Candle Strategy**: Classifies candles as Bull/Bear/Neutral based on body percentage
- **1-Minute Sweep Detection**: Detects sweeps of 15-minute candle lows
- **IMPS Trigger**: 1-minute bullish Fair Value Gap detection
- **CISD Trigger**: Change in State of Delivery (passing bear candle opens)
- **2:1 Risk:Reward**: Fixed 2:1 ratio for both IMPS and CISD triggers
- **Live Market Data**: Real-time tick-by-tick data via WebSocket
- **Automated Trading**: Places orders with target and stop loss
- **Dynamic Targets**: Updates targets based on price movement (50% → 1:2, 100% → 1:4)
- **Price Rounding**: Automatically rounds prices to tick size (0.05 INR)
- **Modular Architecture**: Clean separation of concerns for easy maintenance

## Configuration

Create a `.env` file with the following parameters:

```env
# Dhan API Credentials
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token

# Trading Symbol
SYMBOL=NIFTY 19 JUN 24900 CALL
QUANTITY=75

# Strategy Configuration
CANDLE_TIMEFRAME=5          # Candle timeframe in seconds (default: 5)
MAX_CANDLES=100             # Maximum candles to store (default: 100)
TICK_SIZE=0.05              # Price tick size in INR (default: 0.05)

# Risk Management
INITIAL_RISK_REWARD=1.0     # Initial risk:reward ratio (default: 1.0)
TARGET_UPDATE_50_PERCENT=0.5  # Update target at 50% move (default: 0.5)
TARGET_UPDATE_100_PERCENT=1.0 # Update target at 100% move (default: 1.0)
```

## Strategy Logic

1. **15-Minute Candle Classification**: 
   - Bull Candle: Close > Open and body ≥ 50% of total size
   - Bear Candle: Open > Close and body ≥ 50% of total size  
   - Neutral Candle: body < 50% of total size

2. **Sweep Detection**: Waits for 1-minute candles to sweep the low of bear/neutral 15-minute candles

3. **Trigger Detection**:
   - **IMPS**: 1-minute bullish FVG (c3.low > c1.high) with stop loss at c1.low
   - **CISD**: Price passes open of bear candle with stop loss at lowest bear low

4. **Trade Entry**: Places market order with 2:1 risk:reward ratio

5. **Dynamic Targets**: 
   - At 50% move in favor: Updates target to 1:2
   - At 100% move in favor: Updates target to 1:4

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your `.env` file with API credentials
4. Run the bot:
   ```bash
   python trading_bot_modular.py
   ```

## Testing

Test individual modules:
```bash
# Test strategy components
python -c "from strategies.candle_strategy import CandleStrategy; print('Strategy works!')"

# Test broker components  
python -c "from brokers.dhan_broker import DhanBroker; print('Broker works!')"
```

## Files

- `trading_bot_modular.py`: Main modular trading bot
- `models/`: Candle data models and classification
- `strategies/`: 15-minute candle strategy implementation
- `brokers/`: Dhan API interactions
- `websocket/`: Market data WebSocket handling
- `position/`: Position and order management
- `utils/`: Market utilities and helpers
- `requirements.txt`: Python dependencies
- `run_bot.bat`: Windows batch script to run the bot
- `setup.bat`: Windows batch script to set up virtual environment
- `MODULAR_README.md`: Detailed modular architecture documentation

## Trading Parameters

- **15-Minute Candles**: For candle classification and sweep detection
- **1-Minute Candles**: For sweep detection and trigger identification
- **Default Quantity**: 75 lots
- **Market Hours**: 9:15 AM to 3:30 PM IST
- **Position Closure**: 5 minutes before market end
- **Risk:Reward**: 2:1 for both IMPS and CISD triggers

## Important Notes

⚠️ **Risk Warning**: This is a live trading bot. Use at your own risk and ensure you understand the strategy before deploying with real money.

⚠️ **Testing**: Always test with small quantities first and monitor the bot's performance.

⚠️ **Market Hours**: The bot only trades during market hours (9:15 AM to 3:30 PM IST).

## File Structure

```
DhanOption/
├── trading_bot_modular.py  # Main modular trading bot
├── models/                 # Candle data models
├── strategies/             # 15-minute candle strategy
├── brokers/                # Dhan API interactions
├── websocket/              # Market data handling
├── position/               # Position management
├── utils/                  # Market utilities
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── MODULAR_README.md      # Detailed architecture docs
├── .env                   # Environment variables (create this)
└── dhan_instruments.csv   # Downloaded instruments list
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