"""
Multi-Symbol Demo Data Client for connecting to multi-symbol demo server
"""

import time
import requests
import json
from datetime import datetime
from typing import Optional, Callable, Dict
import threading

class MultiSymbolDemoClient:
    """Client for connecting to multi-symbol demo server and streaming data"""
    
    def __init__(self, server_url: str = "http://localhost:8080"):
        self.server_url = server_url
        self.is_connected = False
        self.current_candles = {}
        self.current_timestamp = None
        self.callback = None
        self.data_thread = None
        self.running = False
        
    def connect(self) -> bool:
        """Connect to demo server"""
        try:
            response = requests.get(f"{self.server_url}/")
            if response.status_code == 200:
                data = response.json()
                print(f"Connected to multi-symbol demo server: {data}")
                self.is_connected = True
                return True
            else:
                print(f"Failed to connect to demo server: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error connecting to demo server: {e}")
            return False
    
    def start_simulation(self) -> bool:
        """Start the demo simulation"""
        try:
            response = requests.get(f"{self.server_url}/start")
            if response.status_code == 200:
                data = response.json()
                print(f"Demo simulation started: {data}")
                return True
            else:
                print(f"Failed to start simulation: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error starting simulation: {e}")
            return False
    
    def stop_simulation(self) -> bool:
        """Stop the demo simulation"""
        try:
            response = requests.get(f"{self.server_url}/stop")
            if response.status_code == 200:
                data = response.json()
                print(f"Demo simulation stopped: {data}")
                return True
            else:
                print(f"Failed to stop simulation: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error stopping simulation: {e}")
            return False
    
    def reset_simulation(self) -> bool:
        """Reset the demo simulation"""
        try:
            response = requests.get(f"{self.server_url}/reset")
            if response.status_code == 200:
                data = response.json()
                print(f"Demo simulation reset: {data}")
                return True
            else:
                print(f"Failed to reset simulation: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error resetting simulation: {e}")
            return False
    
    def set_callback(self, callback: Callable):
        """Set callback function for data updates"""
        self.callback = callback
    
    def start_data_stream(self):
        """Start the data streaming thread"""
        if not self.running:
            self.running = True
            self.data_thread = threading.Thread(target=self._data_stream_loop)
            self.data_thread.daemon = True
            self.data_thread.start()
            print("Multi-symbol demo data stream started")
    
    def stop_data_stream(self):
        """Stop the data streaming thread"""
        self.running = False
        if self.data_thread:
            self.data_thread.join(timeout=1)
        print("Multi-symbol demo data stream stopped")
    
    def _data_stream_loop(self):
        """Main data streaming loop"""
        while self.running:
            try:
                # Get current candles from server
                response = requests.get(f"{self.server_url}/current_candle")
                if response.status_code == 200:
                    data = response.json()
                    
                    if "error" not in data:
                        # Update current candles and timestamp
                        self.current_candles = data.get("candles", {})
                        self.current_timestamp = datetime.fromisoformat(data["timestamp"])
                        
                        # Call callback if set
                        if self.callback:
                            # Pass all candles data to callback
                            self.callback(self.current_candles, self.current_timestamp, None)
                        
                        # Print demo data info
                        symbol_info = []
                        for symbol, candle_data in self.current_candles.items():
                            symbol_info.append(f"{symbol}: {candle_data['close']:.2f}")
                        
                        print(f"Demo Data: {self.current_timestamp.strftime('%H:%M:%S')} - {' | '.join(symbol_info)}")
                    else:
                        print(f"Demo server error: {data.get('error', 'Unknown error')}")
                        if "completed" in data.get("status", ""):
                            print("Demo simulation completed")
                            break
                
                # Wait for next update
                time.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"Error in demo data stream: {e}")
                time.sleep(5)  # Wait before retrying
    
    def get_current_candles(self) -> Dict[str, dict]:
        """Get current candles for all symbols"""
        return self.current_candles
    
    def get_current_candle(self, symbol: str) -> Optional[dict]:
        """Get current candle for a specific symbol"""
        return self.current_candles.get(symbol)
    
    def get_current_timestamp(self) -> Optional[datetime]:
        """Get current timestamp"""
        return self.current_timestamp
    
    def get_server_status(self) -> dict:
        """Get demo server status"""
        try:
            response = requests.get(f"{self.server_url}/")
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Failed to get status: {response.status_code}"}
        except Exception as e:
            return {"error": f"Error getting status: {e}"}
