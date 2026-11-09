#!/usr/bin/env python3
"""
Simple Scraper Restart Script

Use this when the scraper bugs out every 4th date.
Just run: python3 restart_scraper.py
"""

import sys
sys.path.append('.')
from app.services.hupx_scraper import HUPXScraper
from app.models.database import HourlyPrice, session
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def restart_scraper():
    """Restart the scraper and test it"""
    print("🔄 RESTARTING HUPX SCRAPER...")
    print("=" * 50)
    
    try:
        # Initialize scraper
        scraper = HUPXScraper()
        print("✅ Scraper initialized")
        
        # Test today's data
        print("\n📊 Testing today's data...")
        today_data = scraper.scrape_prices()
        print(f"✅ Today: {len(today_data)} records")
        
        # Test yesterday's data
        print("\n📊 Testing yesterday's data...")
        yesterday_data = scraper.scrape_prices(days_back=1)
        print(f"✅ Yesterday: {len(yesterday_data)} records")
        
        # Test a few recent dates
        print("\n📊 Testing recent dates...")
        test_dates = ['2025-09-14', '2025-09-15', '2025-10-01', '2025-10-02']
        
        for date in test_dates:
            try:
                data = scraper.scrape_prices(target_date=date)
                status = "✅" if data else "❌"
                print(f"  {status} {date}: {len(data)} records")
            except Exception as e:
                print(f"  ❌ {date}: ERROR - {str(e)}")
        
        # Check database status
        print("\n💾 Database status:")
        total_records = session.query(HourlyPrice).count()
        print(f"  Total records: {total_records}")
        
        # Check recent dates in DB
        recent_dates = []
        for i in range(5):
            date = datetime.now().date() - timedelta(days=i)
            count = session.query(HourlyPrice).filter(HourlyPrice.date == date).count()
            status = "✅" if count > 0 else "❌"
            recent_dates.append(f"{status} {date}: {count} records")
        
        print("  Recent dates:")
        for status in recent_dates:
            print(f"    {status}")
        
        print("\n🎉 SCRAPER RESTART COMPLETE!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ RESTART FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 50)

if __name__ == "__main__":
    restart_scraper()
