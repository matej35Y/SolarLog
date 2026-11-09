#!/usr/bin/env python3
"""
HUPX Scraper Usage Examples

This file demonstrates how to use the updated HUPX scraper that now uses the JSON API
from https://labs.hupx.hu/data/v1/dam_aggregated_trading_data

The scraper can now fetch real-time electricity market data for any date.
"""

import sys
sys.path.append('.')
from app.services.hupx_scraper import HUPXScraper
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Demonstrate different ways to use the HUPX scraper"""
    
    # Initialize the scraper
    scraper = HUPXScraper()
    
    print("=== HUPX Scraper Usage Examples ===\n")
    
    # Example 1: Scrape today's data
    print("1. Scraping today's data:")
    today_data = scraper.scrape_prices()
    print(f"   Found {len(today_data)} hourly records")
    if today_data:
        avg_price = sum(r['price'] for r in today_data) / len(today_data)
        print(f"   Average price: {avg_price:.2f} €/MWh")
        print(f"   Price range: {min(r['price'] for r in today_data):.2f} - {max(r['price'] for r in today_data):.2f} €/MWh")
    
    # Example 2: Scrape yesterday's data
    print("\n2. Scraping yesterday's data:")
    yesterday_data = scraper.scrape_prices(days_back=1)
    print(f"   Found {len(yesterday_data)} hourly records")
    
    # Example 3: Scrape specific date
    print("\n3. Scraping specific date (2025-10-05):")
    specific_data = scraper.scrape_prices(target_date='2025-10-05')
    print(f"   Found {len(specific_data)} hourly records")
    
    # Example 4: Scrape multiple dates
    print("\n4. Scraping last 7 days:")
    week_data = scraper.scrape_multiple_dates('2025-09-28', days_count=7)
    print(f"   Found {len(week_data)} total records for 7 days")
    
    # Example 5: Scrape date range
    print("\n5. Scraping date range (2025-10-01 to 2025-10-03):")
    range_data = scraper.scrape_multiple_dates('2025-10-01', end_date='2025-10-03')
    print(f"   Found {len(range_data)} total records for 3 days")
    
    print("\n=== Usage Summary ===")
    print("The scraper now uses the HUPX Labs JSON API:")
    print("- URL: https://labs.hupx.hu/data/v1/dam_aggregated_trading_data")
    print("- Returns real-time electricity market data")
    print("- Supports any date (past or present)")
    print("- Automatically saves data to database")
    print("- Avoids duplicate entries")
    
    print("\n=== Available Methods ===")
    print("1. scraper.scrape_prices() - Today's data")
    print("2. scraper.scrape_prices(days_back=N) - N days ago")
    print("3. scraper.scrape_prices(target_date='YYYY-MM-DD') - Specific date")
    print("4. scraper.scrape_multiple_dates(start_date, days_count=N) - Multiple days")
    print("5. scraper.scrape_multiple_dates(start_date, end_date) - Date range")

if __name__ == "__main__":
    main()
