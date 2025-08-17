# Dual-Mode Trading Bot

A sophisticated trading bot that supports both **Live Trading** and **Demo Trading (Backtesting)** modes with the 15-minute candle classification strategy.

## Features

### 🚀 Live Trading Mode
- **Real-time Market Data**: Connects to Dhan WebSocket API for live streaming
- **Historical Initialization**: Fetches last 30 days of 15-minute candles on startup
- **Real Order Placement**: Places actual orders through Dhan broker account
- **Live P&L Tracking**: Real-time profit/loss monitoring
- **Market Hours Validation**: Only trades during market hours

### 🎯 Demo Trading Mode (Backtesting)
- **Historical Data Streaming**: Simulates market data from past dates
- **Virtual Trading**: No real money involved, perfect for strategy testing
- **P&L Calculation**: Comprehensive profit/loss analysis
- **Trade History**: Detailed record of all virtual trades
- **Performance Metrics**: Win rate, total P&L, and other statistics

### 📊 Strategy Implementation
- **15-Minute Candle Classification**: Bull, Bear, and Neutral candle detection
- **Sweep Detection**: Monitors for price breaking below specific lows
- **IMPS (1-Minute Bullish FVG)**: Fair Value Gap detection in 1-minute timeframe
- **CISD (Candle In Sweep Detection)**: Price passing bear candle opens
- **Risk Management**: Fixed 2:1 Risk:Reward ratio for all trades

## Architecture

```
DualModeTradingBot/
├── trading_bot_dual_mode.py     # Main entry point
├── utils/
│   ├── config.py                # Configuration management
│   ├── historical_data.py       # Historical data fetching
│   └── market_utils.py          # Market utilities
├── brokers/
│   ├── dhan_broker.py           # Live trading broker
│   └── demo_broker.py           # Virtual trading broker
├── demo/
│   ├── demo_server.py           # Historical data streaming server
│   └── demo_data_client.py      # Demo data client
├── models/
│   └── candle.py                # Candle data model
├── strategies/
│   └── candle_strategy.py       # Trading strategy logic
├── position/
│   └── position_manager.py      # Position and order management
└── websocket/
    └── market_data.py           # WebSocket handling
```

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd DhanOption
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   Create a `.env` file with your settings:
   ```env
   # Trading Mode
   TRADING_MODE=demo  # or 'live'
   
   # Live Trading (required for live mode)
   DHAN_CLIENT_ID=your_client_id
   DHAN_ACCESS_TOKEN=your_access_token
   
   # Common Settings
   TICK_SIZE=0.05
   MAX_15MIN_CANDLES=30
   TRADING_SYMBOL=NIFTY24JAN19000CE
   
   # Demo Settings
DEMO_START_DATE=2024-12-15  # Set to recent date for demo trading
DEMO_INTERVAL_MINUTES=1
DEMO_STREAM_INTERVAL_SECONDS=1.0  # How fast to stream each candle (lower = faster backtesting)
DEMO_SERVER_PORT=8080
HISTORICAL_DATA_DAYS=7
   ```

## Usage

### Demo Mode (Recommended for Testing)

1. **Set mode to demo**:
   ```env
   TRADING_MODE=demo
   ```

2. **Run the bot**:
   ```bash
   python trading_bot_dual_mode.py
   # or
   run_bot.bat
   ```

3. **Monitor the demo server**:
   - Server runs on `http://localhost:8080`
   - View status: `http://localhost:8080/`
   - Control simulation: `/start`, `/stop`, `/reset`

### Backtesting Speed Optimization

To speed up backtesting, you can configure the streaming speed:

```env
# Very fast backtesting (0.1 seconds per candle)
DEMO_STREAM_INTERVAL_SECONDS=0.1

# Fast backtesting (0.5 seconds per candle)  
DEMO_STREAM_INTERVAL_SECONDS=0.5

# Normal speed (1 second per candle)
DEMO_STREAM_INTERVAL_SECONDS=1.0

# Slower for detailed monitoring (2 seconds per candle)
DEMO_STREAM_INTERVAL_SECONDS=2.0
```

**Note**: Lower values make backtesting much faster but may make it harder to monitor the bot's behavior in real-time.

### Live Mode

1. **Set mode to live**:
   ```env
   TRADING_MODE=live
   ```

2. **Configure Dhan credentials**:
   ```env
   DHAN_CLIENT_ID=your_actual_client_id
   DHAN_ACCESS_TOKEN=your_actual_access_token
   ```

3. **Run the bot**:
   ```bash
   python trading_bot_dual_mode.py
   ```

## Configuration Options

### Trading Mode
- `TRADING_MODE`: Set to `live` or `demo`

### Live Trading
- `DHAN_CLIENT_ID`: Your Dhan client ID
- `DHAN_ACCESS_TOKEN`: Your Dhan access token
- `TRADING_SYMBOL`: Symbol to trade (e.g., NIFTY24JAN19000CE)

### Demo Trading
- `DEMO_START_DATE`: Start date for backtesting (YYYY-MM-DD) - **Important: Set to recent date for current data**
- `DEMO_INTERVAL_MINUTES`: Data streaming interval (default: 1)
- `DEMO_STREAM_INTERVAL_SECONDS`: How fast to stream each candle (default: 1.0) - **Set to lower values for faster backtesting**
- `DEMO_SERVER_PORT`: Demo server port (default: 8080)
- `HISTORICAL_DATA_DAYS`: Days of historical data to fetch (default: 7)

**Note:** You can configure the demo start date directly in the `.env` file or by setting the `DEMO_START_DATE` environment variable.

### Common Settings
- `TICK_SIZE`: Price tick size (default: 0.05)
- `MAX_15MIN_CANDLES`: Maximum 15-minute candles to maintain (default: 30)

## Strategy Details

### 15-Minute Candle Classification
- **Bull Candle**: Close > Open and body ≥ 50% of total candle length
- **Bear Candle**: Open > Close and body ≥ 50% of total candle length
- **Neutral Candle**: Body < 50% of total candle length

### Sweep Detection
- Monitors for price breaking below the low of bear or neutral 15-minute candles
- Triggers transition to 1-minute timeframe analysis

### Trade Entry Conditions

#### IMPS (1-Minute Bullish FVG)
- **Condition**: 1-minute bullish Fair Value Gap after sweep
- **Stop Loss**: Low of candle 1 (of the FVG)
- **Target**: 2:1 Risk:Reward ratio

#### CISD (Candle In Sweep Detection)
- **Condition**: Price passes the open of bear candle(s) that helped in sweeping
- **Stop Loss**: Low of lowest tracked bear candle
- **Target**: 2:1 Risk:Reward ratio

## API Endpoints (Demo Mode)

### Demo Server Endpoints
- `GET /`: Server status and configuration
- `GET /start`: Start simulation
- `GET /stop`: Stop simulation
- `GET /reset`: Reset simulation to start
- `GET /current_candle`: Get current candle data
- `GET /streamed_candles`: Get all streamed candles
- `POST /set_time`: Set simulation time

### Example Usage
```bash
# Check server status
curl http://localhost:8080/

# Start simulation
curl http://localhost:8080/start

# Get current candle
curl http://localhost:8080/current_candle
```

## Monitoring and Logs

### Live Mode
- Real-time price updates via WebSocket
- Order placement confirmations
- Position updates and P&L tracking

### Demo Mode
- Historical data streaming simulation
- Virtual order placement logs
- Comprehensive P&L analysis
- Trade history and performance metrics

## Safety Features

### Live Trading
- Market hours validation
- Order validation before placement
- Error handling and retry mechanisms
- Graceful shutdown on interruption

### Demo Trading
- No real money involved
- Complete simulation environment
- Detailed logging and analysis
- Safe for strategy testing

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed (Live Mode)**
   - Check Dhan credentials
   - Verify internet connection
   - Ensure market hours

2. **Historical Data Fetch Failed (Demo Mode)**
   - Check symbol validity
   - Verify date range
   - Ensure Dhan API access

3. **Demo Server Not Starting**
   - Check port availability
   - Verify Flask installation
   - Check firewall settings

### Debug Mode
Enable detailed logging by setting:
```env
DEBUG=true
```

## Performance Metrics

### Demo Mode Reports
- Total P&L
- Win rate percentage
- Number of trades
- Average trade duration
- Maximum drawdown
- Risk-adjusted returns

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Disclaimer

- **Live Trading**: Trading involves risk. Use at your own discretion.
- **Demo Trading**: For educational and testing purposes only.
- **No Financial Advice**: This software is not financial advice.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error messages
3. Create an issue with detailed information
