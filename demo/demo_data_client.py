"""
Demo data client for connecting to demo server and providing market data
"""

import time
import requests
import json
from datetime import datetime
from typing import Optional, Callable
import threading

class DemoDataClient:
    """Client for connecting to demo server and streaming data"""
    
    def __init__(self, server_url: str = "http://localhost:8080"):
        self.server_url = server_url
        self.is_connected = False
        self.current_price = None
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
                print(f"Connected to demo server: {data}")
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
        """Set callback function for price updates"""
        self.callback = callback
    
    def start_data_stream(self):
        """Start streaming data from demo server"""
        if not self.is_connected:
            print("Not connected to demo server")
            return
        
        self.running = True
        self.data_thread = threading.Thread(target=self._data_stream_loop)
        self.data_thread.daemon = True
        self.data_thread.start()
        print("Demo data stream started")
    
    def stop_data_stream(self):
        """Stop streaming data"""
        self.running = False
        if self.data_thread:
            self.data_thread.join(timeout=1)
        print("Demo data stream stopped")
    
    def _data_stream_loop(self):
        """Main data streaming loop"""
        while self.running:
            try:
                # Get current candle from server
                response = requests.get(f"{self.server_url}/current_candle")
                if response.status_code == 200:
                    candle_data = response.json()
                    
                    if "error" not in candle_data:
                        # Update current price and timestamp
                        self.current_price = candle_data["close"]
                        self.current_timestamp = datetime.fromisoformat(candle_data["timestamp"])
                        
                        # Call callback if set
                        if self.callback:
                            # Pass security_id as None for demo mode (not needed for demo)
                            # Pass the complete candle data instead of just the close price
                            self.callback(candle_data, self.current_timestamp)
                        
                        print(f"Demo Data: {self.current_timestamp.strftime('%H:%M:%S')} - Price: {self.current_price}")
                    else:
                        # No more data available, stop the stream
                        print("No more demo data available, stopping stream")
                        self.running = False
                        break
                else:
                    print(f"Failed to get candle data: {response.status_code}")
                    time.sleep(5)  # Wait before retrying
                
                # Wait for next update (poll faster than server advances to catch all candles)
                time.sleep(1)  # Check every 1 second (server advances every 2 seconds)
                
            except Exception as e:
                print(f"Error in demo data stream: {e}")
                time.sleep(5)  # Wait before retrying
    
    def get_current_price(self) -> Optional[float]:
        """Get current price"""
        return self.current_price
    
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
                return {"error": f"Server returned {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_streamed_candles(self) -> list:
        """Get all streamed candles"""
        try:
            response = requests.get(f"{self.server_url}/streamed_candles")
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception as e:
            print(f"Error getting streamed candles: {e}")
            return []
    
    def is_running(self) -> bool:
        """Check if the demo client is running"""
        return self.running