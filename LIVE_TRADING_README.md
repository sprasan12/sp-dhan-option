# Live Trading Setup Guide

## ⚠️ IMPORTANT WARNINGS

**LIVE TRADING INVOLVES REAL MONEY AND REAL RISKS!**

- This bot will place real orders with real money
- Always test with small quantities first
- Monitor the bot closely during live trading
- Ensure you have sufficient funds for the trades
- Be aware of market risks and potential losses

## 🚀 Setup Instructions

### 1. Environment Configuration

1. **Copy the configuration template:**
   ```bash
   cp live_trading_config_example.txt .env
   ```

2. **Edit the `.env` file with your credentials:**
   ```bash
   # Replace these with your actual Dhan credentials
   DHAN_CLIENT_ID=your_actual_client_id
   DHAN_ACCESS_TOKEN=your_actual_access_token
   TRADING_SYMBOL=NIFTY 21 AUG 24700 CALL
   
   # Set trading mode to live
   TRADING_MODE=live
   
   # Adjust account balance to match your actual balance
   ACCT_START_BALANCE=50000
   ```

### 2. Credential Requirements

**Dhan API Credentials:**
- **Client ID**: Your Dhan trading account client ID
- **Access Token**: Your Dhan API access token
- **Trading Symbol**: The exact option symbol you want to trade

**How to get credentials:**
1. Log into your Dhan trading account
2. Go to API settings/developers section
3. Generate API credentials
4. Note down Client ID and Access Token

### 3. Risk Management Settings

**Critical Parameters to Review:**

```bash
# Fixed Stop Loss Amount (10% of account balance)
FIXED_SL_PERCENTAGE=10.0

# Maximum SL as percentage of market price (15%)
MAX_SL_PERCENTAGE_OF_PRICE=15.0

# Trading quantity (start with 1 lot)
TRADING_QUANTITY=1

# Lot size (75 for NIFTY options)
LOT_SIZE=75
```

**Risk Calculation Example:**
- Account Balance: ₹50,000
- Fixed SL Amount: ₹5,000 (10% of balance)
- If market price is ₹100 and SL is ₹90:
  - Risk per lot = 75 × (100-90) = ₹750
  - Max lots = ₹5,000 ÷ ₹750 = 6 lots
- If SL is ₹85 (15% of ₹100), max lots = ₹5,000 ÷ ₹1,125 = 4 lots

### 4. Pre-Trading Checklist

✅ **Environment Setup:**
- [ ] `.env` file created with correct credentials
- [ ] `TRADING_MODE=live` set
- [ ] Account balance matches actual balance
- [ ] Trading symbol is correct and active

✅ **Risk Management:**
- [ ] Fixed SL percentage reviewed
- [ ] Max SL percentage of price reviewed
- [ ] Trading quantity set to small value (1 lot)
- [ ] Lot size matches the instrument

✅ **Market Conditions:**
- [ ] Market is open (9:15 AM - 3:30 PM IST)
- [ ] Option symbol is liquid and tradeable
- [ ] Sufficient funds in account
- [ ] No existing positions that conflict

✅ **System Setup:**
- [ ] Internet connection stable
- [ ] Bot running on reliable machine
- [ ] Logs directory exists
- [ ] All dependencies installed

### 5. Running Live Trading

**Start the bot:**
```bash
python trading_bot_dual_mode.py
```

**Expected startup sequence:**
1. ✅ Configuration validation
2. ✅ API connectivity test
3. ✅ Account balance verification
4. ✅ Instruments list loading
5. ✅ Historical data initialization
6. ✅ WebSocket connection
7. ⚠️ **LIVE TRADING MODE ACTIVE**

### 6. Monitoring Live Trading

**Key things to monitor:**

1. **Log Messages:**
   - Look for "LIVE TRADING MODE" warnings
   - Monitor order placement confirmations
   - Check for API errors or connection issues

2. **Trade Management:**
   - Entry orders and confirmations
   - Stop loss and target modifications
   - Position updates and P&L

3. **Risk Alerts:**
   - Account balance changes
   - Position size warnings
   - Stop loss hits

### 7. Emergency Procedures

**If something goes wrong:**

1. **Immediate Stop:**
   ```bash
   # Press Ctrl+C to stop the bot
   # The bot will attempt graceful shutdown
   ```

2. **Manual Position Management:**
   - Log into Dhan trading platform
   - Check current positions
   - Manually close positions if needed

3. **Check Logs:**
   - Review `logs/` directory for error details
   - Look for failed orders or API errors

### 8. Best Practices

**Before Live Trading:**
- ✅ Test thoroughly in demo mode first
- ✅ Start with small quantities (1 lot)
- ✅ Monitor the first few trades closely
- ✅ Have sufficient funds for multiple trades

**During Live Trading:**
- ✅ Keep the bot running on stable hardware
- ✅ Monitor logs regularly
- ✅ Don't interfere with running trades
- ✅ Have backup internet connection

**Risk Management:**
- ✅ Never risk more than you can afford to lose
- ✅ Set appropriate stop losses
- ✅ Don't override bot decisions manually
- ✅ Keep track of total P&L

### 9. Troubleshooting

**Common Issues:**

1. **API Connection Failed:**
   - Check internet connection
   - Verify credentials in `.env`
   - Ensure Dhan API is accessible

2. **Order Placement Failed:**
   - Check account balance
   - Verify symbol is tradeable
   - Check market hours

3. **WebSocket Disconnection:**
   - Bot will attempt reconnection
   - Check internet stability
   - Monitor reconnection attempts

4. **Position Not Closing:**
   - Check order status manually
   - Verify symbol and quantity
   - Contact Dhan support if needed

### 10. Support and Safety

**Emergency Contacts:**
- Dhan Trading Support: [Your Dhan support contact]
- Technical Issues: [Your technical contact]

**Safety Measures:**
- Always have a backup plan
- Keep emergency contact numbers handy
- Monitor account regularly
- Set up alerts for large position changes

---

## 🎯 Ready for Live Trading?

If you've completed all the setup steps and are confident with the risks, you're ready to start live trading. Remember:

**Start Small, Monitor Closely, Trade Responsibly!**

The bot is designed to be safe and conservative, but live trading always involves risks. Good luck with your trading!
