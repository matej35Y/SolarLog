# MEMO Integration Guide

## Overview

The application now supports scraping prices from both HUPX and MEMO sources, with the ability to select which source to use in the daily analysis UI.

## What Was Implemented

### 1. Database Model Updates
- Added `source` field to `HourlyPrice` model
- Updated unique constraint to include `source` (prevents duplicates per date/hour/source combination)
- Default source is 'hupx' for backward compatibility

### 2. MEMO Scraper (`MEMOScraper`)
- Created scraper class for https://dam.memo.mk/
- Attempts multiple data extraction methods:
  - API endpoint detection
  - HTML table scraping
  - JSON data extraction from script tags
  - Common API endpoint patterns

### 3. API Updates
- `/api/prices/by-date/{date}` - Now accepts optional `source` parameter
- `/api/analysis/by-date/{date}` - Now accepts optional `source` parameter
- Both endpoints filter results by source when provided

### 4. UI Updates
- Added source selector dropdown in daily analysis page
- Options: "All Sources", "HUPX", "MEMO"
- Default selection: "HUPX"

## Database Migration

Run the migration script to add the `source` column to existing records:

```bash
python3 migrate_add_source.py
```

This will:
- Add `source` column if it doesn't exist
- Set all existing records to `source='hupx'`
- Update the unique constraint

## MEMO Scraper Status

⚠️ **Note**: The MEMO scraper is currently a template implementation. It needs refinement based on:

1. **Hourly Data Availability**: The MEMO website (dam.memo.mk) shows summary prices (Base Price, Peak Price) but the exact location of hourly breakdown data needs to be identified.

2. **Data Source Options**:
   - Check if MEMO has a public API endpoint for hourly prices
   - Look for detail pages that show hourly breakdowns
   - Check if there's a downloadable data format (CSV, JSON, etc.)

3. **Current Implementation**: The scraper tries multiple approaches but may need adjustment once the exact data structure is known.

## Testing the MEMO Scraper

To test the MEMO scraper:

```python
from app.scraper_factory import ScraperFactory

# Get MEMO scraper
memo_scraper = ScraperFactory.get_scraper('memo')

# Try scraping a date
data = memo_scraper.scrape_prices(target_date='2025-01-06')
print(f"Scraped {len(data)} records")
```

## Using the Source Selector in UI

1. Navigate to `/ui/daily`
2. Select a date
3. Choose price source from dropdown:
   - **All Sources**: Shows data from both HUPX and MEMO (if available)
   - **HUPX**: Shows only HUPX prices
   - **MEMO**: Shows only MEMO prices
4. Click "Load Data"

## API Usage Examples

### Get prices for a specific date and source:
```bash
# HUPX only
GET /api/prices/by-date/2025-01-06?source=hupx

# MEMO only
GET /api/prices/by-date/2025-01-06?source=memo

# All sources
GET /api/prices/by-date/2025-01-06
```

### Get analysis with source filter:
```bash
# HUPX analysis
GET /api/analysis/by-date/2025-01-06?source=hupx

# MEMO analysis
GET /api/analysis/by-date/2025-01-06?source=memo
```

## Next Steps

1. **Identify MEMO Hourly Data Source**:
   - Inspect MEMO website for hourly price endpoints
   - Check if there's a detail page for specific dates
   - Look for API documentation

2. **Refine MEMO Scraper**:
   - Update `_scrape_from_html()` method based on actual HTML structure
   - Implement proper hourly data extraction
   - Add error handling for missing data

3. **Test Integration**:
   - Scrape MEMO data for various dates
   - Verify data quality and format
   - Test UI with both sources

## Troubleshooting

### No MEMO data available
- Check if MEMO website is accessible
- Verify the scraper can find hourly data
- Check logs for scraping errors

### Source selector not working
- Ensure database migration was run
- Check browser console for JavaScript errors
- Verify API endpoints are returning source field

### Duplicate data warnings
- This is normal - the system prevents duplicates per date/hour/source
- Each source can have its own price for the same date/hour
