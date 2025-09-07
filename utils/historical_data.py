"""
Historical data fetcher for demo trading mode
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from utils.rate_limiter import rate_limit, make_rate_limited_request, add_delay_between_requests

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
            
            # Map interval to API format
            interval_map = {
                "1min": "1",
                "5min": "5", 
                "15min": "15",
                "30min": "30",
                "1hour": "60",
                "1day": "D"
            }
            
            api_interval = interval_map.get(interval, interval)
            
            # Prepare request body
            request_body = {
                "securityId": security_id,
                "exchangeSegment": "NSE_FNO",
                "instrument": "OPTIDX",
                "fromDate": start_date.strftime('%Y-%m-%d %H:%M:%S'),
                "toDate": end_date.strftime('%Y-%m-%d %H:%M:%S'),
                "interval": api_interval,
                "oi": False
            }
            
            print(f"Request body: {request_body}")
            
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'access-token': self.access_token
            }
            
            # Use rate-limited request to avoid hitting API limits
            response = make_rate_limited_request('POST', self.base_url, json=request_body, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                # Handle different response formats
                if isinstance(data, list) and len(data) > 0:
                    # List of candles
                    df = pd.DataFrame(data)
                elif isinstance(data, dict) and 'data' in data and data['data']:
                    # Nested data structure
                    df = pd.DataFrame(data['data'])
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
                    else:
                        # Single candle object
                        df = pd.DataFrame([data])
                else:
                    print("No historical data found")
                    return None
                
                # Convert timestamp to datetime
                try:
                    # Try different parsing strategies
                    if df['timestamp'].dtype == 'object':
                        # Check if timestamps are Unix timestamps (numbers)
                        first_timestamp = str(df['timestamp'].iloc[0])
                        if first_timestamp.replace('.', '').replace('-', '').isdigit():
                            # Likely Unix timestamp - convert from seconds or milliseconds
                            try:
                                # Try as seconds first
                                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='s', utc=True)
                            except:
                                try:
                                    # Try as milliseconds
                                    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms', utc=True)
                                except:
                                    # Try as nanoseconds
                                    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ns', utc=True)
                        else:
                            # Try standard datetime parsing
                            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
                    else:
                        # Already numeric, try Unix timestamp conversion
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce', utc=True)
                    
                    # Convert UTC to IST (UTC+5:30)
                    df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Kolkata')
                    
                    # Check if we have any invalid timestamps
                    invalid_timestamps = df['timestamp'].isna().sum()
                    if invalid_timestamps > 0:
                        # Remove rows with invalid timestamps
                        df = df.dropna(subset=['timestamp'])
                    
                    # Check for timestamps that are too old (before 2000)
                    comparison_date = pd.Timestamp('2000-01-01').tz_localize('Asia/Kolkata')
                    old_timestamps = (df['timestamp'] < comparison_date).sum()
                    if old_timestamps > 0 and old_timestamps == len(df):
                        # If all timestamps are old, try alternative parsing
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
                                    df['timestamp'] = pd.to_datetime(raw_timestamps, unit=unit, utc=True)
                                    df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Kolkata')
                                    break
                            except:
                                continue
                    
                except Exception as e:
                    print(f"Error converting timestamps: {e}")
                    return None
                
                # Sort by timestamp
                df = df.sort_values('timestamp').reset_index(drop=True)
                return df
            else:
                print(f"API request failed with status {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error making API request: {e}")
            return None
    
    def fetch_15min_candles(self, symbol: str, instruments_df: pd.DataFrame, 
                           days_back: int = 30, start_date: datetime = None, 
                           end_date: datetime = None) -> Optional[pd.DataFrame]:
        """
        Fetch 15-minute candles for live trading initialization
        """
        if start_date is None or end_date is None:
            # Use days_back parameter
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
    
    def fetch_5min_candles(self, symbol: str, instruments_df: pd.DataFrame,
                          start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """
        Fetch 5-minute candles for liquidity analysis
        
        Args:
            symbol: Trading symbol
            instruments_df: Instruments dataframe
            start_date: Start date
            end_date: End date
        
        Returns:
            DataFrame with 5-minute candles or None if failed
        """
        return self.fetch_historical_data(
            symbol=symbol,
            instruments_df=instruments_df,
            start_date=start_date,
            end_date=end_date,
            interval="5min"
        )
    
    def fetch_10_days_historical_data(self, symbol: str, instruments_df: pd.DataFrame,
                                       reference_date: datetime = None, hist_days: float = 1.0) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Fetch 10 days of historical data for both 5min and 15min timeframes
        This is used for ERL to IRL strategy initialization
        
        Args:
            symbol: Trading symbol
            instruments_df: Instruments dataframe
            reference_date: Reference date to calculate 10 days back from (default: current time)
        
        Returns:
            Dictionary with '5min' and '15min' DataFrames
        """
        from datetime import datetime, timedelta
        
        # Calculate date range (10 trading days back from reference date)
        if reference_date is None:
            reference_date = datetime.now()
        
        end_date = reference_date
        start_date = end_date - timedelta(days=hist_days) # 14 calendar days to ensure 10 trading days
        
        print(f"Fetching 10 days of historical data for {symbol}")
        print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Fetch 5-minute candles
        print("Fetching 5-minute candles...")
        candles_5min = self.fetch_5min_candles(symbol, instruments_df, start_date, end_date)
        
        # Add delay between API calls to respect rate limits
        print("Waiting to respect API rate limits...")
        add_delay_between_requests(delay_seconds=0.5)  # 500ms delay
        
        # Fetch 15-minute candles
        print("Fetching 15-minute candles...")
        candles_15min = self.fetch_15min_candles(symbol, instruments_df, start_date=start_date, end_date=end_date)
        
        result = {
            '5min': candles_5min,
            '15min': candles_15min
        }
        
        # Print summary
        if candles_5min is not None:
            print(f"✅ 5-minute candles: {len(candles_5min)} candles")
            print(f"   Date range: {candles_5min['timestamp'].min()} to {candles_5min['timestamp'].max()}")
        else:
            print("❌ Failed to fetch 5-minute candles")
        
        if candles_15min is not None:
            print(f"✅ 15-minute candles: {len(candles_15min)} candles")
            print(f"   Date range: {candles_15min['timestamp'].min()} to {candles_15min['timestamp'].max()}")
        else:
            print("❌ Failed to fetch 15-minute candles")
        
        return result