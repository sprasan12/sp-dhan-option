"""
Strategy Manager - Manages multiple trading strategies
Checks strategies sequentially until a trade condition is found
"""

from typing import List, Dict, Optional, Callable
from models.candle import Candle
from strategies.candle_data import CandleData
from strategies.liquidity_tracker import LiquidityTracker
from strategies.erl_to_irl_strategy import ERLToIRLStrategy
from strategies.irl_to_erl_strategy import IRLToERLStrategy
from utils.logger import TradingLogger


class StrategyManager:
    """
    Manages multiple trading strategies and checks them sequentially
    Only one trade can be active at a time
    """
    
    def __init__(self, symbol: str, tick_size: float, logger: TradingLogger = None):
        self.position_manager = None
        self.current_target = None
        self.current_stop_loss = None
        self.entry_price = None
        self.symbol = symbol
        self.tick_size = tick_size
        self.logger = logger
        
        # Initialize candle data manager
        self.candle_data = CandleData(tick_size=tick_size, logger=logger, strategy_manager=self)
        
        # Initialize liquidity tracker
        self.liquidity_tracker = LiquidityTracker(logger=logger)
        
        # Set up 5-minute candle completion callback
        self.candle_data.set_5min_candle_callback(self._on_5min_candle_complete)
        
        # Initialize strategies
        self.strategies = []
        self._initialize_strategies()
        
        # Trade state management
        self.in_trade = False
        self.current_trade = None
        self.entry_callback = None
        self.exit_callback = None
        
        # Strategy state
        self.initialized = False
        
        if self.logger:
            self.logger.info(f"StrategyManager initialized for {symbol} with {len(self.strategies)} strategies")
    
    def _initialize_strategies(self):
        """Initialize all available strategies"""
        # ERL to IRL Strategy
        erl_to_irl = ERLToIRLStrategy(
            symbol=self.symbol,
            tick_size=self.tick_size,
            logger=self.logger,
            candle_data=self.candle_data
        )
        self.strategies.append({
            'name': 'ERL_to_IRL',
            'strategy': erl_to_irl,
            'enabled': True
        })
        
        # IRL to ERL Strategy
        irl_to_erl = IRLToERLStrategy(
            symbol=self.symbol,
            tick_size=self.tick_size,
            logger=self.logger,
            candle_data=self.candle_data
        )
        self.strategies.append({
            'name': 'IRL_to_ERL',
            'strategy': irl_to_erl,
            'enabled': True
        })
        
        if self.logger:
            self.logger.info(f"Initialized {len(self.strategies)} strategies: {[s['name'] for s in self.strategies]}")
    
    def _on_5min_candle_complete(self, candle: Candle):
        """
        Handle 5-minute candle completion by processing it through liquidity tracker
        
        Args:
            candle: The completed 5-minute candle
        """
        if not self.initialized:
            if self.logger:
                self.logger.debug("StrategyManager not initialized yet, skipping 5min candle processing")
            return
        
        if self.logger:
            self.logger.info(f"🕯️ PROCESSING 5-MINUTE CANDLE COMPLETION")
            self.logger.info(f"   Time: {candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"   OHLC: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
        
        try:
            # Process the completed 5-minute candle through liquidity tracker
            self.liquidity_tracker.process_candle(candle, '5min', self.symbol)
            
            # Check for mitigation of existing liquidity zones
            self.liquidity_tracker.check_and_mark_mitigation(candle)
            
            if self.logger:
                summary = self.liquidity_tracker.get_liquidity_summary()
                self.logger.info(f"   📊 Liquidity Summary: {summary['total_zones']} active zones")
                self.logger.info(f"      Bullish FVGs: {summary['bullish_fvgs']}, Bearish FVGs: {summary['bearish_fvgs']}")
                self.logger.info(f"      Bullish IFVGs: {summary['bullish_ifvgs']}, Bearish IFVGs: {summary['bearish_ifvgs']}")
                self.logger.info(f"   ✅ 5-minute candle processing completed")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Error processing 5-minute candle: {e}")
    
    def set_callbacks(self, entry_callback: Callable = None, exit_callback: Callable = None):
        """Set callback functions for trade entry and exit"""
        self.entry_callback = entry_callback
        self.exit_callback = exit_callback
        
        # Set callbacks for all strategies
        for strategy_info in self.strategies:
            strategy_info['strategy'].set_callbacks(entry_callback, exit_callback)
    
    def initialize_with_historical_data(self, historical_data: Dict[str, List[Candle]]) -> bool:
        """
        Initialize all strategies with historical data
        
        Args:
            historical_data: Dictionary with '5min' and '1min' candle lists
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self.logger:
            self.logger.info(f"Initializing StrategyManager with historical data for {self.symbol}")
        
        candles_5min = historical_data.get('5min', [])
        candles_1min = historical_data.get('1min', [])
        
        if not candles_5min or not candles_1min:
            if self.logger:
                self.logger.error("Missing historical data for strategy initialization")
            return False
        
        # Initialize liquidity tracker with historical data
        self.liquidity_tracker.add_historical_data(candles_5min, self.symbol)
        
        # Initialize candle data with historical candles
        # NOTE: We don't set initial candles here because they will be set when demo streaming starts
        # This prevents old historical candles from interfering with new demo session
        if self.logger:
            self.logger.info(f"Historical data loaded: {len(candles_5min)} 5m candles, {len(candles_1min)} 1m candles")
            if candles_5min:
                self.logger.info(f"Last historical 5m candle: {candles_5min[-1].timestamp.strftime('%H:%M:%S')}")
            if candles_1min:
                self.logger.info(f"Last historical 1m candle: {candles_1min[-1].timestamp.strftime('%H:%M:%S')}")
        
        # Initialize all strategies
        for strategy_info in self.strategies:
            if strategy_info['enabled']:
                success = strategy_info['strategy'].initialize_with_historical_data(self.symbol, historical_data)
                if not success:
                    if self.logger:
                        self.logger.warning(f"Failed to initialize strategy: {strategy_info['name']}")
                    strategy_info['enabled'] = False
        
        self.initialized = True
        self.candle_data.set_initial_5min_candle(candles_5min[-1])
        if self.logger:
            summary = self.liquidity_tracker.get_liquidity_summary()
            active_strategies = [s['name'] for s in self.strategies if s['enabled']]
            self.logger.info(f"StrategyManager initialized with {summary['total_zones']} active liquidity zones")
            self.logger.info(f"Active strategies: {active_strategies}")
        
        return True
    
    def update_1min_candle(self, candle_data, timestamp) -> Optional[Dict]:
        """
        Update with new 1-minute candle data and check all strategies
        
        Args:
            candle_data: Either a Candle object or Dictionary with OHLC data
            timestamp: Candle timestamp
        
        Returns:
            Trade trigger if found, None otherwise
        """
        if not self.initialized:
            if self.logger:
                self.logger.debug("StrategyManager not initialized yet")
            return None
        
        # Handle both Candle objects and dictionaries
        if isinstance(candle_data, Candle):
            candle = candle_data
            ohlc_data = {
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close
            }
        else:
            # It's a dictionary
            ohlc_data = candle_data
            candle = Candle(
                timestamp=timestamp,
                open_price=candle_data['open'],
                high=candle_data['high'],
                low=candle_data['low'],
                close=candle_data['close']
            )
        
        # Log strategy processing start
        if self.logger:
            self.logger.info(f"🔄 PROCESSING STRATEGIES")
            self.logger.info(f"   Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"   OHLC: O:{ohlc_data['open']:.2f} H:{ohlc_data['high']:.2f} L:{ohlc_data['low']:.2f} C:{ohlc_data['close']:.2f}")
        
        # Update candle data
        #self.candle_data.update_1min_candle_with_data(candle_data, timestamp)
        
        # Check for FVG/IFVG mitigation
        self.liquidity_tracker.check_and_mark_mitigation(candle)
        
        # If already in trade, check for exits instead of new entries
        if self.in_trade:
            if self.logger:
                self.logger.info(f"⏸️  ALREADY IN TRADE - Checking for exits")
            
            # Check for stop loss or target hit
            exit_result = self._check_for_trade_exit(candle)
            if exit_result:
                return exit_result
            
            return None
        
        # Check all strategies sequentially until one triggers
        for strategy_info in self.strategies:
            if not strategy_info['enabled']:
                continue
            
            strategy = strategy_info['strategy']
            strategy_name = strategy_info['name']
            
            try:
                # Log strategy check
                if self.logger:
                    self.logger.info(f"🔍 CHECKING STRATEGY: {strategy_name}")
                
                # Update strategy with candle data
                strategy.update_1m_candle( candle)
                
                # Check if strategy has triggered a trade
                if hasattr(strategy, 'in_trade') and strategy.in_trade:
                    # Get trade details from strategy
                    trade_details = self._get_trade_details_from_strategy(strategy, strategy_name)
                    if trade_details:
                        self.in_trade = True
                        self.current_trade = trade_details
                        
                        if self.logger:
                            self.logger.info(f"🎯 TRADE TRIGGERED BY {strategy_name.upper()} STRATEGY!")
                            self.logger.info(f"   📈 Entry: {trade_details['entry']:.2f}")
                            self.logger.info(f"   🛑 Stop Loss: {trade_details['stop_loss']:.2f}")
                            self.logger.info(f"   🎯 Target: {trade_details['target']:.2f}")
                            self.logger.info(f"   💰 Risk: {trade_details['entry'] - trade_details['stop_loss']:.2f}")
                            self.logger.info(f"   💎 Reward: {trade_details['target'] - trade_details['entry']:.2f}")
                        
                        return trade_details
                else:
                    if self.logger:
                        self.logger.info(f"❌ {strategy_name} - No trade condition met")
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ ERROR in {strategy_name} strategy: {e}")
                continue
        
        if self.logger:
            self.logger.info(f"✅ ALL STRATEGIES CHECKED - No trade conditions met")
        
        return None
    
    def _check_for_trade_exit(self, candle: Candle) -> Optional[Dict]:
        """
        Check if current candle should trigger a trade exit (stop loss or target hit)
        
        Args:
            candle: Current 1-minute candle
        
        Returns:
            Exit trigger if found, None otherwise
        """
        if not self.current_trade:
            return None
        
        current_price = candle.close
        entry_price = self.current_trade['entry']
        stop_loss = self.current_trade['stop_loss']
        target = self.current_trade['target']
        
        # Check for stop loss hit (price went below stop loss)
        if current_price <= stop_loss:
            if self.logger:
                self.logger.info(f"🛑 STOP LOSS HIT!")
                self.logger.info(f"   Current Price: {current_price:.2f}")
                self.logger.info(f"   Stop Loss: {stop_loss:.2f}")
                self.logger.info(f"   Entry Price: {entry_price:.2f}")
            
            # Reset trade state
            self.in_trade = False
            self.current_trade = None
            
            # Call exit callback
            if self.exit_callback:
                self.exit_callback(current_price, "stop_loss")
            
            return {
                'type': 'EXIT',
                'exit_price': current_price,
                'reason': 'stop_loss',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'target': target
            }
        
        # Check for target hit (price went above target)
        if current_price >= target:
            if self.logger:
                self.logger.info(f"🎯 TARGET HIT!")
                self.logger.info(f"   Current Price: {current_price:.2f}")
                self.logger.info(f"   Target: {target:.2f}")
                self.logger.info(f"   Entry Price: {entry_price:.2f}")
            
            # Reset trade state
            self.in_trade = False
            self.current_trade = None
            
            # Call exit callback
            if self.exit_callback:
                self.exit_callback(current_price, "target")
            
            return {
                'type': 'EXIT',
                'exit_price': current_price,
                'reason': 'target',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'target': target
            }
        
        return None
    
    def _get_trade_details_from_strategy(self, strategy, strategy_name: str) -> Optional[Dict]:
        """Extract trade details from a strategy"""
        try:
            # Get strategy status
            status = strategy.get_strategy_status()
            
            if status.get('in_trade', False):
                return {
                    'strategy_name': strategy_name,
                    'type': getattr(strategy, 'trade_type', 'Unknown'),
                    'entry': status.get('entry_price', 0),
                    'stop_loss': status.get('stop_loss', 0),
                    'target': status.get('target', 0),
                    'timestamp': self.candle_data.current_1min_candle.timestamp if self.candle_data.current_1min_candle else None
                }
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error extracting trade details from {strategy_name}: {e}")
        
        return None

    def get_status(self) -> Dict:
        """Get current status of all strategies and trade state"""
        status = {
            'initialized': self.initialized,
            'in_trade': self.in_trade,
            'current_trade': self.current_trade,
            'candle_data': self.candle_data.get_candle_summary(),
            'liquidity_summary': self.liquidity_tracker.get_liquidity_summary(),
            'strategies': []
        }
        
        for strategy_info in self.strategies:
            strategy_status = {
                'name': strategy_info['name'],
                'enabled': strategy_info['enabled'],
                'status': strategy_info['strategy'].get_strategy_status() if hasattr(strategy_info['strategy'], 'get_strategy_status') else {}
            }
            status['strategies'].append(strategy_status)
        
        return status
    
    def enable_strategy(self, strategy_name: str):
        """Enable a specific strategy"""
        for strategy_info in self.strategies:
            if strategy_info['name'] == strategy_name:
                strategy_info['enabled'] = True
                if self.logger:
                    self.logger.info(f"Enabled strategy: {strategy_name}")
                break
    
    def disable_strategy(self, strategy_name: str):
        """Disable a specific strategy"""
        for strategy_info in self.strategies:
            if strategy_info['name'] == strategy_name:
                strategy_info['enabled'] = False
                if self.logger:
                    self.logger.info(f"Disabled strategy: {strategy_name}")
                break
    
    def get_active_strategies(self) -> List[str]:
        """Get list of active strategy names"""
        return [s['name'] for s in self.strategies if s['enabled']]
