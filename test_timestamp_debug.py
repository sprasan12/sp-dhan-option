"""
Test script to debug timestamp format from Dhan API
"""

import requests
import pandas as pd
from datetime import datetime, timedelta

def test_dhan_api_timestamps():
    """Test Dhan API to see what timestamp format it returns"""
    
    # Use a sample request (you'll need to replace with your actual credentials)
    access_token = "your_access_token_here"  # Replace with actual token
    client_id = "your_client_id_here"        # Replace with actual client ID
    
    # Sample request body
    request_body = {
        "securityId": "47205",  # Sample security ID
        "exchangeSegment": "NSE_FNO",
        "instrument": "OPTIDX",
        "fromDate": "2024-12-15 09:15:00",
        "toDate": "2024-12-16 16:00:00",
        "interval": "1",
        "oi": False
    }
    
    headers = {
        'access-token': access_token,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    try:
        print("Testing Dhan API timestamp format...")
        print(f"Request body: {request_body}")
        
        response = requests.post(
            "https://api.dhan.co/v2/charts/intraday",
            headers=headers,
            json=request_body
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nAPI Response type: {type(data)}")
            
            # Analyze the timestamp format
            if isinstance(data, list) and len(data) > 0:
                print(f"List response with {len(data)} records")
                if len(data) > 0:
                    first_record = data[0]
                    print(f"First record keys: {list(first_record.keys())}")
                    if 'timestamp' in first_record:
                        raw_timestamp = first_record['timestamp']
                        print(f"Raw timestamp value: {raw_timestamp}")
                        print(f"Raw timestamp type: {type(raw_timestamp)}")
                        
                        # Try different parsing methods
                        print("\nTrying different timestamp parsing methods:")
                        
                        # Method 1: Direct pandas conversion
                        try:
                            parsed1 = pd.to_datetime(raw_timestamp)
                            print(f"Method 1 (pd.to_datetime): {parsed1}")
                        except Exception as e:
                            print(f"Method 1 failed: {e}")
                        
                        # Method 2: Unix seconds
                        try:
                            parsed2 = pd.to_datetime(float(raw_timestamp), unit='s')
                            print(f"Method 2 (Unix seconds): {parsed2}")
                        except Exception as e:
                            print(f"Method 2 failed: {e}")
                        
                        # Method 3: Unix milliseconds
                        try:
                            parsed3 = pd.to_datetime(float(raw_timestamp), unit='ms')
                            print(f"Method 3 (Unix milliseconds): {parsed3}")
                        except Exception as e:
                            print(f"Method 3 failed: {e}")
                        
                        # Method 4: Unix nanoseconds
                        try:
                            parsed4 = pd.to_datetime(float(raw_timestamp), unit='ns')
                            print(f"Method 4 (Unix nanoseconds): {parsed4}")
                        except Exception as e:
                            print(f"Method 4 failed: {e}")
                        
            elif isinstance(data, dict):
                print(f"Dict response with keys: {list(data.keys())}")
                if 'timestamp' in data and isinstance(data['timestamp'], list):
                    print(f"Timestamp array length: {len(data['timestamp'])}")
                    if len(data['timestamp']) > 0:
                        raw_timestamp = data['timestamp'][0]
                        print(f"First raw timestamp: {raw_timestamp}")
                        print(f"First raw timestamp type: {type(raw_timestamp)}")
                        
                        # Try parsing
                        try:
                            parsed = pd.to_datetime(raw_timestamp)
                            print(f"Parsed timestamp: {parsed}")
                        except Exception as e:
                            print(f"Parsing failed: {e}")
                            
                            # Try Unix timestamp
                            try:
                                parsed_unix = pd.to_datetime(float(raw_timestamp), unit='s')
                                print(f"Unix seconds parsing: {parsed_unix}")
                            except Exception as e2:
                                print(f"Unix parsing failed: {e2}")
            
        else:
            print(f"API request failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Error testing API: {e}")

if __name__ == "__main__":
    print("Dhan API Timestamp Debug Tool")
    print("=" * 40)
    print("Note: You need to replace the access_token and client_id with your actual credentials")
    print("This script will help identify the timestamp format returned by the Dhan API")
    print()
    
    # Uncomment the line below and add your credentials to test
    # test_dhan_api_timestamps()
