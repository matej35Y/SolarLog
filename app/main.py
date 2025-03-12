from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_utils.tasks import repeat_every
from datetime import datetime, timedelta
import logging
from typing import Optional, List
import calendar
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .scraper import HUPXScraper
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

scraper = HUPXScraper()

# Initialize the energy service
energy_service = EnergyDataService()

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
        
        # 2. Update energy data for recent days (today and yesterday)
        logger.info("Updating energy data for recent days...")
        for days_back in range(2):  # Update today and yesterday
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
        "last_update": price_cache["last_updated"]
    }


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
async def get_prices_by_date(date: str):
    """Get prices for a specific date (format: YYYY-MM-DD)"""
    if not price_cache["data"]:
        raise HTTPException(status_code=503, detail="Price data not available")

    try:
        # Filter prices for the specified date
        prices = [
            price for price in price_cache["data"]
            if price["date"] == date
        ]

        if not prices:
            raise HTTPException(status_code=404, detail=f"No prices found for date {date}")

        return {
            "date": date,
            "prices": prices
        }
    except Exception as e:
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


@app.get("/api/energy/fetch/{days_back}")
async def fetch_energy_data(days_back: int):
    """Fetch and store energy data for a specific day in the past"""
    success = energy_service.save_data_to_db(days_back)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to fetch energy data")
    
    return {"status": "success", "message": f"Energy data for {days_back} days ago fetched and stored"}


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/by-date/{date}")
async def get_price_energy_analysis(date: str):
    """Get combined price and energy analysis for a specific date"""
    try:
        # Parse the date string to ensure correct format
        try:
            parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD")
        
        # Calculate days_back for energy data
        days_back = (datetime.now().date() - parsed_date).days
        if days_back < 0:
            raise HTTPException(status_code=400, detail="Cannot analyze future dates")
        
        # 1. Always refresh price data first
        logger.info(f"Refreshing price data for analysis of {date}")
        try:
            await update_price_cache()
            logger.info("Price data refreshed successfully")
        except Exception as e:
            logger.warning(f"Failed to refresh price data: {str(e)}")
        
        # 2. Always fetch energy data for the requested date
        logger.info(f"Ensuring energy data is available for {date}")
        try:
            energy_service.save_data_to_db(days_back)
            logger.info(f"Energy data for {date} is now up-to-date")
        except Exception as e:
            logger.warning(f"Failed to fetch energy data: {str(e)}")
        
        # 3. Get energy data from database
        energy_records = session.query(EnergyGeneration).filter(
            EnergyGeneration.date == parsed_date
        ).all()
        
        if not energy_records:
            raise HTTPException(status_code=404, detail=f"Energy data not available for date {date}")
        
        # 4. Get price data (first from database, then from cache if needed)
        price_records = session.query(HourlyPrice).filter(
            HourlyPrice.date == parsed_date
        ).all()
        
        if not price_records:
            # Check if we have price data in the cache
            if price_cache["data"]:
                cached_prices = [p for p in price_cache["data"] if p["date"] == date]
                if cached_prices:
                    # Create temporary price records from cache
                    price_records = []
                    for p in cached_prices:
                        price_obj = HourlyPrice(
                            date=parsed_date,
                            hour=p["hour"],
                            price=p["price"]
                        )
                        price_records.append(price_obj)
            
            if not price_records:
                raise HTTPException(status_code=404, detail=f"Price data not available for date {date}")
        
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
        
        for hour in sorted_hours:
            energy_kwh = energy_by_hour.get(hour, 0)
            price_per_mwh = price_by_hour.get(hour, 0)
            
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
        
        return {
            "date": date,
            "hourly_data": analysis_data,
            "summary": {
                "total_energy_kwh": round(total_energy, 3),
                "total_energy_mwh": round(total_energy_mwh, 3),
                "total_value": round(total_value, 2),
                "average_price_per_mwh": round(total_value / total_energy_mwh if total_energy_mwh > 0 else 0, 2),
                "arithmetic_avg_price_per_mwh": round(arithmetic_avg_price, 2)
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
async def get_monthly_analysis(year_month: str):
    """Get total_value for all days in a month (format: YYYY-MM)"""
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
        
        logger.info(f"Processing monthly analysis for {year_month}")
        
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
                
                # Get price data
                price_records = session.query(HourlyPrice).filter(
                    HourlyPrice.date == date_obj
                ).all()
                
                if not price_records:
                    logger.info(f"No price data for {date_str}")
                    continue
                
                logger.info(f"Found data for {date_str}: {len(energy_records)} energy records, {len(price_records)} price records")
                
                # Create mappings for easier access
                energy_by_hour = {r.hour: r.energy_kwh for r in energy_records}
                price_by_hour = {r.hour: r.price for r in price_records}
                
                # Calculate total value and energy
                total_value = 0
                total_energy_kwh = 0
                working_hour_prices = []
                
                # Get all hours from both datasets
                all_hours = set(energy_by_hour.keys()) & set(price_by_hour.keys())
                
                if not all_hours:
                    logger.info(f"No matching hours between energy and price data for {date_str}")
                    continue
                
                for hour in all_hours:
                    energy_kwh = energy_by_hour.get(hour, 0)
                    price_per_mwh = price_by_hour.get(hour, 0)
                    
                    # Add to total energy
                    total_energy_kwh += energy_kwh
                    
                    # Convert kWh to MWh for calculation
                    energy_mwh = energy_kwh / 1000
                    
                    # Add to total value
                    total_value += energy_mwh * price_per_mwh
                    
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