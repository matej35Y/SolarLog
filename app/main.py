from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_utils.tasks import repeat_every
from datetime import datetime, timedelta
import logging
from typing import Optional, List
import calendar
import requests
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .scraper_factory import ScraperFactory
from .config import settings
from .models import HourlyPrice, session, EnergyGeneration
from .energy_service import EnergyDataService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="API for HUPX electricity price data"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global cache for storing the scraped data
price_cache = {
    "last_updated": None,
    "data": None
}

# Initialize scraper using factory (supports multiple scraper types)
scraper = ScraperFactory.get_scraper(settings.SCRAPER_NAME)
logger.info(f"Using scraper: {settings.SCRAPER_NAME} ({scraper.name})")

# Initialize the energy service with Tailscale support
energy_service = EnergyDataService(
    device_ip=settings.ENERGY_DEVICE_IP,
    tailscale_ip=getattr(settings, 'ENERGY_DEVICE_TAILSCALE_IP', None),
    use_tailscale_first=getattr(settings, 'USE_TAILSCALE_FIRST', False)
)

# Setup templates and static files
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
async def startup_event():
    """Initial cache population on startup"""
    logger.info("Starting up the application...")
    await update_price_cache()


@app.on_event("startup")
@repeat_every(seconds=settings.CACHE_TIMEOUT)
async def update_price_cache():
    """Background task to update the price cache periodically"""
    try:
        logger.info("Updating price cache...")
        price_cache["data"] = scraper.scrape_prices()
        price_cache["last_updated"] = datetime.now()
        logger.info(f"Price cache updated successfully. Cache size: {len(price_cache['data']) if price_cache['data'] else 0} records")
    except Exception as e:
        logger.error(f"Failed to update price cache: {str(e)}")
        logger.exception(e)  # This will print the full stack trace


@app.on_event("startup")
@repeat_every(seconds=settings.CACHE_TIMEOUT)
async def update_all_data():
    """Background task to update both price and energy data periodically"""
    try:
        # 1. Update price cache
        logger.info("Updating price cache...")
        price_cache["data"] = scraper.scrape_prices()
        price_cache["last_updated"] = datetime.now()
        logger.info(f"Price cache updated successfully. Cache size: {len(price_cache['data']) if price_cache['data'] else 0} records")
        
        # 2. Update energy data for recent days (up to 7 days back to recover from downtime)
        logger.info("Updating energy data for recent days...")
        for days_back in range(7):  # Update past 7 days
            try:
                energy_service.save_data_to_db(days_back)
                logger.info(f"Energy data updated for {days_back} days ago")
            except Exception as e:
                logger.error(f"Failed to update energy data for {days_back} days ago: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to update data: {str(e)}")
        logger.exception(e)  # This will print the full stack trace


@app.get("/")
async def root():
    """Root endpoint returning API information"""
    return {
        "name": settings.APP_NAME,
        "status": "running",
        "scraper": settings.SCRAPER_NAME,
        "scraper_name": scraper.name,
        "last_update": price_cache["last_updated"]
    }


@app.get("/api/scrapers")
async def list_scrapers():
    """List all available scrapers"""
    scrapers = ScraperFactory.list_scrapers()
    return {
        "available_scrapers": scrapers,
        "current_scraper": settings.SCRAPER_NAME,
        "current_scraper_name": scraper.name
    }


@app.get("/api/scrapers/switch/{scraper_name}")
async def switch_scraper(scraper_name: str):
    """Switch to a different scraper (requires app restart to take effect)"""
    try:
        # Validate scraper exists
        test_scraper = ScraperFactory.get_scraper(scraper_name)
        return {
            "status": "success",
            "message": f"Scraper '{scraper_name}' is available. Update SCRAPER_NAME in config or .env file and restart the app to switch.",
            "available_scraper": scraper_name,
            "scraper_name": test_scraper.name,
            "current_scraper": settings.SCRAPER_NAME
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/prices/current")
async def get_current_prices():
    """Get the current cached price data"""
    if not price_cache["data"]:
        raise HTTPException(status_code=503, detail="Price data not available")

    return {
        "last_updated": price_cache["last_updated"],
        "data": price_cache["data"]
    }


@app.get("/api/prices/refresh")
async def refresh_prices():
    """Force refresh the price cache"""
    try:
        await update_price_cache()
        return {
            "status": "success",
            "message": "Price cache updated successfully",
            "last_updated": price_cache["last_updated"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices/by-date/{date}")
async def get_prices_by_date(date: str, source: Optional[str] = None):
    """Get prices for a specific date (format: YYYY-MM-DD). Optional source filter: 'hupx' or 'memo'"""
    try:
        # Query database directly for the specified date
        query = session.query(HourlyPrice).filter(HourlyPrice.date == date)
        if source:
            query = query.filter(HourlyPrice.source == source)
        records = query.all()

        # If no records found, try to scrape the data
        if not records:
            logger.info(f"No data found for {date}, attempting to scrape...")
            try:
                # Use the appropriate scraper based on source
                if source:
                    from .scraper_factory import ScraperFactory
                    source_scraper = ScraperFactory.get_scraper(source)
                    scraped_data = source_scraper.scrape_prices(target_date=date)
                else:
                    scraped_data = scraper.scrape_prices(target_date=date)
                
                if scraped_data:
                    logger.info(f"Successfully scraped {len(scraped_data)} records for {date}")
                    # Query again after scraping
                    query = session.query(HourlyPrice).filter(HourlyPrice.date == date)
                    if source:
                        query = query.filter(HourlyPrice.source == source)
                    records = query.all()
                else:
                    logger.warning(f"No data available from API for {date}")
                    raise HTTPException(status_code=404, detail=f"No data available for date {date}")
            except Exception as scrape_error:
                logger.error(f"Failed to scrape data for {date}: {str(scrape_error)}")
                raise HTTPException(status_code=404, detail=f"No data available for date {date}")

        # Convert to dict format
        prices = [
            {
                "date": record.date.strftime('%Y-%m-%d'),
                "hour": record.hour,
                "price": record.price,
                "source": record.source
            }
            for record in records
        ]

        return {
            "date": date,
            "source": source or "all",
            "prices": prices
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting prices for {date}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices/by-dates")
async def get_prices_by_dates(dates: str):
    """Get prices for multiple dates (format: YYYY-MM-DD,YYYY-MM-DD)"""
    if not price_cache["data"]:
        raise HTTPException(status_code=503, detail="Price data not available")
    
    try:
        # Split the dates string into a list
        date_list = dates.split(',')
        
        # Filter prices for the specified dates
        result = {}
        for date in date_list:
            date = date.strip()  # Remove any whitespace
            prices = [
                price for price in price_cache["data"] 
                if price["date"] == date
            ]
            if prices:
                result[date] = prices
        
        if not result:
            raise HTTPException(status_code=404, detail="No prices found for the specified dates")
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices/from-db")
async def get_prices_from_db():
    """Get all prices from the database"""
    prices = session.query(HourlyPrice).all()
    return [
        {
            "date": price.date.strftime('%Y-%m-%d'),
            "hour": price.hour,
            "price": price.price
        }
        for price in prices
    ]


@app.post("/api/prices/fill-gaps")
async def fill_missing_data_gaps(start_date: str, end_date: str = None, max_days: int = 30):
    """Fill missing data gaps in the database for a date range"""
    try:
        from datetime import datetime, timedelta
        
        # Parse start date
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        # Determine end date
        if end_date:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end = start + timedelta(days=max_days-1)
        
        # Find missing dates
        missing_dates = []
        current_date = start
        while current_date <= end:
            count = session.query(HourlyPrice).filter(HourlyPrice.date == current_date).count()
            if count == 0:
                missing_dates.append(current_date)
            current_date += timedelta(days=1)
        
        logger.info(f"Found {len(missing_dates)} missing dates between {start} and {end}")
        
        # Fill missing dates
        filled_dates = []
        failed_dates = []
        
        for date in missing_dates:
            try:
                date_str = date.strftime('%Y-%m-%d')
                logger.info(f"Scraping data for {date_str}")
                data = scraper.scrape_prices(target_date=date_str)
                
                if data:
                    filled_dates.append({
                        "date": date_str,
                        "records": len(data)
                    })
                    logger.info(f"Successfully filled {date_str} with {len(data)} records")
                else:
                    failed_dates.append({
                        "date": date_str,
                        "reason": "No data available in HUPX API"
                    })
                    logger.warning(f"No data available for {date_str}")
                    
            except Exception as e:
                failed_dates.append({
                    "date": date_str,
                    "reason": str(e)
                })
                logger.error(f"Failed to scrape {date_str}: {str(e)}")
        
        return {
            "status": "completed",
            "total_missing": len(missing_dates),
            "filled_dates": filled_dates,
            "failed_dates": failed_dates,
            "summary": {
                "successfully_filled": len(filled_dates),
                "failed": len(failed_dates)
            }
        }
        
    except Exception as e:
        logger.error(f"Error filling data gaps: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices/missing-dates")
async def get_missing_dates(start_date: str, end_date: str = None):
    """Get list of missing dates in the database for a date range"""
    try:
        from datetime import datetime, timedelta
        
        # Parse dates
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end = datetime.now().date()
        
        # Find missing dates
        missing_dates = []
        current_date = start
        while current_date <= end:
            count = session.query(HourlyPrice).filter(HourlyPrice.date == current_date).count()
            if count == 0:
                missing_dates.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "missing_dates": missing_dates,
            "total_missing": len(missing_dates)
        }
        
    except Exception as e:
        logger.error(f"Error getting missing dates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/energy/fetch/{days_back}")
async def fetch_energy_data(days_back: int):
    """Fetch and store energy data for a specific day in the past"""
    success = energy_service.save_data_to_db(days_back)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to fetch energy data")
    
    return {"status": "success", "message": f"Energy data for {days_back} days ago fetched and stored"}


@app.get("/api/energy/direct/{date}")
async def get_energy_direct_from_hardware(date: str):
    """Fetch energy data DIRECTLY from hardware, bypassing the database"""
    try:
        # Parse the date string to ensure correct format
        parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
        today = datetime.now().date()
        days_back = (today - parsed_date).days
        
        if days_back < 0:
            return {"error": "Cannot fetch future energy data", "date": date}

        logger.info(f"Direct hardware fetch requested for {date} ({days_back} days ago)")
        hourly_data, total_kwh = energy_service.get_hourly_data(days_back)
        
        if hourly_data is None:
            raise HTTPException(status_code=503, detail="Failed to connect to energy device or parse data")
            
        return {
            "source": "hardware_direct",
            "date": date,
            "days_back": days_back,
            "total_kwh": total_kwh,
            "hourly_data": hourly_data
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error in direct fetch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/energy/by-date/{date}")
async def get_energy_by_date(date: str):
    """Get energy generation for a specific date"""
    try:
        # Query database for energy data
        records = session.query(EnergyGeneration).filter(
            EnergyGeneration.date == date
        ).all()
        
        if not records:
            raise HTTPException(status_code=404, detail=f"No energy data found for date {date}")
        
        return {
            "date": date,
            "energy_data": [
                {
                    "hour": record.hour,
                    "energy_kwh": record.energy_kwh
                } for record in records
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/by-date/{date}")
async def get_price_energy_analysis(date: str, source: Optional[str] = None):
    """Get combined price and energy analysis for a specific date. Optional source filter: 'hupx' or 'memo'"""
    try:
        # Parse the date string to ensure correct format
        try:
            parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD")
        
        # Calculate days_back for energy data
        days_back = (datetime.now().date() - parsed_date).days
        
        # 1. Allow future dates but skip energy device check (production is always 0 for future)
        if days_back < 0:
            logger.info(f"Future date requested: {date}. Price discovery will be attempted.")
        else:
            # 2. Always fetch energy data for the requested date (if not in the future)
            logger.info(f"Ensuring energy data is available for {date}")
            try:
                energy_service.save_data_to_db(days_back)
                logger.info(f"Energy data for {date} is now up-to-date")
            except Exception as e:
                logger.warning(f"Failed to fetch energy data: {str(e)}")
        
        # 4. Get energy data from database
        energy_records = session.query(EnergyGeneration).filter(
            EnergyGeneration.date == parsed_date
        ).all()
        
        # 5. Get price data (first from database, then auto-scrape if missing)
        price_query = session.query(HourlyPrice).filter(HourlyPrice.date == parsed_date)
        if source:
            price_query = price_query.filter(HourlyPrice.source == source)
        price_records = price_query.all()
        
        # If no price data found, try to scrape it
        if not price_records:
            logger.info(f"No price data found for {date}, attempting to scrape...")
            try:
                # Use the appropriate scraper based on source
                if source:
                    from .scraper_factory import ScraperFactory
                    source_scraper = ScraperFactory.get_scraper(source)
                    scraped_data = source_scraper.scrape_prices(target_date=date)
                else:
                    scraped_data = scraper.scrape_prices(target_date=date)
                
                if scraped_data:
                    logger.info(f"Successfully scraped {len(scraped_data)} price records for {date}")
                    # Query again after scraping
                    price_query = session.query(HourlyPrice).filter(HourlyPrice.date == parsed_date)
                    if source:
                        price_query = price_query.filter(HourlyPrice.source == source)
                    price_records = price_query.all()
                else:
                    logger.warning(f"No price data available from API for {date}")
            except Exception as scrape_error:
                logger.error(f"Failed to scrape price data for {date}: {str(scrape_error)}")
        
        # If we don't have ANY data (neither energy nor price), return empty data structure
        if not energy_records and not price_records:
            logger.warning(f"No data at all found for {date}")
            
            # Create a minimal data structure with zeros instead of returning 404
            return {
                "hourly_data": [],
                "summary": {
                    "date": date,
                    "total_energy_kwh": 0,
                    "total_value": 0,
                    "arithmetic_avg_price_per_mwh": 0,
                    "weighted_avg_price_per_mwh": 0,
                    "working_hours_count": 0
                },
                "message": "No data available for this date"
            }
        
        if not energy_records:
            logger.info(f"No energy records for {date}, but price records exist. Proceeding with price data only.")
        elif not price_records:
            logger.info(f"No price records for {date}, but energy records exist. Proceeding with energy data only.")
        
        # Create a mapping for easier access
        energy_by_hour = {r.hour: r.energy_kwh for r in energy_records}
        price_by_hour = {r.hour: r.price for r in price_records}
        
        # Calculate hourly values and totals
        total_energy = 0
        total_value = 0
        analysis_data = []
        
        # Get all hours from both datasets
        all_hours = set(energy_by_hour.keys()) | set(price_by_hour.keys())
        
        # Sort hours numerically (H1, H2, ..., H24)
        def hour_to_number(hour):
            # Extract the number from the hour string (e.g., 'H1' -> 1)
            return int(hour[1:]) if hour[1:].isdigit() else 0
        
        sorted_hours = sorted(all_hours, key=hour_to_number)
        
        # Add this at the beginning of the get_price_energy_analysis function
        logger.info(f"Processing analysis for date: {date}")

        # Add this after loading energy records
        logger.info(f"Energy records: {[(r.hour, r.energy_kwh) for r in energy_records]}")

        for hour in sorted_hours:
            energy_kwh = energy_by_hour.get(hour, 0)
            price_per_mwh = price_by_hour.get(hour, 0)
            
            # Log each hour's energy value
            logger.info(f"Hour {hour}: energy_kwh={energy_kwh}, price={price_per_mwh}")
            
            # Convert kWh to MWh for calculation (1 MWh = 1000 kWh)
            energy_mwh = energy_kwh / 1000
            
            # Calculate value in EUR
            value = energy_mwh * price_per_mwh
            
            if energy_kwh > 0 or price_per_mwh > 0:  # Only include hours with data
                total_energy += energy_kwh
                total_value += value
                
                analysis_data.append({
                    "hour": hour,
                    "energy_kwh": round(energy_kwh, 3),
                    "price_per_mwh": round(price_per_mwh, 2),
                    "value": round(value, 2)
                })
        
        # Calculate total energy in MWh for summary
        total_energy_mwh = total_energy / 1000
        
        # Calculate simple arithmetic average of hourly prices (sum of all prices / number of hours)
        all_prices = [hour["price_per_mwh"] for hour in analysis_data]
        arithmetic_avg_price = sum(all_prices) / len(all_prices) if all_prices else 0
        
        # Calculate average price during working hours (when energy was produced)
        working_hours_prices = []
        working_hours_count = 0

        for hour in analysis_data:
            if hour["energy_kwh"] > 0:
                working_hours_prices.append(hour["price_per_mwh"])
                working_hours_count += 1

        logger.info(f"Working hours count: {working_hours_count}")
        logger.info(f"Working hours prices: {working_hours_prices}")

        working_hours_avg_price = 0
        if working_hours_count > 0:
            working_hours_avg_price = sum(working_hours_prices) / working_hours_count

        logger.info(f"Working hours avg price: {working_hours_avg_price}")
        
        return {
            "date": date,
            "hourly_data": analysis_data,
            "summary": {
                "total_energy_kwh": round(total_energy, 3),
                "total_energy_mwh": round(total_energy_mwh, 3),
                "total_value": round(total_value, 2),
                "average_price_per_mwh": round(total_value / total_energy_mwh if total_energy_mwh > 0 else 0, 2),
                "arithmetic_avg_price_per_mwh": round(arithmetic_avg_price, 2),
                "working_hours_avg_price_per_mwh": round(working_hours_avg_price, 2),
                "working_hours_count": working_hours_count
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/available-dates")
async def get_available_dates():
    """Get dates that have both price and energy data available"""
    try:
        # Get all dates with energy data
        energy_dates = session.query(EnergyGeneration.date).distinct().all()
        energy_dates = [d[0].strftime('%Y-%m-%d') for d in energy_dates]
        
        # Get all dates with price data
        price_dates = session.query(HourlyPrice.date).distinct().all()
        price_dates = [d[0].strftime('%Y-%m-%d') for d in price_dates]
        
        # Find dates that have both
        common_dates = sorted(set(energy_dates) & set(price_dates))
        
        return {
            "energy_dates": sorted(energy_dates),
            "price_dates": sorted(price_dates),
            "analysis_ready_dates": common_dates
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/by-month/{year_month}")
async def get_monthly_analysis(year_month: str, source: Optional[str] = None):
    """Get total_value for all days in a month (format: YYYY-MM). Optional source filter: 'hupx' or 'memo'"""
    try:
        # Validate the year_month format
        try:
            year, month = year_month.split('-')
            if len(year) != 4 or len(month) != 2:
                raise ValueError("Invalid format")
            year = int(year)
            month = int(month)
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Invalid format. Use YYYY-MM")
        
        logger.info(f"Processing monthly analysis for {year_month} with source={source or 'all'}")
        
        # Determine the number of days in the month
        _, last_day = calendar.monthrange(year, month)
        
        # Create a dictionary to store results
        monthly_data = {}
        days_processed = 0
        days_with_data = 0
        total_month_mwh = 0
        total_month_value = 0
        all_working_hour_prices = []
        
        # Process each day in the month
        for day in range(1, last_day + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            days_processed += 1
            
            # Skip future dates
            if date_obj > datetime.now().date():
                logger.info(f"Skipping future date: {date_str}")
                continue
                
            try:
                logger.info(f"Checking data for {date_str}")
                
                # Get energy data
                energy_records = session.query(EnergyGeneration).filter(
                    EnergyGeneration.date == date_obj
                ).all()
                
                if not energy_records:
                    logger.info(f"No energy data for {date_str}")
                    continue
                
                # Get price data (with optional source filter)
                price_query = session.query(HourlyPrice).filter(HourlyPrice.date == date_obj)
                if source:
                    price_query = price_query.filter(HourlyPrice.source == source)
                price_records = price_query.all()
                
                # If no price data found, try to scrape it (like daily endpoint)
                if not price_records:
                    logger.info(f"No price data found for {date_str}, attempting to scrape...")
                    try:
                        # Use the appropriate scraper based on source
                        if source:
                            source_scraper = ScraperFactory.get_scraper(source)
                            scraped_data = source_scraper.scrape_prices(target_date=date_str)
                        else:
                            # If no source specified, try both HUPX and MEMO
                            scraped_data = scraper.scrape_prices(target_date=date_str)
                            
                            # Also try MEMO if HUPX didn't return data
                            if not scraped_data:
                                memo_scraper = ScraperFactory.get_scraper('memo')
                                scraped_data = memo_scraper.scrape_prices(target_date=date_str)
                        
                        if scraped_data:
                            logger.info(f"Successfully scraped {len(scraped_data)} price records for {date_str}")
                            # Query again after scraping
                            price_query = session.query(HourlyPrice).filter(HourlyPrice.date == date_obj)
                            if source:
                                price_query = price_query.filter(HourlyPrice.source == source)
                            price_records = price_query.all()
                        else:
                            logger.warning(f"No price data available from scraper for {date_str}")
                    except Exception as scrape_error:
                        logger.error(f"Failed to scrape price data for {date_str}: {str(scrape_error)}")
                
                if not price_records:
                    logger.info(f"No price data available for {date_str} after scraping attempt")
                    continue
                
                logger.info(f"Found data for {date_str}: {len(energy_records)} energy records, {len(price_records)} price records")
                
                # Create mappings for easier access
                energy_by_hour = {r.hour: r.energy_kwh for r in energy_records}
                price_by_hour = {r.hour: r.price for r in price_records}
                
                # Calculate total value and energy
                total_value = 0
                total_energy_kwh = 0
                working_hour_prices = []
                
                # Get all hours from both datasets (use union like daily endpoint for consistency)
                all_hours = set(energy_by_hour.keys()) | set(price_by_hour.keys())
                
                if not all_hours:
                    logger.info(f"No hours found in energy or price data for {date_str}")
                    continue
                
                # Sort hours numerically (H1, H2, ..., H24) like daily endpoint
                def hour_to_number(hour):
                    return int(hour[1:]) if hour[1:].isdigit() else 0
                
                sorted_hours = sorted(all_hours, key=hour_to_number)
                
                for hour in sorted_hours:
                    energy_kwh = energy_by_hour.get(hour, 0)
                    price_per_mwh = price_by_hour.get(hour, 0)
                    
                    # Only include hours with data (same logic as daily endpoint)
                    if energy_kwh > 0 or price_per_mwh > 0:
                        # Add to total energy
                        total_energy_kwh += energy_kwh
                        
                        # Convert kWh to MWh for calculation
                        energy_mwh = energy_kwh / 1000
                        
                        # Calculate value in EUR (same calculation as daily endpoint)
                        value = energy_mwh * price_per_mwh
                        
                        # Add to total value
                        total_value += value
                        
                        # Track prices during working hours (when energy was produced)
                        if energy_kwh > 0:
                            working_hour_prices.append(price_per_mwh)
                            all_working_hour_prices.append(price_per_mwh)
                
                # Calculate total energy in MWh
                total_energy_mwh = total_energy_kwh / 1000
                
                # Calculate average price during working hours
                avg_working_hour_price = 0
                if working_hour_prices:
                    avg_working_hour_price = sum(working_hour_prices) / len(working_hour_prices)
                
                # Add to monthly data
                monthly_data[date_str] = {
                    "total_value": round(total_value, 2),
                    "total_energy_mwh": round(total_energy_mwh, 3),
                    "avg_working_hour_price": round(avg_working_hour_price, 2),
                    "working_hours": len(working_hour_prices)
                }
                
                # Add to monthly totals
                total_month_mwh += total_energy_mwh
                total_month_value += total_value
                
                days_with_data += 1
                logger.info(f"Added data for {date_str}: total_value = {round(total_value, 2)}, total_energy_mwh = {round(total_energy_mwh, 3)}")
                
            except Exception as e:
                logger.warning(f"Error processing {date_str}: {str(e)}")
                # Continue with next day instead of failing the whole request
                continue
        
        # Add summary information if the response is empty
        if not monthly_data:
            logger.warning(f"No data found for month {year_month}")
            return {
                "status": "no_data",
                "message": f"No data found for month {year_month}",
                "details": {
                    "days_processed": days_processed,
                    "days_with_data": days_with_data
                }
            }
        
        # Calculate average price across all working hours in the month
        month_avg_working_hour_price = 0
        if all_working_hour_prices:
            month_avg_working_hour_price = sum(all_working_hour_prices) / len(all_working_hour_prices)
        
        # Add monthly summary
        monthly_data["month_summary"] = {
            "total_value": round(total_month_value, 2),
            "total_energy_mwh": round(total_month_mwh, 3),
            "days_with_data": days_with_data,
            "avg_working_hour_price": round(month_avg_working_hour_price, 2),
            "total_working_hours": len(all_working_hour_prices)
        }
        
        logger.info(f"Monthly analysis complete for {year_month}: {days_with_data} days with data, {round(total_month_mwh, 3)} MWh produced")
        return monthly_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in monthly analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add web UI routes
@app.get("/ui", response_class=HTMLResponse)
async def ui_home(request: Request):
    """Home page for the web UI"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ui/daily", response_class=HTMLResponse)
async def ui_daily(request: Request):
    """Daily analysis page"""
    return templates.TemplateResponse("daily.html", {"request": request})

@app.get("/ui/monthly", response_class=HTMLResponse)
async def ui_monthly(request: Request):
    """Monthly analysis page"""
    return templates.TemplateResponse("monthly.html", {"request": request})

@app.get("/api/debug/energy-data")
async def debug_energy_data():
    """Debug endpoint to check energy data"""
    try:
        # Get all energy records
        energy_records = session.query(EnergyGeneration).all()
        
        # Group by date
        data_by_date = {}
        for record in energy_records:
            date_str = record.date.strftime('%Y-%m-%d')
            if date_str not in data_by_date:
                data_by_date[date_str] = []
            
            data_by_date[date_str].append({
                "hour": record.hour,
                "energy_kwh": record.energy_kwh
            })
        
        # Count working hours per date
        working_hours_by_date = {}
        for date_str, records in data_by_date.items():
            working_hours = sum(1 for r in records if r["energy_kwh"] > 0)
            working_hours_by_date[date_str] = working_hours
        
        return {
            "total_records": len(energy_records),
            "dates_with_data": len(data_by_date),
            "working_hours_by_date": working_hours_by_date,
            "sample_data": list(data_by_date.items())[:3] if data_by_date else []
        }
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/add-test-data")
async def add_test_data():
    """Add test energy data with production"""
    try:
        # Create a test date (today)
        test_date = datetime.now().date()
        
        # Add energy data for each hour
        for hour in range(1, 25):
            hour_str = f"H{hour}"
            
            # Add some production for daylight hours
            energy_kwh = 0
            if 8 <= hour <= 18:  # Between 8am and 6pm
                energy_kwh = hour * 10  # More production in middle of day
            
            # Check if record already exists
            existing = session.query(EnergyGeneration).filter_by(
                date=test_date, hour=hour_str
            ).first()
            
            if existing:
                # Update existing record
                existing.energy_kwh = energy_kwh
            else:
                # Create new record
                energy_record = EnergyGeneration(
                    date=test_date,
                    hour=hour_str,
                    energy_kwh=energy_kwh
                )
                session.add(energy_record)
        
        session.commit()
        return {"status": "success", "message": f"Added test data for {test_date}"}
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding test data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/check-data/{date}")
async def debug_check_data(date: str):
    """Debug endpoint to check both energy and price data for a date"""
    try:
        # Parse the date
        parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get energy data
        energy_records = session.query(EnergyGeneration).filter(
            EnergyGeneration.date == parsed_date
        ).all()
        
        # Get price data
        price_records = session.query(HourlyPrice).filter(
            HourlyPrice.date == parsed_date
        ).all()
        
        # Format the results
        energy_data = {r.hour: r.energy_kwh for r in energy_records}
        price_data = {r.hour: r.price for r in price_records}
        
        # Check for missing hours
        all_hours = set(energy_data.keys()) | set(price_data.keys())
        missing_energy = [h for h in all_hours if h not in energy_data]
        missing_prices = [h for h in all_hours if h not in price_data]
        
        return {
            "date": date,
            "energy_records_count": len(energy_records),
            "price_records_count": len(price_records),
            "energy_data": energy_data,
            "price_data": price_data,
            "missing_energy_hours": missing_energy,
            "missing_price_hours": missing_prices
        }
    except Exception as e:
        logger.error(f"Error in debug check: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/add-mar14-prices")
async def add_march14_prices():
    """Add specific price data for March 14, 2025"""
    try:
        # Set the date to March 14, 2025
        price_date = datetime(2025, 3, 14).date()
        
        # Price data from the screenshot
        price_data = {
            "H1": 109.09,
            "H2": 106.00,
            "H3": 105.90,
            "H4": 103.83,
            "H5": 105.30,
            "H6": 114.11,
            "H7": 143.08,
            "H8": 155.99,
            "H9": 163.69,
            "H10": 139.02,
            "H11": 119.00,
            "H12": 113.75,
            "H13": 109.82,
            "H14": 109.93,
            "H15": 112.88,
            "H16": 110.32,
            "H17": 126.56,
            "H18": 143.36,
            "H19": 153.20,
            "H20": 151.84,
            "H21": 130.01,
            "H22": 111.39,
            "H23": 114.00,
            "H24": 105.17
        }
        
        added_count = 0
        updated_count = 0
        
        # Add or update price records
        for hour, price in price_data.items():
            # Check if record already exists
            existing = session.query(HourlyPrice).filter_by(
                date=price_date, hour=hour
            ).first()
            
            if existing:
                # Update existing record
                existing.price = price
                updated_count += 1
            else:
                # Create new record
                price_record = HourlyPrice(
                    date=price_date,
                    hour=hour,
                    price=price
                )
                session.add(price_record)
                added_count += 1
        
        session.commit()
        return {
            "status": "success", 
            "message": f"Price data for 2025-03-14 added/updated successfully",
            "added": added_count,
            "updated": updated_count
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding March 14 prices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/test-energy-connection")
async def test_energy_connection():
    """Test connection to energy device and fetch data for multiple days"""
    try:
        device_ip = settings.ENERGY_DEVICE_IP
        tailscale_ip = getattr(settings, 'ENERGY_DEVICE_TAILSCALE_IP', None)
        results = {
            "device_ip": device_ip,
            "tailscale_ip": tailscale_ip,
            "current_ip": energy_service.current_ip,
            "device_url": f"http://{device_ip}/getjp",
            "tailscale_url": f"http://{tailscale_ip}/getjp" if tailscale_ip else None,
            "connection_tests": []
        }
        
        # Test connection for last 7 days
        for days_back in range(7):
            try:
                logger.info(f"Testing energy device connection for {days_back} days ago...")
                hourly_data, total_kwh = energy_service.get_hourly_data(days_back)
                
                if hourly_data is None:
                    results["connection_tests"].append({
                        "days_back": days_back,
                        "status": "error",
                        "message": "Connection failed or timeout"
                    })
                elif not hourly_data:
                    results["connection_tests"].append({
                        "days_back": days_back,
                        "status": "no_data",
                        "message": "Device returned empty data",
                        "total_kwh": 0
                    })
                else:
                    results["connection_tests"].append({
                        "days_back": days_back,
                        "status": "success",
                        "total_kwh": total_kwh,
                        "hours_with_data": len(hourly_data)
                    })
            except Exception as e:
                results["connection_tests"].append({
                    "days_back": days_back,
                    "status": "error",
                    "message": str(e)
                })
        
        return results
    except Exception as e:
        logger.error(f"Error testing energy connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/test-network-connectivity")
async def test_network_connectivity():
    """Test network connectivity to both local and Tailscale IPs"""
    import socket
    import time
    
    device_ip = settings.ENERGY_DEVICE_IP
    tailscale_ip = getattr(settings, 'ENERGY_DEVICE_TAILSCALE_IP', None)
    
    results = {
        "local_ip": device_ip,
        "tailscale_ip": tailscale_ip,
        "tests": {}
    }
    
    def test_ip_connectivity(ip, port=80):
        """Test if we can connect to an IP on a specific port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception as e:
            return False, str(e)
    
    def test_http_response(ip):
        """Test if we can get an HTTP response from the device"""
        try:
            url = f"http://{ip}/"
            response = requests.get(url, timeout=10)
            return {
                "success": True,
                "status_code": response.status_code,
                "response_size": len(response.content)
            }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Timeout"}
        except requests.exceptions.ConnectionError as e:
            return {"success": False, "error": f"Connection error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Test local IP
    logger.info(f"Testing connectivity to local IP: {device_ip}")
    results["tests"]["local_ip"] = {
        "ip": device_ip,
        "port_80_open": test_ip_connectivity(device_ip, 80),
        "http_response": test_http_response(device_ip)
    }
    
    # Test Tailscale IP if available
    if tailscale_ip:
        logger.info(f"Testing connectivity to Tailscale IP: {tailscale_ip}")
        results["tests"]["tailscale_ip"] = {
            "ip": tailscale_ip,
            "port_80_open": test_ip_connectivity(tailscale_ip, 80),
            "http_response": test_http_response(tailscale_ip)
        }
    else:
        results["tests"]["tailscale_ip"] = {
            "ip": None,
            "message": "Tailscale IP not configured"
        }
    
    # Determine which IP to recommend
    local_works = results["tests"]["local_ip"]["http_response"]["success"]
    tailscale_works = results["tests"].get("tailscale_ip", {}).get("http_response", {}).get("success", False)
    
    if tailscale_works and not local_works:
        results["recommendation"] = "Use Tailscale IP - local IP not accessible"
    elif local_works and not tailscale_works:
        results["recommendation"] = "Use local IP - Tailscale IP not accessible"
    elif local_works and tailscale_works:
        results["recommendation"] = "Both IPs work - prefer local IP for speed"
    else:
        results["recommendation"] = "Neither IP is accessible - check network/Tailscale connection"
    
    return results

@app.get("/api/debug/fetch-today-data")
async def fetch_today_data():
    """Force fetch both price and energy data for today"""
    today = datetime.now().date().strftime("%Y-%m-%d")
    
    try:
        # 1. Force update price cache
        logger.info("Forcing price cache update...")
        await update_price_cache()
        
        # 2. Fetch energy data for today (days_back = 0)
        logger.info("Fetching today's energy data...")
        energy_success = energy_service.save_data_to_db(0)
        
        # 3. Check what we have in the database now
        date_obj = datetime.now().date()
        price_records = session.query(HourlyPrice).filter(
            HourlyPrice.date == date_obj
        ).count()
        
        energy_records = session.query(EnergyGeneration).filter(
            EnergyGeneration.date == date_obj
        ).count()
        
        return {
            "status": "success",
            "date": today,
            "price_records_count": price_records,
            "energy_records_count": energy_records,
            "message": f"Data fetch attempted for {today}"
        }
        
    except Exception as e:
        logger.error(f"Error fetching today's data: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/api/debug/add-april-data")
async def add_april_data():
    """Add test data for April 1st, 2025"""
    try:
        session.rollback()  # Ensure clean transaction state
        
        # Create date object for April 1st, 2025
        test_date = datetime(2025, 4, 1).date()
        
        # First add price data for the day
        for hour in range(1, 25):
            hour_key = f"H{hour}"
            # Check if record exists
            existing = session.query(HourlyPrice).filter_by(
                date=test_date, hour=hour_key
            ).first()
            
            if not existing:
                # Mock price that varies by hour 
                price = 70 + (hour * 2)
                price_record = HourlyPrice(
                    date=test_date,
                    hour=hour_key,
                    price=price
                )
                session.add(price_record)
        
        # Then add energy data
        for hour in range(1, 25):
            hour_key = f"H{hour}"
            # Skip night hours, add energy during daylight
            energy = 0
            if 6 <= hour <= 20:
                energy = 10 + (hour * 3) if hour <= 13 else 50 - (hour * 1.5)
            
            # Check if record exists
            existing = session.query(EnergyGeneration).filter_by(
                date=test_date, hour=hour_key
            ).first()
            
            if not existing:
                energy_record = EnergyGeneration(
                    date=test_date,
                    hour=hour_key,
                    energy_kwh=energy
                )
                session.add(energy_record)
        
        session.commit()
        return {"status": "success", "message": "April 1st test data added successfully"}
        
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}