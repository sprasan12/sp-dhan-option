#!/usr/bin/env python3
"""
Test script to check symbol lookup
"""

import pandas as pd
import os

def test_symbol_lookup():
    """Test symbol lookup in instruments file"""
    
    instruments_file = "dhan_instruments.csv"
    
    if not os.path.exists(instruments_file):
        print(f"Instruments file {instruments_file} not found!")
        return
    
    print(f"Loading instruments from {instruments_file}...")
    df = pd.read_csv(instruments_file)
    
    # Filter for NSE options
    options_df = df[
        (df['EXCH_ID'] == 'NSE') & 
        (df['SEGMENT'] == 'D') &
        (df['INSTRUMENT'] == 'OPTIDX')
    ]
    
    print(f"Found {len(options_df)} NSE options")
    
    # Test the exact symbol we're using
    test_symbol = "NIFTY 21 AUG 24700 CALL"
    print(f"\nLooking for exact symbol: '{test_symbol}'")
    
    exact_match = options_df[options_df['DISPLAY_NAME'] == test_symbol]
    if not exact_match.empty:
        print(f"✓ Found exact match: {exact_match.iloc[0]['DISPLAY_NAME']} (ID: {exact_match.iloc[0]['SECURITY_ID']})")
    else:
        print(f"✗ No exact match found for '{test_symbol}'")
        
        # Try to find similar symbols
        print("\nLooking for similar symbols...")
        
        # Look for NIFTY symbols
        nifty_symbols = options_df[options_df['DISPLAY_NAME'].str.contains('NIFTY', case=False)]
        print(f"Found {len(nifty_symbols)} NIFTY symbols")
        
        # Look for AUG symbols
        aug_symbols = options_df[options_df['DISPLAY_NAME'].str.contains('AUG', case=False)]
        print(f"Found {len(aug_symbols)} AUG symbols")
        
        # Look for 24700 strike
        strike_24700 = options_df[options_df['DISPLAY_NAME'].str.contains('24700', case=False)]
        print(f"Found {len(strike_24700)} symbols with strike 24700")
        
        # Show some sample NIFTY symbols
        print("\nSample NIFTY symbols:")
        for idx, row in nifty_symbols.head(10).iterrows():
            print(f"  {row['DISPLAY_NAME']} (ID: {row['SECURITY_ID']})")

if __name__ == "__main__":
    test_symbol_lookup()
