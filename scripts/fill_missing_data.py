#!/usr/bin/env python3
"""
Fill Missing Data Script

This script fills in missing data gaps in the HUPX database.
It will attempt to scrape data for all missing dates and report which ones
have data available and which ones don't.
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

def get_missing_dates(start_date, end_date):
    """Get list of missing dates in the database"""
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    missing_dates = []
    current_date = start
    while current_date <= end:
        count = session.query(HourlyPrice).filter(HourlyPrice.date == current_date).count()
        if count == 0:
            missing_dates.append(current_date)
        current_date += timedelta(days=1)
    
    return missing_dates

def fill_missing_data(start_date, end_date, max_days=None):
    """Fill missing data for a date range"""
    scraper = HUPXScraper()
    
    # Get missing dates
    missing_dates = get_missing_dates(start_date, end_date)
    logger.info(f"Found {len(missing_dates)} missing dates between {start_date} and {end_date}")
    
    if max_days:
        missing_dates = missing_dates[:max_days]
        logger.info(f"Limiting to first {max_days} dates")
    
    # Fill missing dates
    filled_dates = []
    failed_dates = []
    
    for i, date in enumerate(missing_dates, 1):
        try:
            date_str = date.strftime('%Y-%m-%d')
            logger.info(f"[{i}/{len(missing_dates)}] Scraping data for {date_str}")
            
            data = scraper.scrape_prices(target_date=date_str)
            
            if data:
                filled_dates.append({
                    "date": date_str,
                    "records": len(data)
                })
                logger.info(f"✅ Successfully filled {date_str} with {len(data)} records")
            else:
                failed_dates.append({
                    "date": date_str,
                    "reason": "No data available in HUPX API"
                })
                logger.warning(f"❌ No data available for {date_str}")
                
        except Exception as e:
            failed_dates.append({
                "date": date_str,
                "reason": str(e)
            })
            logger.error(f"❌ Failed to scrape {date_str}: {str(e)}")
    
    # Summary
    logger.info(f"\n=== SUMMARY ===")
    logger.info(f"Total missing dates: {len(missing_dates)}")
    logger.info(f"Successfully filled: {len(filled_dates)}")
    logger.info(f"Failed: {len(failed_dates)}")
    
    if filled_dates:
        logger.info(f"\n✅ Successfully filled dates:")
        for item in filled_dates:
            logger.info(f"  {item['date']}: {item['records']} records")
    
    if failed_dates:
        logger.info(f"\n❌ Failed dates:")
        for item in failed_dates:
            logger.info(f"  {item['date']}: {item['reason']}")
    
    return {
        "filled_dates": filled_dates,
        "failed_dates": failed_dates,
        "summary": {
            "total_missing": len(missing_dates),
            "successfully_filled": len(filled_dates),
            "failed": len(failed_dates)
        }
    }

def main():
    """Main function"""
    print("=== HUPX Missing Data Filler ===\n")
    
    # You can customize these dates
    start_date = "2025-08-01"
    end_date = "2025-10-05"
    max_days = 50  # Limit to prevent too many API calls
    
    print(f"Filling missing data from {start_date} to {end_date}")
    print(f"Maximum {max_days} dates to process\n")
    
    result = fill_missing_data(start_date, end_date, max_days)
    
    print(f"\n=== FINAL RESULT ===")
    print(f"Successfully filled: {result['summary']['successfully_filled']} dates")
    print(f"Failed: {result['summary']['failed']} dates")
    print(f"Total processed: {result['summary']['total_missing']} dates")

if __name__ == "__main__":
    main()
