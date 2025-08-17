# Modular Trading Bot Architecture

## Overview

The trading bot has been refactored into a modular architecture for better maintainability, testability, and extensibility. Each module has a specific responsibility and can be developed, tested, and maintained independently.

## Project Structure

```
DhanOption/
├── models/
│   ├── __init__.py
│   └── candle.py              # Candle data model with classification
├── utils/
│   ├── __init__.py
│   └── market_utils.py        # Market utilities (time, price rounding)
├── strategies/
│   ├── __init__.py
│   └── candle_strategy.py     # 15-minute candle strategy logic
├── brokers/
│   ├── __init__.py
│   └── dhan_broker.py         # Dhan API interactions
├── websocket/
│   ├── __init__.py
│   └── market_data.py         # WebSocket market data handling
├── position/
│   ├── __init__.py
│   └── position_manager.py    # Position and order management
├── trading_bot.py             # Original monolithic bot
├── trading_bot_modular.py     # New modular bot
├── test_new_strategy.py       # Strategy testing
└── README files
```

## Module Descriptions

### 1. Models (`models/`)

#### `candle.py`
- **Purpose**: Data model for OHLC candles with classification logic
- **Key Features**:
  - Candle data structure (timestamp, open, high, low, close)
  - Body size and percentage calculations
  - Bull/Bear/Neutral classification methods
  - String representation for debugging

**Usage**:
```python
from models.candle import Candle

candle = Candle(timestamp, open_price, high, low, close)
print(f"Is Bull: {candle.is_bull_candle()}")
print(f"Body %: {candle.body_percentage():.1f}%")
```

### 2. Utils (`utils/`)

#### `market_utils.py`
- **Purpose**: Market-related utility functions
- **Key Features**:
  - Market hours checking
  - Trading end detection
  - Price rounding to tick size
  - Market boundary time calculations

**Usage**:
```python
from utils.market_utils import is_market_hours, round_to_tick

if is_market_hours():
    rounded_price = round_to_tick(price, tick_size=0.05)
```

### 3. Strategies (`strategies/`)

#### `candle_strategy.py`
- **Purpose**: 15-minute candle strategy implementation
- **Key Features**:
  - 15-minute and 1-minute candle tracking
  - Candle classification and analysis
  - Sweep detection logic
  - IMPS (1-minute FVG) detection
  - CISD (Change in State of Delivery) detection
  - Strategy status monitoring

**Usage**:
```python
from strategies.candle_strategy import CandleStrategy

strategy = CandleStrategy(tick_size=0.05)
strategy.update_15min_candle(price, timestamp)
strategy.update_1min_candle(price, timestamp)
trigger = strategy.check_sweep_conditions(candle)
```

### 4. Brokers (`brokers/`)

#### `dhan_broker.py`
- **Purpose**: Dhan API interactions and order management
- **Key Features**:
  - Security ID lookup
  - Order placement with targets and stop losses
  - Order modification (target updates)
  - Order cancellation
  - Error handling and logging

**Usage**:
```python
from brokers.dhan_broker import DhanBroker

broker = DhanBroker(client_id, access_token, tick_size=0.05)
order = broker.place_order(symbol, quantity, target_price=target, stop_loss_price=sl)
broker.modify_target(order_id, new_target)
broker.cancel_order(order_id)
```

### 5. WebSocket (`websocket/`)

#### `market_data.py`
- **Purpose**: WebSocket connection and market data processing
- **Key Features**:
  - WebSocket connection management
  - Market data subscription
  - Ticker data processing
  - Connection error handling and reconnection
  - Callback-based data handling

**Usage**:
```python
from websocket.market_data import MarketDataWebSocket

ws = MarketDataWebSocket(access_token, client_id, on_message_callback=handler)
ws.connect(security_id)
```

### 6. Position (`position/`)

#### `position_manager.py`
- **Purpose**: Position tracking and risk management
- **Key Features**:
  - Position state management
  - Order tracking and validation
  - Risk management (target updates, trailing stops)
  - Position closure
  - Order cleanup and validation

**Usage**:
```python
from position.position_manager import PositionManager

position_mgr = PositionManager(broker, tick_size=0.05)
success = position_mgr.enter_trade_with_trigger(trigger, trigger_type, symbol, quantity, instruments_df)
position_mgr.check_and_update_target(current_price)
position_mgr.close_position(symbol)
```

## Main Bot (`trading_bot_modular.py`)

The main bot orchestrates all modules:

```python
class DhanTradingBot:
    def __init__(self):
        # Initialize all components
        self.broker = DhanBroker(client_id, access_token, tick_size)
        self.position_manager = PositionManager(self.broker, tick_size)
        self.strategy = CandleStrategy(tick_size)
        self.websocket = None
```

## Benefits of Modular Architecture

### 1. **Separation of Concerns**
- Each module has a single responsibility
- Easy to understand and maintain
- Clear interfaces between components

### 2. **Testability**
- Each module can be tested independently
- Mock dependencies for unit testing
- Easier to write comprehensive tests

### 3. **Extensibility**
- Easy to add new strategies
- Simple to switch brokers
- Modular risk management

### 4. **Maintainability**
- Changes in one module don't affect others
- Clear code organization
- Easier debugging

### 5. **Reusability**
- Modules can be reused in other projects
- Strategy logic independent of broker
- Utility functions shared across modules

## Migration from Monolithic to Modular

### Before (Monolithic):
```python
# All logic in one large file
class DhanTradingBot:
    def __init__(self):
        # 1000+ lines of mixed responsibilities
        pass
    
    def place_order(self): pass
    def detect_fvg(self): pass
    def update_candle(self): pass
    # ... many more methods
```

### After (Modular):
```python
# Clean separation of concerns
class DhanTradingBot:
    def __init__(self):
        self.broker = DhanBroker(...)
        self.strategy = CandleStrategy(...)
        self.position_manager = PositionManager(...)
        self.websocket = MarketDataWebSocket(...)
```

## Usage

### Running the Modular Bot

```bash
# Run the modular version
python trading_bot_modular.py

# Run the original version (still available)
python trading_bot.py
```

### Testing Individual Modules

```bash
# Test the strategy
python -c "from strategies.candle_strategy import CandleStrategy; print('Strategy works!')"

# Test the broker
python -c "from brokers.dhan_broker import DhanBroker; print('Broker works!')"
```

## Configuration

The modular bot uses the same environment variables as the original:

```env
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
SYMBOL=NIFTY 19 JUN 24900 CALL
QUANTITY=75
TICK_SIZE=0.05
```

## Adding New Features

### Adding a New Strategy

1. Create a new file in `strategies/`
2. Implement the strategy interface
3. Update the main bot to use the new strategy

### Adding a New Broker

1. Create a new file in `brokers/`
2. Implement the broker interface
3. Update the position manager to use the new broker

### Adding New Utilities

1. Add functions to `utils/market_utils.py` or create new utility modules
2. Import and use in other modules as needed

## Testing

Each module includes its own tests and can be tested independently:

```python
# Test candle classification
from models.candle import Candle
candle = Candle(...)
assert candle.is_bull_candle() == True

# Test strategy logic
from strategies.candle_strategy import CandleStrategy
strategy = CandleStrategy()
# ... test strategy methods

# Test broker interactions
from brokers.dhan_broker import DhanBroker
broker = DhanBroker(...)
# ... test broker methods
```

## Future Enhancements

1. **Database Integration**: Add a data layer for historical data
2. **Configuration Management**: Centralized configuration system
3. **Logging**: Structured logging across all modules
4. **Monitoring**: Health checks and performance monitoring
5. **API Layer**: REST API for bot control and monitoring
6. **Backtesting**: Historical strategy testing framework

## Conclusion

The modular architecture provides a solid foundation for:
- Easy maintenance and debugging
- Independent testing of components
- Simple addition of new features
- Clear separation of responsibilities
- Better code organization and readability

This structure makes the trading bot more professional, maintainable, and extensible while preserving all existing functionality.
