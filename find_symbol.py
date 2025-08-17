#!/usr/bin/env python3
"""
Script to find valid symbols in the instruments file
"""

import pandas as pd
import os

def find_symbols():
    """Find valid symbols in the instruments file"""
    
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
    
    # Look for symbols containing "NIFTY" and "AUG"
    nifty_aug_symbols = options_df[
        options_df['DISPLAY_NAME'].str.contains('NIFTY', case=False) &
        options_df['DISPLAY_NAME'].str.contains('AUG', case=False)
    ]
    
    print(f"\nFound {len(nifty_aug_symbols)} NIFTY AUG symbols:")
    for idx, row in nifty_aug_symbols.head(10).iterrows():
        print(f"  {row['DISPLAY_NAME']} (ID: {row['SECURITY_ID']})")
    
    # Look for symbols with "24700" (strike price)
    strike_24700 = options_df[
        options_df['DISPLAY_NAME'].str.contains('24700', case=False)
    ]
    
    print(f"\nFound {len(strike_24700)} symbols with strike 24700:")
    for idx, row in strike_24700.head(5).iterrows():
        print(f"  {row['DISPLAY_NAME']} (ID: {row['SECURITY_ID']})")
    
    # Look for CALL options
    call_options = options_df[
        options_df['DISPLAY_NAME'].str.contains('CALL', case=False)
    ]
    
    print(f"\nFound {len(call_options)} CALL options:")
    for idx, row in call_options.head(5).iterrows():
        print(f"  {row['DISPLAY_NAME']} (ID: {row['SECURITY_ID']})")

if __name__ == "__main__":
    find_symbols()
