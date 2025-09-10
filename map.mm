<?xml version="1.0" encoding="UTF-8"?>
<map version="1.0.1">
<node TEXT="DhanOptionV2">
  <node TEXT="brokers">
    <node TEXT="__init__.py">
    </node>
    <node TEXT="demo_broker.py">
      <node TEXT="DemoBroker">
        <node TEXT="get_security_id()">
        </node>
        <node TEXT="get_account_balance()">
        </node>
        <node TEXT="place_order()">
        </node>
        <node TEXT="modify_target()">
        </node>
        <node TEXT="cancel_order()">
        </node>
        <node TEXT="get_positions()">
        </node>
        <node TEXT="get_trade_history()">
        </node>
        <node TEXT="get_order_history()">
        </node>
        <node TEXT="get_account_summary()">
        </node>
        <node TEXT="print_account_summary()">
        </node>
      </node>
    </node>
    <node TEXT="dhan_broker.py">
      <node TEXT="DhanBroker">
        <node TEXT="get_security_id()">
        </node>
        <node TEXT="get_account_balance()">
        </node>
        <node TEXT="place_order()">
        </node>
        <node TEXT="modify_target()">
        </node>
        <node TEXT="modify_stop_loss()">
        </node>
        <node TEXT="cancel_order()">
        </node>
        <node TEXT="cancel_target_leg()">
        </node>
        <node TEXT="cancel_stop_loss_leg()">
        </node>
        <node TEXT="cancel_entry_leg()">
        </node>
        <node TEXT="get_positions()">
        </node>
        <node TEXT="get_order_status()">
        </node>
        <node TEXT="print_account_summary()">
        </node>
      </node>
    </node>
  </node>
  <node TEXT="demo">
    <node TEXT="__init__.py">
    </node>
    <node TEXT="demo_data_client.py">
      <node TEXT="DemoDataClient">
        <node TEXT="connect()">
        </node>
        <node TEXT="start_simulation()">
        </node>
        <node TEXT="stop_simulation()">
        </node>
        <node TEXT="reset_simulation()">
        </node>
        <node TEXT="set_callback()">
        </node>
        <node TEXT="start_data_stream()">
        </node>
        <node TEXT="stop_data_stream()">
        </node>
        <node TEXT="get_current_price()">
        </node>
        <node TEXT="get_current_timestamp()">
        </node>
        <node TEXT="get_server_status()">
        </node>
        <node TEXT="get_streamed_candles()">
        </node>
      </node>
    </node>
    <node TEXT="demo_server.py">
      <node TEXT="DemoServer">
        <node TEXT="setup_routes()">
        </node>
        <node TEXT="start_simulation()">
        </node>
        <node TEXT="stop_simulation()">
        </node>
        <node TEXT="reset_simulation()">
        </node>
        <node TEXT="set_simulation_time()">
        </node>
        <node TEXT="run()">
        </node>
        <node TEXT="get_current_price()">
        </node>
        <node TEXT="get_current_timestamp()">
        </node>
      </node>
    </node>
    <node TEXT="multi_symbol_demo_client.py">
      <node TEXT="MultiSymbolDemoClient">
        <node TEXT="connect()">
        </node>
        <node TEXT="start_simulation()">
        </node>
        <node TEXT="stop_simulation()">
        </node>
        <node TEXT="reset_simulation()">
        </node>
        <node TEXT="set_callback()">
        </node>
        <node TEXT="start_data_stream()">
        </node>
        <node TEXT="stop_data_stream()">
        </node>
        <node TEXT="get_current_candles()">
        </node>
        <node TEXT="get_current_candle()">
        </node>
        <node TEXT="get_current_timestamp()">
        </node>
        <node TEXT="get_server_status()">
        </node>
      </node>
    </node>
    <node TEXT="multi_symbol_demo_server.py">
      <node TEXT="MultiSymbolDemoServer">
        <node TEXT="setup_routes()">
        </node>
        <node TEXT="set_simulation_time()">
        </node>
        <node TEXT="run()">
        </node>
        <node TEXT="get_current_candles()">
        </node>
        <node TEXT="get_current_timestamp()">
        </node>
      </node>
    </node>
  </node>
  <node TEXT="logs">
  </node>
  <node TEXT="models">
    <node TEXT="__init__.py">
    </node>
    <node TEXT="candle.py">
      <node TEXT="Candle">
        <node TEXT="size()">
        </node>
        <node TEXT="body_size()">
        </node>
        <node TEXT="body_percentage()">
        </node>
        <node TEXT="is_bull_candle()">
        </node>
        <node TEXT="is_bear_candle()">
        </node>
        <node TEXT="is_neutral_candle()">
        </node>
      </node>
    </node>
  </node>
  <node TEXT="position">
    <node TEXT="__init__.py">
    </node>
    <node TEXT="position_manager.py">
      <node TEXT="PositionManager">
        <node TEXT="check_existing_orders()">
        </node>
        <node TEXT="validate_order_state()">
        </node>
        <node TEXT="cleanup_orphaned_orders()">
        </node>
        <node TEXT="enter_trade_with_trigger()">
        </node>
        <node TEXT="check_and_update_target()">
        </node>
        <node TEXT="update_trailing_stop()">
        </node>
        <node TEXT="handle_trade_exit()">
        </node>
        <node TEXT="close_position()">
        </node>
        <node TEXT="display_order_status()">
        </node>
        <node TEXT="periodic_order_validation()">
        </node>
      </node>
    </node>
  </node>
  <node TEXT="strategies">
    <node TEXT="__init__.py">
    </node>
    <node TEXT="candle_strategy.py">
      <node TEXT="CandleStrategy">
        <node TEXT="update_15min_candle()">
        </node>
        <node TEXT="update_15min_candle_from_1min()">
        </node>
        <node TEXT="update_5min_candle_from_1min()">
        </node>
        <node TEXT="update_1min_candle()">
        </node>
        <node TEXT="update_1min_candle_with_data()">
        </node>
        <node TEXT="get_candle_type()">
        </node>
        <node TEXT="classify_and_analyze_15min_candle()">
        </node>
        <node TEXT="check_sweep_conditions()">
        </node>
        <node TEXT="detect_1min_bullish_fvg()">
        </node>
        <node TEXT="detect_15min_bullish_fvg()">
        </node>
        <node TEXT="detect_cisd()">
        </node>
        <node TEXT="reset_sweep_detection()">
        </node>
        <node TEXT="update_session_high_low()">
        </node>
        <node TEXT="is_potential_swing_low()">
        </node>
        <node TEXT="is_days_low_sweep()">
        </node>
        <node TEXT="calculate_target_ratio()">
        </node>
        <node TEXT="get_strategy_status()">
        </node>
        <node TEXT="enter_trade()">
        </node>
        <node TEXT="exit_trade()">
        </node>
        <node TEXT="detect_swing_low()">
        </node>
        <node TEXT="update_swing_lows()">
        </node>
        <node TEXT="should_move_stop_loss()">
        </node>
        <node TEXT="should_move_stop_loss_continuously()">
        </node>
        <node TEXT="move_stop_loss_to_swing_low()">
        </node>
        <node TEXT="check_trade_exit()">
        </node>
        <node TEXT="set_initial_15min_candle()">
        </node>
        <node TEXT="should_move_target()">
        </node>
        <node TEXT="move_target_to_rr4()">
        </node>
        <node TEXT="remove_target_and_trail()">
        </node>
      </node>
    </node>
    <node TEXT="erl_to_irl_strategy.py">
      <node TEXT="ERLToIRLStrategy">
        <node TEXT="set_callbacks()">
        </node>
        <node TEXT="initialize_with_historical_data()">
        </node>
        <node TEXT="update_price()">
        </node>
        <node TEXT="update_1m_candle()">
        </node>
        <node TEXT="update_5m_candle()">
        </node>
        <node TEXT="update_15m_candle()">
        </node>
        <node TEXT="update_price()">
        </node>
        <node TEXT="set_callbacks()">
        </node>
        <node TEXT="get_strategy_status()">
        </node>
      </node>
    </node>
    <node TEXT="implied_fvg_detector.py">
      <node TEXT="ImpliedFVGDetector">
        <node TEXT="detect_bullish_implied_fvg()">
        </node>
        <node TEXT="detect_bearish_implied_fvg()">
        </node>
        <node TEXT="scan_candles_for_implied_fvgs()">
        </node>
        <node TEXT="find_nearest_implied_fvg()">
        </node>
      </node>
    </node>
    <node TEXT="irl_to_erl_strategy.py">
      <node TEXT="IRLToERLStrategy">
        <node TEXT="set_callbacks()">
        </node>
        <node TEXT="initialize_with_historical_data()">
        </node>
        <node TEXT="update_1m_candle()">
        </node>
        <node TEXT="update_5m_candle()">
        </node>
        <node TEXT="update_15m_candle()">
        </node>
        <node TEXT="reset_sting_detection()">
        </node>
        <node TEXT="update_price()">
        </node>
        <node TEXT="get_strategy_status()">
        </node>
      </node>
    </node>
    <node TEXT="liquidity_tracker.py">
      <node TEXT="LiquidityZone">
      </node>
      <node TEXT="LiquidityTracker">
        <node TEXT="add_historical_data()">
        </node>
        <node TEXT="find_nearest_bearish_target()">
        </node>
        <node TEXT="find_nearest_bullish_target()">
        </node>
        <node TEXT="check_and_mark_mitigation()">
        </node>
        <node TEXT="get_liquidity_summary()">
        </node>
        <node TEXT="get_bullish_fvgs()">
        </node>
        <node TEXT="get_bullish_ifvgs()">
        </node>
        <node TEXT="get_swing_highs()">
        </node>
        <node TEXT="process_candle()">
        </node>
      </node>
    </node>
    <node TEXT="symbol_manager.py">
      <node TEXT="SymbolManager">
        <node TEXT="update_15min_candle()">
        </node>
        <node TEXT="update_1min_candle()">
        </node>
        <node TEXT="update_1min_candle_with_data()">
        </node>
        <node TEXT="check_sweep_conditions()">
        </node>
        <node TEXT="is_any_symbol_in_trade()">
        </node>
        <node TEXT="get_active_symbol()">
        </node>
        <node TEXT="get_strategy_status()">
        </node>
        <node TEXT="set_initial_15min_candle()">
        </node>
        <node TEXT="reset_sweep_detection()">
        </node>
        <node TEXT="get_all_pending_triggers()">
        </node>
        <node TEXT="select_best_trigger()">
        </node>
      </node>
    </node>
  </node>
  <node TEXT="utils">
    <node TEXT="__init__.py">
    </node>
    <node TEXT="account_manager.py">
      <node TEXT="AccountManager">
        <node TEXT="get_current_balance()">
        </node>
        <node TEXT="update_balance()">
        </node>
        <node TEXT="calculate_trade_parameters()">
        </node>
        <node TEXT="deduct_investment()">
        </node>
        <node TEXT="add_investment_return()">
        </node>
        <node TEXT="calculate_pnl()">
        </node>
        <node TEXT="log_trade_summary()">
        </node>
      </node>
    </node>
    <node TEXT="config.py">
      <node TEXT="TradingMode">
      </node>
      <node TEXT="StrategyMode">
      </node>
      <node TEXT="TradingConfig">
        <node TEXT="is_live_mode()">
        </node>
        <node TEXT="is_demo_mode()">
        </node>
        <node TEXT="get_symbols()">
        </node>
        <node TEXT="is_dual_symbol_mode()">
        </node>
        <node TEXT="is_erl_to_irl_strategy()">
        </node>
        <node TEXT="is_irl_to_erl_strategy()">
        </node>
        <node TEXT="is_both_strategies()">
        </node>
        <node TEXT="get_demo_start_datetime()">
        </node>
        <node TEXT="get_num_hist_days()">
        </node>
        <node TEXT="get_fixed_sl_amount()">
        </node>
        <node TEXT="validate_config()">
        </node>
        <node TEXT="print_config()">
        </node>
      </node>
    </node>
    <node TEXT="historical_data.py">
      <node TEXT="HistoricalDataFetcher">
        <node TEXT="get_security_id()">
        </node>
        <node TEXT="fetch_historical_data()">
        </node>
        <node TEXT="fetch_15min_candles()">
        </node>
        <node TEXT="fetch_1min_candles()">
        </node>
        <node TEXT="fetch_5min_candles()">
        </node>
        <node TEXT="fetch_10_days_historical_data()">
        </node>
      </node>
    </node>
    <node TEXT="logger.py">
      <node TEXT="TradingLogger">
        <node TEXT="debug()">
        </node>
        <node TEXT="info()">
        </node>
        <node TEXT="warning()">
        </node>
        <node TEXT="error()">
        </node>
        <node TEXT="critical()">
        </node>
        <node TEXT="log_trade_entry()">
        </node>
        <node TEXT="log_trade_exit()">
        </node>
        <node TEXT="log_candle_data()">
        </node>
        <node TEXT="log_sweep_detection()">
        </node>
        <node TEXT="log_fvg_detection()">
        </node>
        <node TEXT="log_cisd_detection()">
        </node>
        <node TEXT="log_stop_loss_movement()">
        </node>
        <node TEXT="log_target_movement()">
        </node>
        <node TEXT="log_swing_low_detection()">
        </node>
        <node TEXT="log_strategy_status()">
        </node>
        <node TEXT="log_15min_candle_completion()">
        </node>
        <node TEXT="log_5min_candle_completion()">
        </node>
        <node TEXT="log_1min_candle_completion()">
        </node>
        <node TEXT="log_price_update()">
        </node>
        <node TEXT="log_error()">
        </node>
        <node TEXT="log_config()">
        </node>
      </node>
    </node>
    <node TEXT="logger_wrapper.py">
      <node TEXT="LoggerWrapper">
        <node TEXT="debug()">
        </node>
        <node TEXT="info()">
        </node>
        <node TEXT="warning()">
        </node>
        <node TEXT="error()">
        </node>
        <node TEXT="critical()">
        </node>
        <node TEXT="log_trade_entry()">
        </node>
        <node TEXT="log_trade_exit()">
        </node>
        <node TEXT="log_fvg_detection()">
        </node>
        <node TEXT="log_sweep_detection()">
        </node>
        <node TEXT="log_price_update()">
        </node>
        <node TEXT="log_error()">
        </node>
        <node TEXT="log_candle_data()">
        </node>
        <node TEXT="log_15min_candle_completion()">
        </node>
        <node TEXT="log_5min_candle_completion()">
        </node>
        <node TEXT="log_1min_candle_completion()">
        </node>
        <node TEXT="log_cisd_detection()">
        </node>
        <node TEXT="log_stop_loss_movement()">
        </node>
        <node TEXT="log_target_movement()">
        </node>
        <node TEXT="log_swing_low_detection()">
        </node>
        <node TEXT="log_strategy_status()">
        </node>
        <node TEXT="log_config()">
        </node>
        <node TEXT="log_trade_entry()">
        </node>
      </node>
    </node>
    <node TEXT="market_data.py">
      <node TEXT="MarketDataWebSocket">
        <node TEXT="on_message()">
        </node>
        <node TEXT="on_error()">
        </node>
        <node TEXT="on_close()">
        </node>
        <node TEXT="on_open()">
        </node>
        <node TEXT="connect()">
        </node>
        <node TEXT="close()">
        </node>
        <node TEXT="is_connected()">
        </node>
      </node>
      <node TEXT="process_ticker_data()">
      </node>
      <node TEXT="process_quote_data()">
      </node>
      <node TEXT="process_market_depth()">
      </node>
    </node>
    <node TEXT="market_utils.py">
      <node TEXT="is_market_hours()">
      </node>
      <node TEXT="is_trading_ending()">
      </node>
      <node TEXT="round_to_tick()">
      </node>
      <node TEXT="get_market_boundary_time()">
      </node>
    </node>
    <node TEXT="rate_limiter.py">
      <node TEXT="RateLimiter">
        <node TEXT="wait_if_needed()">
        </node>
      </node>
      <node TEXT="rate_limit()">
      </node>
      <node TEXT="make_rate_limited_request()">
      </node>
      <node TEXT="add_delay_between_requests()">
      </node>
    </node>
    <node TEXT="symbol_logger.py">
      <node TEXT="SymbolLogger">
        <node TEXT="get_symbol_logger()">
        </node>
        <node TEXT="debug()">
        </node>
        <node TEXT="info()">
        </node>
        <node TEXT="warning()">
        </node>
        <node TEXT="error()">
        </node>
        <node TEXT="critical()">
        </node>
        <node TEXT="log_trade_entry()">
        </node>
        <node TEXT="log_trade_exit()">
        </node>
        <node TEXT="log_fvg_detection()">
        </node>
        <node TEXT="log_sweep_detection()">
        </node>
        <node TEXT="log_price_update()">
        </node>
        <node TEXT="log_error()">
        </node>
        <node TEXT="log_candle_data()">
        </node>
        <node TEXT="log_15min_candle_completion()">
        </node>
        <node TEXT="log_5min_candle_completion()">
        </node>
        <node TEXT="log_1min_candle_completion()">
        </node>
        <node TEXT="log_cisd_detection()">
        </node>
        <node TEXT="log_stop_loss_movement()">
        </node>
        <node TEXT="log_target_movement()">
        </node>
        <node TEXT="log_swing_low_detection()">
        </node>
        <node TEXT="log_strategy_status()">
        </node>
        <node TEXT="log_trade_entry()">
        </node>
        <node TEXT="log_config()">
        </node>
        <node TEXT="close_all_handlers()">
        </node>
      </node>
    </node>
    <node TEXT="timezone_utils.py">
      <node TEXT="normalize_timezone_awareness()">
      </node>
      <node TEXT="ensure_timezone_naive()">
      </node>
      <node TEXT="ensure_timezone_aware()">
      </node>
      <node TEXT="safe_datetime_compare()">
      </node>
      <node TEXT="safe_datetime_arithmetic()">
      </node>
    </node>
  </node>
  <node TEXT=".env">
  </node>
  <node TEXT=".gitignore">
  </node>
  <node TEXT="code2mindmap.py">
    <node TEXT="Node">
      <node TEXT="add()">
      </node>
    </node>
    <node TEXT="parse_python_symbols()">
    </node>
    <node TEXT="parse_js_ts_symbols()">
    </node>
    <node TEXT="parse_java_symbols()">
    </node>
    <node TEXT="dedupe_syms()">
    </node>
    <node TEXT="parse_symbols_for_file()">
    </node>
    <node TEXT="build_tree()">
    </node>
    <node TEXT="to_mermaid_mindmap()">
    </node>
    <node TEXT="to_freemind()">
    </node>
    <node TEXT="main()">
    </node>
  </node>
  <node TEXT="find_symbol.py">
    <node TEXT="find_symbols()">
    </node>
  </node>
  <node TEXT="fix_demo_date.py">
    <node TEXT="fix_demo_date()">
    </node>
  </node>
  <node TEXT="run_bot_debug.py">
  </node>
  <node TEXT="trading_bot_dual_mode.py">
    <node TEXT="DualModeTradingBot">
      <node TEXT="load_instruments()">
      </node>
      <node TEXT="initialize_historical_data()">
      </node>
      <node TEXT="start_demo_server()">
      </node>
      <node TEXT="setup_live_websocket()">
      </node>
      <node TEXT="start_trading()">
      </node>
      <node TEXT="stop_trading()">
      </node>
      <node TEXT="run()">
      </node>
      <node TEXT="initialize_previous_15min_candle()">
      </node>
    </node>
    <node TEXT="signal_handler()">
    </node>
  </node>
  <node TEXT="trading_bot_modular.py">
    <node TEXT="DhanTradingBot">
      <node TEXT="load_instruments()">
      </node>
      <node TEXT="get_security_id()">
      </node>
      <node TEXT="update_candle()">
      </node>
      <node TEXT="handle_market_data()">
      </node>
      <node TEXT="on_websocket_message()">
      </node>
      <node TEXT="on_websocket_error()">
      </node>
      <node TEXT="on_websocket_close()">
      </node>
      <node TEXT="connect_websocket()">
      </node>
      <node TEXT="check_market_end()">
      </node>
      <node TEXT="run_strategy()">
      </node>
      <node TEXT="display_strategy_status()">
      </node>
      <node TEXT="run()">
      </node>
    </node>
    <node TEXT="main()">
    </node>
  </node>
</node>
</map>