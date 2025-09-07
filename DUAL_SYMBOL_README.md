# Dual Symbol Trading Implementation

## 🎯 Overview

The trading bot now supports **dual symbol trading** - monitoring and trading 2 symbols simultaneously while maintaining the constraint of only one active trade at a time. This implementation uses a minimal change strategy that preserves backward compatibility with single symbol trading.

## 🚀 Key Features

- **Simultaneous Monitoring**: Track 15-minute and 1-minute candles for both symbols
- **Single Trade Constraint**: Only one trade can be active at a time
- **Smart Trigger Selection**: When both symbols have triggers, the bot selects the best one
- **Backward Compatibility**: Single symbol mode continues to work unchanged
- **Live & Demo Support**: Works in both live trading and demo/backtesting modes

## 📋 How It Works

### 1. **Symbol Management**
- Each symbol gets its own `CandleStrategy` instance
- Independent candle tracking (15min + 1min) for each symbol
- Separate sweep detection and trigger generation

### 2. **Data Flow**
- Market data is routed to the appropriate symbol's strategy
- WebSocket connections support multiple security IDs
- Demo mode simulates data for both symbols

### 3. **Trade Selection Logic**
When both symbols have trade triggers, the bot selects based on:
1. **Trigger Type Priority**: IMPS (Fair Value Gap) > CISD (Change in State of Delivery)
2. **Entry Price**: Lower entry price preferred among same-type triggers
3. **First Come First Served**: If all else is equal, first trigger wins

### 4. **Trade Management**
- Only one trade can be active at a time
- Once a trade is entered, the bot focuses on managing that trade
- After trade exit, monitoring resumes for both symbols

## ⚙️ Configuration

### Environment Variables

Add these to your `.env` file:

```env
# For Live Trading
LIVE_SYMBOL=NIFTY 21 AUG 24700 CALL      # Primary symbol
LIVE_SYMBOL2=NIFTY 21 AUG 24700 PUT      # Secondary symbol

# For Demo Trading
DEMO_SYMBOL=NIFTY 21 AUG 24700 CALL      # Primary symbol
DEMO_SYMBOL2=NIFTY 21 AUG 24700 PUT      # Secondary symbol
```

### Single vs Dual Mode

- **Single Symbol Mode**: Set only `LIVE_SYMBOL` or `DEMO_SYMBOL` (existing behavior)
- **Dual Symbol Mode**: Set both `LIVE_SYMBOL` + `LIVE_SYMBOL2` or `DEMO_SYMBOL` + `DEMO_SYMBOL2`

## 🔧 Implementation Details

### New Components

1. **SymbolManager** (`strategies/symbol_manager.py`)
   - Manages multiple `CandleStrategy` instances
   - Handles trigger selection logic
   - Maintains single trade constraint

2. **Enhanced Configuration** (`utils/config.py`)
   - Added support for second symbol
   - Methods to detect dual symbol mode
   - Backward compatible with existing config

3. **Updated Trading Bot** (`trading_bot_dual_mode.py`)
   - Routes market data to appropriate symbol
   - Handles multiple WebSocket security IDs
   - Manages dual symbol strategy logic

### Modified Components

- **CandleStrategy**: No changes - works as before
- **PositionManager**: No changes - handles single trades
- **Broker Classes**: No changes - order placement unchanged

## 📊 Example Usage

### Configuration File
```env
# dual_symbol_config_example.env
TRADING_MODE=demo
DEMO_SYMBOL=NIFTY 21 AUG 24700 CALL
DEMO_SYMBOL2=NIFTY 21 AUG 24700 PUT
ACCT_START_BALANCE=50000
FIXED_SL_PERCENTAGE=10.0
```

### Running the Bot
```bash
# Copy the example config
cp dual_symbol_config_example.env .env

# Edit with your symbols
# Then run as usual
python trading_bot_dual_mode.py
```

## 🧪 Testing

Run the test script to verify the implementation:

```bash
python test_dual_symbol.py
```

This tests:
- Configuration parsing
- SymbolManager functionality
- Trigger selection logic
- Backward compatibility

## 📈 Trading Scenarios

### Scenario 1: Both Symbols Have Triggers
```
Symbol A (CALL): CISD trigger at 105.00
Symbol B (PUT):  IMPS trigger at 102.00
Result: Symbol B selected (IMPS > CISD)
```

### Scenario 2: Same Trigger Types
```
Symbol A (CALL): IMPS trigger at 105.00
Symbol B (PUT):  IMPS trigger at 102.00
Result: Symbol B selected (lower entry price)
```

### Scenario 3: One Symbol in Trade
```
Symbol A: Active trade (managing position)
Symbol B: New trigger detected
Result: Symbol B trigger ignored (single trade constraint)
```

## 🔍 Monitoring

The bot logs provide clear visibility into dual symbol operations:

```
Trading Symbols: NIFTY 21 AUG 24700 CALL (Primary), NIFTY 21 AUG 24700 PUT (Secondary)
Dual Symbol Mode: Will monitor both symbols but trade only one at a time
Selected best trigger from 2 options: NIFTY 21 AUG 24700 PUT - bullish
```

## ⚠️ Important Notes

1. **Single Trade Constraint**: The bot will never have more than one active trade
2. **Symbol Priority**: No inherent priority between symbols - selection is based on trigger quality
3. **Demo Mode**: Uses primary symbol's data for demo server, simulates second symbol
4. **Live Mode**: Requires valid security IDs for both symbols
5. **Backward Compatibility**: Existing single symbol configurations work unchanged

## 🚀 Benefits

- **Increased Opportunities**: Monitor more symbols for trade setups
- **Better Selection**: Choose the best trigger when multiple options exist
- **Risk Management**: Maintain single trade constraint for risk control
- **Minimal Changes**: Existing code and configurations remain functional

## 🔧 Troubleshooting

### Common Issues

1. **"No symbols configured"**: Ensure at least one symbol is set
2. **"Could not find security ID"**: Verify symbol names are correct
3. **WebSocket connection fails**: Check if both symbols are valid
4. **Demo mode issues**: Ensure primary symbol has valid historical data

### Debug Mode

Enable debug logging to see detailed symbol management:

```env
LOG_LEVEL=DEBUG
```

This will show:
- Symbol-specific candle updates
- Trigger detection for each symbol
- Selection logic decisions
- Trade entry/exit events

## 📝 Future Enhancements

Potential improvements for future versions:
- Weighted symbol priorities
- Dynamic symbol selection based on volatility
- Multi-timeframe analysis across symbols
- Advanced trigger scoring algorithms
