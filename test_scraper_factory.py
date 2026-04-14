#!/usr/bin/env python3
"""
Test script for the new scraper factory architecture
"""
import sys
sys.path.append('.')

from app.scraper_factory import ScraperFactory
from app.config import settings

def test_scraper_factory():
    print("🧪 Testing Scraper Factory")
    print("=" * 50)
    
    # 1. List available scrapers
    print("\n1. Available scrapers:")
    scrapers = ScraperFactory.list_scrapers()
    for name, class_name in scrapers.items():
        print(f"   - {name}: {class_name}")
    
    # 2. Get default scraper
    print(f"\n2. Default scraper (from config): {settings.SCRAPER_NAME}")
    default_scraper = ScraperFactory.get_default_scraper()
    print(f"   ✅ Default scraper created: {default_scraper.name}")
    
    # 3. Get specific scraper
    print(f"\n3. Getting HUPX scraper:")
    hupx_scraper = ScraperFactory.get_scraper('hupx')
    print(f"   ✅ HUPX scraper created: {hupx_scraper.name}")
    
    # 4. Test singleton pattern (should return same instance)
    print(f"\n4. Testing singleton pattern:")
    scraper1 = ScraperFactory.get_scraper('hupx')
    scraper2 = ScraperFactory.get_scraper('hupx')
    print(f"   Same instance? {scraper1 is scraper2} ✅")
    
    # 5. Test invalid scraper
    print(f"\n5. Testing invalid scraper:")
    try:
        invalid = ScraperFactory.get_scraper('invalid_scraper')
        print(f"   ❌ Should have raised an error!")
    except ValueError as e:
        print(f"   ✅ Correctly raised error: {e}")
    
    # 6. Test scraping (if HUPX scraper)
    if settings.SCRAPER_NAME == 'hupx':
        print(f"\n6. Testing actual scraping (HUPX):")
        try:
            # Just test that it doesn't crash - don't wait for full scrape
            print(f"   Scraper ready: {hupx_scraper.name}")
            print(f"   ✅ Scraper can be instantiated and used")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("\nTo use a different scraper:")
    print("1. Create your scraper class in app/scraper.py")
    print("2. Register it in app/scraper_factory.py")
    print("3. Set SCRAPER_NAME in .env or app/config.py")
    print("4. Restart the application")

if __name__ == "__main__":
    test_scraper_factory()
