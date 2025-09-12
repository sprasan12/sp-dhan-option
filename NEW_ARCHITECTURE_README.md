# New Trading Bot Architecture

## Overview

The trading bot has been redesigned with a clean, modular architecture that separates concerns and provides better maintainability. The new architecture follows the flow you specified:

1. **Demo Server** fetches all history candles and builds LiquidityTracker data
2. **Demo Server** streams 1m candle data at set intervals (2s for example)
3. **CandleData** handles 1m candle updates, updates 5m candles, and manages liquidity tracker
4. **StrategyManager** applies all strategies sequentially until a trade condition is found
5. **Trade Management** ensures only one trade at a time, manages positions and balance
6. **After trade exit**, the system continues looking for the next trade

## Architecture Components

### 1. CandleData (`strategies/candle_data.py`)

**Purpose**: Central candle management and utility methods

**Key Features**:
- Manages 1m and 5m candle storage with deques (memory efficient)
- Provides utility methods for CISD, IMPS, Sweep, Sting detection
- Integrates with StrategyManager for trade detection
- Tracks session high/low, bear candles for analysis
- Handles candle classification and analysis

**Key Methods**:
- `update_1min_candle_with_data()` - Main entry point for candle updates
- `detect_imps()` - Detects 1-minute bullish Fair Value Gaps
- `detect_cisd()` - Detects passing open of bear candles
- `detect_sting()` - Detects stings into bullish FVG/IFVG zones
- `check_sweep_conditions()` - Checks for sweep conditions
- `get_candle_summary()` - Provides comprehensive candle data summary

### 2. StrategyManager (`strategies/strategy_manager.py`)

**Purpose**: Manages multiple trading strategies and checks them sequentially

**Key Features**:
- Manages ERL_to_IRL and IRL_to_ERL strategies
- Ensures only one trade can be active at a time
- Checks strategies sequentially until a trade condition is found
- Integrates with LiquidityTracker for FVG/IFVG management
- Provides strategy enable/disable functionality

**Key Methods**:
- `initialize_with_historical_data()` - Initializes all strategies with historical data
- `update_1min_candle()` - Processes candles through all strategies
- `exit_trade()` - Handles trade exits and resets state
- `get_status()` - Provides comprehensive status of all strategies
- `enable_strategy()` / `disable_strategy()` - Strategy management

### 3. LiquidityTracker (`strategies/liquidity_tracker.py`)

**Purpose**: Manages FVGs, Implied FVGs, and previous highs/lows for liquidity-based trading

**Key Features**:
- Tracks bullish/bearish FVGs and IFVGs
- Manages previous highs/lows and swing points
- Handles FVG/IFVG mitigation detection
- Provides efficient lookup methods for liquidity zones
- Supports historical data processing with 2-pass mitigation check

### 4. Demo Server (`demo/demo_server.py`)

**Purpose**: Streams historical market data (simplified, no strategy logic)

**Key Features**:
- Fetches and streams historical 1m candle data
- Configurable streaming intervals (default 2 seconds)
- Provides REST API for simulation control
- Simple data callback system for external processing
- No strategy logic - just data streaming

### 5. New Architecture Trading Bot (`trading_bot_new_architecture.py`)

**Purpose**: Main trading bot using the new architecture

**Key Features**:
- Uses CandleData + StrategyManager for clean separation
- Supports both live and demo trading modes
- Integrates with existing broker and position management
- Handles trade entry/exit callbacks
- Provides comprehensive logging and error handling

## Data Flow

```
1. Demo Server fetches historical data
   ↓
2. StrategyManager initializes with historical data
   ↓
3. Demo Server streams 1m candles (every 2s)
   ↓
4. CandleData receives candle updates
   ↓
5. CandleData updates 5m candles and liquidity tracker
   ↓
6. StrategyManager processes candles through all strategies
   ↓
7. If trade condition found → Enter trade
   ↓
8. While in trade → Continue updating candles, manage trade
   ↓
9. On trade exit → Reset state, continue looking for next trade
```

## Key Improvements

### 1. **Separation of Concerns**
- **CandleData**: Pure candle management and utility methods
- **StrategyManager**: Strategy orchestration and trade detection
- **Demo Server**: Simple data streaming
- **LiquidityTracker**: FVG/IFVG management

### 2. **Single Trade Management**
- Only one trade can be active at a time
- Clear trade state management
- Proper trade exit handling and state reset

### 3. **Sequential Strategy Checking**
- Strategies are checked in order until one triggers
- Easy to add new strategies
- Strategy enable/disable functionality

### 4. **Clean Integration**
- CandleData integrates with StrategyManager
- Demo Server just streams data
- Clear callback system for trade events

### 5. **Utility Methods**
- CISD, IMPS, Sweep, Sting detection in CandleData
- Comprehensive candle analysis
- Session tracking and bear candle management

## Usage

### Running the New Architecture Bot

```bash
python trading_bot_new_architecture.py
```

### Configuration

The bot uses the same configuration system as before:
- Set `MODE=demo` for demo trading
- Set `MODE=live` for live trading
- Configure symbol, tick size, and other parameters in `.env`

### Demo Mode Flow

1. Bot fetches historical data for the configured symbol
2. Initializes StrategyManager with historical data
3. Starts Demo Server with historical data
4. Demo Server streams 1m candles every 2 seconds
5. CandleData processes each candle and checks strategies
6. When trade condition found, enters trade
7. Manages trade until exit, then continues

### Live Mode Flow

1. Bot fetches historical data for initialization
2. Initializes StrategyManager with historical data
3. Connects to live market data WebSocket
4. Processes live price updates through CandleData
5. Checks strategies on each price update
6. Enters trades when conditions are met

## Strategy Integration

### Adding New Strategies

1. Create new strategy class inheriting from base strategy
2. Add to `StrategyManager._initialize_strategies()`
3. Strategy will be automatically checked in sequence

### Strategy Interface

Each strategy should implement:
- `initialize_with_historical_data()` - Initialize with historical data
- `update_1m_candle()` - Process new 1m candles
- `get_strategy_status()` - Return current status
- `exit_trade()` - Handle trade exits

## Benefits

1. **Maintainable**: Clear separation of concerns
2. **Extensible**: Easy to add new strategies
3. **Testable**: Each component can be tested independently
4. **Efficient**: Single trade management, optimized candle storage
5. **Flexible**: Strategy enable/disable, configurable streaming
6. **Robust**: Comprehensive error handling and logging

## Migration from Old Architecture

The new architecture maintains compatibility with:
- Existing broker interfaces
- Position management system
- Configuration system
- Logging system

To migrate:
1. Use `trading_bot_new_architecture.py` instead of `trading_bot_dual_mode.py`
2. Existing strategies (ERL_to_IRL, IRL_to_ERL) work without changes
3. Same configuration and environment setup
4. Same demo and live trading modes

## Future Enhancements

1. **Strategy Performance Tracking**: Track performance of individual strategies
2. **Dynamic Strategy Weighting**: Weight strategies based on performance
3. **Advanced Risk Management**: More sophisticated position sizing
4. **Strategy Backtesting**: Built-in backtesting capabilities
5. **Real-time Strategy Switching**: Switch strategies based on market conditions
