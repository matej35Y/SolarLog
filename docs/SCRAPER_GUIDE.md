# Scraper Guide - Adding New Price Data Sources

This guide explains how to add support for scraping prices from different websites.

## Architecture Overview

The scraper system uses a flexible architecture:

1. **BasePriceScraper**: Abstract base class that defines the interface all scrapers must implement
2. **ScraperFactory**: Manages and creates scraper instances
3. **Individual Scrapers**: Concrete implementations for specific websites (e.g., HUPXScraper)

## How to Add a New Scraper

### Step 1: Create Your Scraper Class

Create a new class that inherits from `BasePriceScraper` in `app/scraper.py`:

```python
class MyCustomScraper(BasePriceScraper):
    """Scraper for MyCustomWebsite"""
    
    def __init__(self):
        super().__init__("MyCustomScraper")
        # Initialize your scraper-specific settings
        self.api_url = "https://example.com/api/prices"
        self.headers = {
            'User-Agent': 'Mozilla/5.0...',
            'Accept': 'application/json'
        }
    
    def scrape_prices(self, target_date: Optional[str] = None, days_back: int = 0) -> List[Dict]:
        """
        Implement your scraping logic here.
        
        Must return a list of dictionaries with this format:
        [
            {
                'date': 'YYYY-MM-DD',
                'hour': 'H1', 'H2', ..., 'H24',
                'price': float,
                'volume': float (optional),
                'status': str (optional)
            },
            ...
        ]
        """
        try:
            # Determine the date to scrape
            if target_date:
                scrape_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                scrape_date = datetime.now().date() - timedelta(days=days_back)
            
            date_str = scrape_date.strftime('%Y-%m-%d')
            self.logger.info(f"Scraping from {self.name} for date: {date_str}")
            
            # YOUR SCRAPING LOGIC HERE
            # Example: Make API request
            response = requests.get(
                f"{self.api_url}?date={date_str}",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse and format the data
            formatted_data = []
            for record in data:
                formatted_record = {
                    'date': date_str,
                    'hour': f"H{record['hour']}",  # Ensure format is H1, H2, ..., H24
                    'price': float(record['price']),
                    'volume': float(record.get('volume', 0)),  # Optional
                    'status': record.get('status', 'unknown')  # Optional
                }
                formatted_data.append(formatted_record)
            
            # Save to database (inherited method)
            if formatted_data:
                self.save_to_db(formatted_data)
            
            return formatted_data
            
        except Exception as e:
            self.logger.error(f"Error scraping data: {str(e)}")
            return []
```

### Step 2: Register Your Scraper

Add your scraper to the factory in `app/scraper_factory.py`:

```python
from .scraper import BasePriceScraper, HUPXScraper, ExampleScraper, MyCustomScraper

class ScraperFactory:
    _scrapers: Dict[str, Type[BasePriceScraper]] = {
        'hupx': HUPXScraper,
        'example': ExampleScraper,
        'my_custom': MyCustomScraper,  # Add your scraper here
    }
    # ... rest of the factory code
```

### Step 3: Configure Your Scraper

Update your `.env` file or `app/config.py`:

```bash
# In .env file
SCRAPER_NAME=my_custom
```

Or set it in `app/config.py`:

```python
SCRAPER_NAME: str = "my_custom"  # Change from "hupx" to your scraper name
```

### Step 4: Restart the Application

Restart your FastAPI application to use the new scraper:

```bash
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### List Available Scrapers

```bash
GET /api/scrapers
```

Returns:
```json
{
  "available_scrapers": {
    "hupx": "HUPXScraper",
    "example": "ExampleScraper",
    "my_custom": "MyCustomScraper"
  },
  "current_scraper": "hupx",
  "current_scraper_name": "HUPXScraper"
}
```

### Check Scraper Availability

```bash
GET /api/scrapers/switch/{scraper_name}
```

Validates that a scraper exists and can be used.

## Data Format Requirements

Your scraper's `scrape_prices()` method must return a list of dictionaries with this structure:

```python
[
    {
        'date': '2025-01-15',      # Required: YYYY-MM-DD format
        'hour': 'H1',              # Required: H1, H2, ..., H24
        'price': 123.45,            # Required: float
        'volume': 1000.0,           # Optional: float
        'status': 'active'          # Optional: string
    },
    # ... more records
]
```

**Important Notes:**
- `date` must be in `YYYY-MM-DD` format
- `hour` must be in format `H1`, `H2`, ..., `H24` (24-hour format)
- `price` is required and must be a float
- `volume` and `status` are optional
- The `save_to_db()` method (inherited from `BasePriceScraper`) will automatically handle database storage and prevent duplicates

## Example: Web Scraping with BeautifulSoup

If you need to scrape HTML instead of an API:

```python
from bs4 import BeautifulSoup

class HTMLScraper(BasePriceScraper):
    def __init__(self):
        super().__init__("HTMLScraper")
        self.base_url = "https://example.com/prices"
    
    def scrape_prices(self, target_date: Optional[str] = None, days_back: int = 0) -> List[Dict]:
        try:
            # Determine date
            if target_date:
                scrape_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                scrape_date = datetime.now().date() - timedelta(days=days_back)
            
            date_str = scrape_date.strftime('%Y-%m-%d')
            
            # Fetch HTML
            response = requests.get(f"{self.base_url}?date={date_str}")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse HTML table
            formatted_data = []
            table = soup.find('table', {'id': 'prices'})
            rows = table.find_all('tr')[1:]  # Skip header
            
            for row in rows:
                cells = row.find_all('td')
                hour = int(cells[0].text)
                price = float(cells[1].text)
                
                formatted_data.append({
                    'date': date_str,
                    'hour': f"H{hour}",
                    'price': price
                })
            
            if formatted_data:
                self.save_to_db(formatted_data)
            
            return formatted_data
            
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            return []
```

## Example: Selenium for Dynamic Content

If the website uses JavaScript to load data:

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class SeleniumScraper(BasePriceScraper):
    def __init__(self):
        super().__init__("SeleniumScraper")
        self.url = "https://example.com/dynamic-prices"
    
    def scrape_prices(self, target_date: Optional[str] = None, days_back: int = 0) -> List[Dict]:
        try:
            # Setup Selenium
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            driver = webdriver.Chrome(options=options)
            
            # Navigate and wait for content
            driver.get(self.url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "price-table"))
            )
            
            # Extract data
            formatted_data = []
            # ... your extraction logic ...
            
            driver.quit()
            
            if formatted_data:
                self.save_to_db(formatted_data)
            
            return formatted_data
            
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            return []
```

## Testing Your Scraper

Test your scraper directly:

```python
from app.scraper_factory import ScraperFactory

# Get your scraper
scraper = ScraperFactory.get_scraper('my_custom')

# Test scraping today's data
data = scraper.scrape_prices()
print(f"Scraped {len(data)} records")

# Test scraping a specific date
data = scraper.scrape_prices(target_date='2025-01-15')
print(f"Scraped {len(data)} records for 2025-01-15")
```

## Troubleshooting

1. **Scraper not found**: Make sure you registered it in `ScraperFactory._scrapers`
2. **Wrong data format**: Ensure your data matches the required format (date, hour, price)
3. **Database errors**: Check that `save_to_db()` is being called correctly
4. **Import errors**: Make sure your scraper class is imported in `scraper_factory.py`

## Current Scrapers

- **hupx**: HUPX Labs API scraper (default)
- **example**: Template scraper for reference

Add your own scrapers following the same pattern!
