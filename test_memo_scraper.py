#!/usr/bin/env python3

import sys
import os
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scraper import MEMOScraper

def test_memo_scraper():
    print("Testing Refactored MEMO Scraper...")
    
    scraper = MEMOScraper()
    
    # Test with a specific recent date
    test_date = "2026-02-26" 
    print(f"\n1. Scraping data for {test_date}...")
    data = scraper.scrape_prices(target_date=test_date)
    
    print(f"Result: {len(data)} records found")
    if data:
        print("Sample records (first 3):")
        for i, record in enumerate(data[:3]):
            print(f"  {i+1}: {record}")
        
        # Check if we have 24 hours
        if len(data) == 24:
            print("SUCCESS: Found exactly 24 hourly records.")
        else:
            print(f"WARNING: Found {len(data)} records instead of 24.")
            
        # Check prices
        all_prices = [r['price'] for r in data]
        if all(p > 0 for p in all_prices):
            print("SUCCESS: All prices are positive.")
        else:
            print(f"WARNING: Some prices are zero or negative: {all_prices}")
    else:
        print("FAILURE: No data returned from scraper.")

if __name__ == "__main__":
    test_memo_scraper()
