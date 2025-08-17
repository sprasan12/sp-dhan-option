"""
Historical data fetcher for demo trading mode
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class HistoricalDataFetcher:
    """Fetches historical data from Dhan API"""
    
    def __init__(self, access_token: str, client_id: str):
        self.access_token = access_token
        self.client_id = client_id
        self.base_url = "https://api.dhan.co/v2/charts/intraday"
    
    def get_security_id(self, symbol: str, instruments_df: pd.DataFrame) -> Optional[int]:
        """Get Security ID for a given symbol"""
        try:
            if instruments_df is None:
                return None
            
            # Filter for options in NSE
            options_df = instruments_df[
                (instruments_df['EXCH_ID'] == 'NSE') & 
                (instruments_df['SEGMENT'] == 'D') &
                (instruments_df['INSTRUMENT'] == 'OPTIDX')
            ]
            
            print(f"Looking for symbol: '{symbol}'")
            print(f"Available NSE options: {len(options_df)}")
            
            # Find the exact matching symbol using DISPLAY_NAME
            matching_instrument = options_df[options_df['DISPLAY_NAME'] == symbol]
            
            if not matching_instrument.empty:
                security_id = int(matching_instrument.iloc[0]['SECURITY_ID'])
                print(f"Found security ID: {security_id} for symbol: {symbol}")
                return security_id
            else:
                print(f"No matching instrument found for symbol '{symbol}'")
                
                # Show some sample symbols for debugging
                sample_symbols = options_df['DISPLAY_NAME'].head(10).tolist()
                print(f"Sample available symbols: {sample_symbols}")
                
                # Try partial matching
                partial_matches = options_df[options_df['DISPLAY_NAME'].str.contains(symbol.split()[0], case=False)]
                if not partial_matches.empty:
                    print(f"Partial matches found: {partial_matches['DISPLAY_NAME'].head(5).tolist()}")
                
                return None
                
        except Exception as e:
            print(f"Error getting security ID: {e}")
            return None
    
    def fetch_historical_data(self, symbol: str, instruments_df: pd.DataFrame, 
                            start_date: datetime, end_date: datetime, 
                            interval: str = "1min") -> Optional[pd.DataFrame]:
        """
        Fetch historical data from Dhan API
        
        Args:
            symbol: Trading symbol
            instruments_df: Instruments dataframe
            start_date: Start date for historical data
            end_date: End date for historical data
            interval: Data interval (1min, 5min, 15min, 30min, 1day)
        
        Returns:
            DataFrame with historical data or None if failed
        """
        try:
            # Get security ID
            security_id = self.get_security_id(symbol, instruments_df)
            if not security_id:
                print(f"Could not find security ID for symbol {symbol}")
                return None
            
            # Convert interval format to match API requirements
            interval_map = {
                "1min": "1",
                "5min": "5", 
                "15min": "15",
                "30min": "30",
                "1day": "1D"
            }
            api_interval = interval_map.get(interval, interval)
            
            # Prepare request body (POST with JSON)
            request_body = {
                "securityId": str(security_id),
                "exchangeSegment": "NSE_FNO",
                "instrument": "OPTIDX",
                "fromDate": start_date.strftime("%Y-%m-%d 10:30:00"),  # Market open time
                "toDate": end_date.strftime("%Y-%m-%d 16:00:00"),      # Market close time
                "interval": api_interval,
                "oi": False
            }
            
            headers = {
                'access-token': self.access_token,
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            print(f"Fetching historical data for {symbol} from {start_date.date()} to {end_date.date()}")
            print(f"Request body: {request_body}")
            
            # Make API request (POST with JSON body)
            response = requests.post(
                f"{self.base_url}",
                headers=headers,
                json=request_body
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"API Response type: {type(data)}")
                
                # Handle different response formats
                if isinstance(data, list) and len(data) > 0:
                    # List of candles
                    df = pd.DataFrame(data)
                    print(f"List of candles with {len(df)} records")
                elif isinstance(data, dict) and 'data' in data and data['data']:
                    # Nested data structure
                    df = pd.DataFrame(data['data'])
                    print(f"Nested data structure with {len(df)} records")
                elif isinstance(data, dict) and all(key in data for key in ['open', 'high', 'low', 'close', 'volume', 'timestamp']):
                    # Check if values are arrays (separate arrays for each field)
                    if isinstance(data['open'], list) and isinstance(data['close'], list):
                        # Separate arrays format - convert to DataFrame
                        df = pd.DataFrame({
                            'open': data['open'],
                            'high': data['high'],
                            'low': data['low'],
                            'close': data['close'],
                            'volume': data['volume'],
                            'timestamp': data['timestamp']
                        })
                        print(f"Separate arrays format with {len(df)} records")
                    else:
                        # Single candle object
                        df = pd.DataFrame([data])
                        print(f"Single candle object converted to DataFrame")
                else:
                    print("No historical data found")
                    print(f"Response structure: {type(data)}")
                    if isinstance(data, dict):
                        print(f"Available keys: {list(data.keys())}")
                    return None
                
                # Convert timestamp to datetime with better error handling
                try:
                    # First, let's see what we're working with
                    sample_timestamps = df['timestamp'].head(3).tolist()
                    print(f"Sample timestamp values before conversion: {sample_timestamps}")
                    
                    # Try different parsing strategies
                    if df['timestamp'].dtype == 'object':
                        # Check if timestamps are Unix timestamps (numbers)
                        first_timestamp = str(df['timestamp'].iloc[0])
                        if first_timestamp.replace('.', '').replace('-', '').isdigit():
                            # Likely Unix timestamp - convert from seconds or milliseconds
                            try:
                                # Try as seconds first
                                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='s', utc=True)
                                print("Converted timestamps as Unix seconds (UTC)")
                            except:
                                try:
                                    # Try as milliseconds
                                    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms', utc=True)
                                    print("Converted timestamps as Unix milliseconds (UTC)")
                                except:
                                    # Try as nanoseconds
                                    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ns', utc=True)
                                    print("Converted timestamps as Unix nanoseconds (UTC)")
                        else:
                            # Try standard datetime parsing
                            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
                            print("Converted timestamps using standard datetime parsing (UTC)")
                    else:
                        # Already numeric, try Unix timestamp conversion
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce', utc=True)
                        print("Converted numeric timestamps as Unix seconds (UTC)")
                    
                    # Convert UTC to IST (UTC+5:30)
                    df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Kolkata')
                    print("Converted UTC timestamps to IST (Asia/Kolkata)")
                    
                    # Check if we have any invalid timestamps
                    invalid_timestamps = df['timestamp'].isna().sum()
                    if invalid_timestamps > 0:
                        print(f"Warning: {invalid_timestamps} invalid timestamps found")
                        # Remove rows with invalid timestamps
                        df = df.dropna(subset=['timestamp'])
                        print(f"Removed {invalid_timestamps} rows with invalid timestamps")
                    
                    # Check for timestamps that are too old (before 2000)
                    # Create timezone-aware comparison timestamp
                    comparison_date = pd.Timestamp('2000-01-01').tz_localize('Asia/Kolkata')
                    old_timestamps = (df['timestamp'] < comparison_date).sum()
                    if old_timestamps > 0:
                        print(f"Warning: {old_timestamps} timestamps are before 2000, which might indicate parsing issues")
                        print(f"Sample old timestamps: {df[df['timestamp'] < comparison_date]['timestamp'].head().tolist()}")
                        
                        # If we have old timestamps, try alternative parsing
                        if old_timestamps > 0 and old_timestamps == len(df):
                            print("All timestamps are old, trying alternative parsing methods...")
                            # Get the original raw timestamps
                            if isinstance(data, dict) and 'timestamp' in data:
                                raw_timestamps = data['timestamp']
                            elif isinstance(data, list) and len(data) > 0:
                                raw_timestamps = [item.get('timestamp') for item in data]
                            else:
                                raw_timestamps = df['timestamp'].tolist()
                            
                            # Try different units
                            for unit in ['ms', 'us', 'ns']:
                                try:
                                    test_timestamp = pd.to_datetime(float(raw_timestamps[0]), unit=unit, utc=True)
                                    if test_timestamp > pd.Timestamp('2000-01-01').tz_localize('UTC'):
                                        print(f"Found working unit: {unit}")
                                        df['timestamp'] = pd.to_datetime(raw_timestamps, unit=unit, utc=True)
                                        # Convert UTC to IST
                                        df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Kolkata')
                                        print("Converted UTC timestamps to IST (Asia/Kolkata)")
                                        break
                                except:
                                    continue
                        
                except Exception as e:
                    print(f"Error converting timestamps: {e}")
                    print(f"Sample timestamp values: {df['timestamp'].head() if 'timestamp' in df.columns else 'No timestamp column'}")
                    return None
                
                # Sort by timestamp
                df = df.sort_values('timestamp').reset_index(drop=True)
                
                print(f"Successfully fetched {len(df)} historical records")
                print(f"Data columns: {list(df.columns)}")
                print(f"First few records:")
                print(df.head())
                
                # Debug timestamp information
                if 'timestamp' in df.columns:
                    print(f"\nTimestamp debugging:")
                    print(f"Timestamp column type: {df['timestamp'].dtype}")
                    print(f"First 5 raw timestamp values: {df['timestamp'].head().tolist()}")
                    print(f"Timestamp range: {df['timestamp'].min()} to {df['timestamp'].max()}")
                    
                    # Show raw timestamp values before conversion
                    print(f"Raw timestamp values (before pd.to_datetime):")
                    if isinstance(data, dict) and 'timestamp' in data:
                        print(f"Raw timestamp array: {data['timestamp'][:5] if isinstance(data['timestamp'], list) else data['timestamp']}")
                    elif isinstance(data, list) and len(data) > 0:
                        raw_timestamps = [item.get('timestamp', 'N/A') for item in data[:5]]
                        print(f"Raw timestamp values: {raw_timestamps}")
                return df
            else:
                print(f"API request failed with status {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error fetching historical data: {e}")
            return None
    
    def fetch_15min_candles(self, symbol: str, instruments_df: pd.DataFrame, 
                           days_back: int = 30) -> Optional[pd.DataFrame]:
        """
        Fetch last N days of 15-minute candles for live trading initialization
        
        Args:
            symbol: Trading symbol
            instruments_df: Instruments dataframe
            days_back: Number of days to look back
        
        Returns:
            DataFrame with 15-minute candles or None if failed
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        return self.fetch_historical_data(
            symbol=symbol,
            instruments_df=instruments_df,
            start_date=start_date,
            end_date=end_date,
            interval="15min"
        )
    
    def fetch_1min_candles(self, symbol: str, instruments_df: pd.DataFrame,
                          start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """
        Fetch 1-minute candles for demo mode
        
        Args:
            symbol: Trading symbol
            instruments_df: Instruments dataframe
            start_date: Start date
            end_date: End date
        
        Returns:
            DataFrame with 1-minute candles or None if failed
        """
        return self.fetch_historical_data(
            symbol=symbol,
            instruments_df=instruments_df,
            start_date=start_date,
            end_date=end_date,
            interval="1min"
        )
