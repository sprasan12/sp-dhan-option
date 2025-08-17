"""
Demo server for streaming historical market data
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd

class DemoServer:
    """Demo server for streaming historical market data"""
    
    def __init__(self, historical_data: pd.DataFrame, start_date: datetime, 
                 interval_minutes: int = 1, port: int = 8080, stream_interval_seconds: float = 1.0):
        self.historical_data = historical_data
        self.start_date = start_date
        self.interval_minutes = interval_minutes
        self.port = port
        self.stream_interval_seconds = stream_interval_seconds  # How fast to stream each candle
        
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
        self.streamed_candles = []
        
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def home():
            return jsonify({
                "status": "Demo Server Running",
                "start_date": self.start_date.isoformat(),
                "current_time": self.current_sim_time.isoformat(),
                "interval_minutes": self.interval_minutes,
                "stream_interval_seconds": self.stream_interval_seconds,
                "total_candles": len(self.historical_data),
                "streamed_candles": len(self.streamed_candles)
            })
        
        @self.app.route('/start')
        def start_simulation():
            if not self.simulation_running:
                self.start_simulation()
                return jsonify({"status": "Simulation started"})
            else:
                return jsonify({"status": "Simulation already running"})
        
        @self.app.route('/stop')
        def stop_simulation():
            if self.simulation_running:
                self.stop_simulation()
                return jsonify({"status": "Simulation stopped"})
            else:
                return jsonify({"status": "Simulation not running"})
        
        @self.app.route('/reset')
        def reset_simulation():
            self.reset_simulation()
            return jsonify({"status": "Simulation reset"})
        
        @self.app.route('/current_candle')
        def get_current_candle():
            if self.current_candle_index < len(self.historical_data):
                candle = self.historical_data.iloc[self.current_candle_index]
                return jsonify({
                    "timestamp": candle['timestamp'].isoformat(),
                    "open": float(candle['open']),
                    "high": float(candle['high']),
                    "low": float(candle['low']),
                    "close": float(candle['close']),
                    "volume": int(candle['volume']) if 'volume' in candle else 0
                })
            else:
                return jsonify({"error": "No more data available"})
        
        @self.app.route('/streamed_candles')
        def get_streamed_candles():
            return jsonify(self.streamed_candles)
        
        @self.app.route('/set_time', methods=['POST'])
        def set_simulation_time():
            data = request.get_json()
            if 'timestamp' in data:
                try:
                    new_time = datetime.fromisoformat(data['timestamp'])
                    self.set_simulation_time(new_time)
                    return jsonify({"status": "Time set successfully"})
                except ValueError:
                    return jsonify({"error": "Invalid timestamp format"})
            else:
                return jsonify({"error": "timestamp parameter required"})
    
    def start_simulation(self):
        """Start the simulation thread"""
        if not self.simulation_running:
            self.simulation_running = True
            self.simulation_thread = threading.Thread(target=self._simulation_loop)
            self.simulation_thread.daemon = True
            self.simulation_thread.start()
            print(f"Demo simulation started at {self.current_sim_time}")
    
    def stop_simulation(self):
        """Stop the simulation"""
        self.simulation_running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=1)
        print("Demo simulation stopped")
    
    def reset_simulation(self):
        """Reset simulation to start"""
        self.stop_simulation()
        self.current_sim_time = self.start_date
        self.current_candle_index = 0
        self.streamed_candles = []
        print(f"Demo simulation reset to {self.start_date}")
    
    def set_simulation_time(self, new_time: datetime):
        """Set simulation time to a specific point"""
        self.current_sim_time = new_time
        
        # Find the closest candle index
        for i, row in self.historical_data.iterrows():
            if row['timestamp'] >= new_time:
                self.current_candle_index = i
                break
        
        print(f"Demo simulation time set to {new_time}")
    
    def _simulation_loop(self):
        """Main simulation loop"""
        while self.simulation_running and self.current_candle_index < len(self.historical_data):
            try:
                # Get current candle
                candle = self.historical_data.iloc[self.current_candle_index]
                
                # Update simulation time
                self.current_sim_time = candle['timestamp']
                
                # Add to streamed candles
                candle_data = {
                    "timestamp": candle['timestamp'].isoformat(),
                    "open": float(candle['open']),
                    "high": float(candle['high']),
                    "low": float(candle['low']),
                    "close": float(candle['close']),
                    "volume": int(candle['volume']) if 'volume' in candle else 0
                }
                self.streamed_candles.append(candle_data)
                
                # Format timestamp for human-readable output
                try:
                    if hasattr(candle['timestamp'], 'strftime'):
                        # It's already a datetime object
                        readable_time = candle['timestamp'].strftime('%Y-%m-%d %H:%M:%S %Z')
                    else:
                        # Try to parse it
                        parsed_time = pd.to_datetime(candle['timestamp'])
                        readable_time = parsed_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                except Exception as e:
                    readable_time = f"Invalid timestamp: {candle['timestamp']}"
                
                print(f"Streaming candle: {readable_time} - Close: {candle_data['close']} Low: {candle_data['low']}")
                
                # Move to next candle
                self.current_candle_index += 1
                
                # Wait for configurable interval (much faster than real time)
                time.sleep(self.stream_interval_seconds)
                
            except Exception as e:
                print(f"Error in simulation loop: {e}")
                break
        
        if self.current_candle_index >= len(self.historical_data):
            print("Demo simulation completed - all data streamed")
            self.simulation_running = False
    
    def run(self):
        """Run the Flask server"""
        print(f"Starting demo server on port {self.port}")
        print(f"Historical data: {len(self.historical_data)} candles")
        print(f"Start date: {self.start_date}")
        print(f"Interval: {self.interval_minutes} minutes")
        print(f"Stream speed: {self.stream_interval_seconds} seconds per candle")
        
        # Debug timestamp information
        if len(self.historical_data) > 0:
            print(f"\nTimestamp debugging:")
            print(f"First candle timestamp: {self.historical_data.iloc[0]['timestamp']}")
            print(f"Last candle timestamp: {self.historical_data.iloc[-1]['timestamp']}")
            print(f"Timestamp column type: {self.historical_data['timestamp'].dtype}")
        
        self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)
    
    def get_current_price(self) -> Optional[float]:
        """Get current price for trading bot"""
        if self.current_candle_index < len(self.historical_data):
            candle = self.historical_data.iloc[self.current_candle_index]
            return float(candle['close'])
        return None
    
    def get_current_timestamp(self) -> Optional[datetime]:
        """Get current timestamp for trading bot"""
        if self.current_candle_index < len(self.historical_data):
            candle = self.historical_data.iloc[self.current_candle_index]
            return candle['timestamp']
        return None
