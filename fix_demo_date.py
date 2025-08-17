#!/usr/bin/env python3
"""
Quick script to fix demo date configuration
"""

import os
from datetime import datetime, timedelta

def fix_demo_date():
    """Fix the demo start date to a recent past date"""
    
    # Calculate a recent past date (7 days ago)
    recent_date = datetime.now() - timedelta(days=7)
    demo_date = recent_date.strftime('%Y-%m-%d')
    
    print(f"Current date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"Setting demo start date to: {demo_date}")
    
    # Set environment variable
    os.environ['DEMO_START_DATE'] = demo_date
    
    print(f"DEMO_START_DATE set to: {demo_date}")
    print("You can also create a .env file with:")
    print(f"DEMO_START_DATE={demo_date}")
    
    return demo_date

if __name__ == "__main__":
    fix_demo_date()
