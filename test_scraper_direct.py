#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scraper import HUPXScraper
import json

def test_scraper():
    print("Testing HUPX Scraper directly...")
    
    scraper = HUPXScraper()
    
    print("1. Testing PDF extraction...")
    pdf_data = scraper._extract_data_from_pdfs()
    print(f"PDF data extracted: {len(pdf_data)} records")
    if pdf_data:
        print("Sample PDF data:")
        for i, record in enumerate(pdf_data[:3]):
            print(f"  {i+1}: {record}")
    
    print("\n2. Testing full scrape...")
    full_data = scraper.scrape_prices()
    print(f"Full scrape result: {len(full_data)} records")
    if full_data:
        print("Sample full data:")
        for i, record in enumerate(full_data[:5]):
            print(f"  {i+1}: {record}")
    
    print("\n3. Testing dummy data...")
    dummy_data = scraper._get_dummy_data()
    print(f"Dummy data: {len(dummy_data)} records")
    if dummy_data:
        print("Sample dummy data:")
        for i, record in enumerate(dummy_data[:5]):
            print(f"  {i+1}: {record}")

if __name__ == "__main__":
    test_scraper()
