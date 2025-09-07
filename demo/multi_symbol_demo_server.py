"""
Multi-Symbol Demo Server for streaming historical market data for multiple symbols
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
from utils.timezone_utils import ensure_timezone_naive

class MultiSymbolDemoServer:
    """Multi-symbol demo server for streaming historical market data"""
    
    def __init__(self, symbols_data: Dict[str, pd.DataFrame], start_date: datetime, 
                 interval_minutes: int = 1, port: int = 8080, stream_interval_seconds: float = 1.0):
        """
        Initialize multi-symbol demo server
        
        Args:
            symbols_data: Dictionary mapping symbol names to their historical data DataFrames
            start_date: Start date for simulation
            interval_minutes: Candle interval (1 minute)
            port: Server port
            stream_interval_seconds: How fast to stream each candle
        """
        self.symbols_data = symbols_data
        self.symbols = list(symbols_data.keys())
        self.start_date = start_date
        self.interval_minutes = interval_minutes
        self.port = port
        self.stream_interval_seconds = stream_interval_seconds
        
        # Current simulation time
        self.current_sim_time = start_date
        self.simulation_running = False
        self.simulation_thread = None
        
        # Flask app
        self.app = Flask(__name__)
        CORS(self.app)
        self.setup_routes()
        
        # Data tracking
        self.current_candle_index = 0
        self.streamed_candles = {symbol: [] for symbol in self.symbols}
        
        # Find the minimum length across all symbols to ensure we don't go out of bounds
        self.min_data_length = min(len(data) for data in self.symbols_data.values())
        
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def status():
            return jsonify({
                "status": "running" if self.simulation_running else "stopped",
                "symbols": self.symbols,
                "current_time": self.current_sim_time.isoformat(),
                "current_candle_index": self.current_candle_index,
                "total_candles": self.min_data_length,
                "streamed_candles": {symbol: len(candles) for symbol, candles in self.streamed_candles.items()}
            })
        
        @self.app.route('/start')
        def start_simulation():
            if not self.simulation_running:
                self.simulation_running = True
                self.simulation_thread = threading.Thread(target=self._simulation_loop)
                self.simulation_thread.daemon = True
                self.simulation_thread.start()
                return jsonify({"status": "started", "message": "Simulation started"})
            else:
                return jsonify({"status": "already_running", "message": "Simulation already running"})
        
        @self.app.route('/stop')
        def stop_simulation():
            self.simulation_running = False
            if self.simulation_thread:
                self.simulation_thread.join(timeout=2)
            return jsonify({"status": "stopped", "message": "Simulation stopped"})
        
        @self.app.route('/reset')
        def reset_simulation():
            self.simulation_running = False
            self.current_candle_index = 0
            self.current_sim_time = self.start_date
            self.streamed_candles = {symbol: [] for symbol in self.symbols}
            return jsonify({"status": "reset", "message": "Simulation reset"})
        
        @self.app.route('/current_candle')
        def get_current_candle():
            if self.current_candle_index >= self.min_data_length:
                return jsonify({"error": "No more data", "status": "completed"})
            
            # Get current candle for all symbols
            current_candles = {}
            for symbol in self.symbols:
                if self.current_candle_index < len(self.symbols_data[symbol]):
                    candle = self.symbols_data[symbol].iloc[self.current_candle_index]
                    # Ensure candle timestamp is timezone-naive
                    candle_timestamp = ensure_timezone_naive(candle['timestamp'])
                    
                    current_candles[symbol] = {
                        "timestamp": candle_timestamp.isoformat(),
                        "open": float(candle['open']),
                        "high": float(candle['high']),
                        "low": float(candle['low']),
                        "close": float(candle['close']),
                        "volume": int(candle['volume']) if 'volume' in candle else 0
                    }
            
            # Ensure timestamp is timezone-naive for consistency
            timestamp = ensure_timezone_naive(self.current_sim_time)
            
            return jsonify({
                "timestamp": timestamp.isoformat(),
                "candles": current_candles
            })
        
        @self.app.route('/candles/<symbol>')
        def get_candles_for_symbol(symbol):
            if symbol not in self.symbols:
                return jsonify({"error": f"Symbol {symbol} not found"}), 404
            
            return jsonify({
                "symbol": symbol,
                "candles": self.streamed_candles[symbol]
            })
    
    def set_simulation_time(self, new_time: datetime):
        """Set the simulation time"""
        self.current_sim_time = new_time
        
        # Find the closest candle index for this time
        # This is a simplified approach - in reality, you'd want more sophisticated time matching
        time_diff = (new_time - self.start_date).total_seconds() / 60  # minutes
        self.current_candle_index = int(time_diff)
        
        # Ensure we don't go out of bounds
        self.current_candle_index = max(0, min(self.current_candle_index, self.min_data_length - 1))
        
        print(f"Demo simulation time set to {new_time}")
    
    def _simulation_loop(self):
        """Main simulation loop"""
        while self.simulation_running and self.current_candle_index < self.min_data_length:
            try:
                # Get current candles for all symbols
                current_candles = {}
                for symbol in self.symbols:
                    if self.current_candle_index < len(self.symbols_data[symbol]):
                        candle = self.symbols_data[symbol].iloc[self.current_candle_index]
                        
                        # Update simulation time (use the first symbol's timestamp as reference)
                        if symbol == self.symbols[0]:
                            self.current_sim_time = candle['timestamp']
                        
                        # Add to streamed candles
                        # Ensure candle timestamp is timezone-naive
                        candle_timestamp = candle['timestamp']
                        if candle_timestamp.tzinfo is not None:
                            candle_timestamp = candle_timestamp.replace(tzinfo=None)
                        
                        candle_data = {
                            "timestamp": candle_timestamp.isoformat(),
                            "open": float(candle['open']),
                            "high": float(candle['high']),
                            "low": float(candle['low']),
                            "close": float(candle['close']),
                            "volume": int(candle['volume']) if 'volume' in candle else 0
                        }
                        self.streamed_candles[symbol].append(candle_data)
                        current_candles[symbol] = candle_data
                
                # Format timestamp for human-readable output
                try:
                    if hasattr(self.current_sim_time, 'strftime'):
                        readable_time = self.current_sim_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                    else:
                        parsed_time = pd.to_datetime(self.current_sim_time)
                        readable_time = parsed_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                except Exception as e:
                    readable_time = f"Invalid timestamp: {self.current_sim_time}"
                
                # Print streaming info for all symbols
                symbol_info = []
                for symbol, candle_data in current_candles.items():
                    symbol_info.append(f"{symbol}: {candle_data['close']:.2f}")
                
                print(f"Streaming candles: {readable_time} - {' | '.join(symbol_info)}")
                
                # Move to next candle
                self.current_candle_index += 1
                
                # Wait for configurable interval
                time.sleep(self.stream_interval_seconds)
                
            except Exception as e:
                print(f"Error in simulation loop: {e}")
                break
        
        if self.current_candle_index >= self.min_data_length:
            print("Demo simulation completed - all data streamed")
            self.simulation_running = False
    
    def run(self):
        """Run the Flask server"""
        print(f"Starting multi-symbol demo server on port {self.port}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Historical data: {self.min_data_length} candles per symbol")
        print(f"Start date: {self.start_date}")
        print(f"Interval: {self.interval_minutes} minutes")
        print(f"Stream speed: {self.stream_interval_seconds} seconds per candle")
        
        # Debug timestamp information
        if self.min_data_length > 0:
            print(f"\nTimestamp debugging:")
            for symbol in self.symbols:
                if len(self.symbols_data[symbol]) > 0:
                    first_candle = self.symbols_data[symbol].iloc[0]
                    last_candle = self.symbols_data[symbol].iloc[-1]
                    print(f"{symbol}: {first_candle['timestamp']} to {last_candle['timestamp']}")
        
        self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)
    
    def get_current_candles(self) -> Dict[str, Optional[dict]]:
        """Get current candles for all symbols"""
        if self.current_candle_index >= self.min_data_length:
            return {symbol: None for symbol in self.symbols}
        
        current_candles = {}
        for symbol in self.symbols:
            if self.current_candle_index < len(self.symbols_data[symbol]):
                candle = self.symbols_data[symbol].iloc[self.current_candle_index]
                current_candles[symbol] = {
                    "timestamp": candle['timestamp'],
                    "open": float(candle['open']),
                    "high": float(candle['high']),
                    "low": float(candle['low']),
                    "close": float(candle['close']),
                    "volume": int(candle['volume']) if 'volume' in candle else 0
                }
            else:
                current_candles[symbol] = None
        
        return current_candles
    
    def get_current_timestamp(self) -> Optional[datetime]:
        """Get current timestamp"""
        return self.current_sim_time
