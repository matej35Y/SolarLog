import requests
from datetime import datetime, timedelta
import logging
import json
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
from app.models.database import HourlyPrice, session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BasePriceScraper(ABC):
    """Base class for all price scrapers. All scrapers must implement this interface."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def scrape_prices(self, target_date: Optional[str] = None, days_back: int = 0) -> List[Dict]:
        """
        Scrape price data for a specific date or days back from today.
        
        Args:
            target_date: Date in format 'YYYY-MM-DD'. If None, uses days_back.
            days_back: Number of days back from today to scrape (default: 0 = today)
        
        Returns:
            List of dictionaries with format:
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
        pass
    
    def scrape_multiple_dates(self, start_date: str, end_date: Optional[str] = None, days_count: Optional[int] = None) -> List[Dict]:
        """
        Scrape data for multiple dates.
        
        Args:
            start_date: Start date in format 'YYYY-MM-DD'
            end_date: End date in format 'YYYY-MM-DD' (optional)
            days_count: Number of days to scrape from start_date (optional)
        
        Returns:
            List of all scraped records
        """
        try:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            if end_date:
                if isinstance(end_date, str):
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
            elif days_count:
                dates = [start_date + timedelta(days=i) for i in range(days_count)]
            else:
                dates = [start_date]
            
            all_data = []
            for date in dates:
                date_str = date.strftime('%Y-%m-%d')
                self.logger.info(f"Scraping data for {date_str}")
                data = self.scrape_prices(target_date=date_str)
                all_data.extend(data)
            
            self.logger.info(f"Scraped total of {len(all_data)} records for {len(dates)} dates")
            return all_data
            
        except Exception as e:
            self.logger.error(f"Error scraping multiple dates: {str(e)}")
            return []
    
    def save_to_db(self, data: List[Dict]) -> None:
        """
        Save scraped data to the database.
        Prevents duplicate entries by checking existing records.
        
        Args:
            data: List of dictionaries with price data
        """
        try:
            session.rollback()  # First rollback any failed transaction
            
            saved_count = 0
            skipped_count = 0
            
            for record in data:
                # Skip records with missing prices
                if record.get('price', 0) is None:
                    self.logger.debug(f"Skipping record for {record.get('hour', 'unknown')} on {record.get('date', 'unknown')} due to missing price")
                    skipped_count += 1
                    continue
                    
                # Convert date string to a date object
                try:
                    date_obj = datetime.strptime(record['date'], '%Y-%m-%d').date()
                except ValueError:
                    self.logger.warning(f"Could not parse date: {record['date']}")
                    skipped_count += 1
                    continue
                
                # Get source from record, default to scraper name (lowercase)
                source = record.get('source', self.name.lower().replace('scraper', ''))
                
                # Check if the record already exists (including source)
                existing_record = session.query(HourlyPrice).filter_by(
                    date=date_obj, 
                    hour=record['hour'],
                    source=source
                ).first()
                
                if existing_record is None:
                    # Create a new HourlyPrice object
                    price_record = HourlyPrice(
                        date=date_obj,
                        hour=record['hour'],
                        price=record['price'],
                        source=source
                    )
                    session.add(price_record)
                    saved_count += 1
                else:
                    # Overwrite existing record if it had a 0 price and the new price is valid
                    if existing_record.price == 0.0 and record['price'] > 0:
                        existing_record.price = record['price']
                        self.logger.info(f"Updated 0-price record for {record['hour']} on {record['date']} from {source} with new price {record['price']}.")
                        saved_count += 1
                    else:
                        self.logger.debug(f"Record for {record['hour']} on {record['date']} from {source} already exists. Skipping.")
                        skipped_count += 1

            # Commit the session to save data
            session.commit()
            self.logger.info(f"Data saved to database: {saved_count} inserted/updated records, {skipped_count} skipped")
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error in save_to_db: {str(e)}")
            raise


class HUPXScraper(BasePriceScraper):
    """Scraper for HUPX Labs API (https://labs.hupx.hu)"""
    
    def __init__(self):
        super().__init__("HUPXScraper")
        self.api_url = "https://labs.hupx.hu/data/v1/dam_aggregated_trading_data"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json'
        }

    def scrape_prices(self, target_date: Optional[str] = None, days_back: int = 0) -> List[Dict]:
        """Scrape real data from HUPX Labs API"""
        try:
            # Determine the date to scrape
            if target_date:
                scrape_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                scrape_date = datetime.now().date() - timedelta(days=days_back)
            
            date_str = scrape_date.strftime('%Y-%m-%d')
            self.logger.info(f"Scraping HUPX data for date: {date_str}")
            
            # Build API URL with date filter
            api_url = f"{self.api_url}?filter=DeliveryDay__gte__{date_str},DeliveryDay__lte__{date_str}"
            self.logger.debug(f"API URL: {api_url}")
            
            # Make API request
            response = requests.get(api_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            self.logger.info(f"Successfully accessed HUPX API. Status: {response.status_code}")
            
            # Parse JSON response
            data = response.json()
            
            if data.get('message') != 'Success' or not data.get('data'):
                self.logger.warning(f"No data found for date {date_str}")
                return []
            
            # Extract and format the data
            raw_data = data['data']
            self.logger.info(f"Retrieved {len(raw_data)} records from API")
            
            # Convert API data to our format
            formatted_data = []
            for record in raw_data:
                try:
                    # Parse delivery day
                    delivery_day = record['DeliveryDay'][:10]  # Extract YYYY-MM-DD from ISO format
                    
                    # Parse hour (ProductH is the hour number)
                    hour_num = int(record['ProductH'])
                    hour = f"H{hour_num}"
                    
                    # Get price and volume
                    price = float(record['Price'])
                    volume = float(record['Volume']) if record.get('Volume') else None
                    status = record.get('Status', 'unknown')
                    
                    formatted_record = {
                        'date': delivery_day,
                        'hour': hour,
                        'price': price,
                        'volume': volume,
                        'status': status,
                        'source': 'hupx'  # Mark as HUPX data
                    }
                    
                    formatted_data.append(formatted_record)
                    self.logger.debug(f"Formatted record: {formatted_record}")
                    
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Error parsing record {record}: {str(e)}")
                    continue
            
            self.logger.info(f"Successfully formatted {len(formatted_data)} records")
            
            # Save to database
            if formatted_data:
                self.save_to_db(formatted_data)
                self.logger.info("Data saved to database successfully")
            
            return formatted_data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error making API request: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON response: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error scraping HUPX data: {str(e)}")
            return []


class MEMOScraper(BasePriceScraper):
    """Scraper for MEMO Day-Ahead Market (https://dam.memo.mk/)"""
    
    def __init__(self):
        super().__init__("MEMOScraper")
        self.base_url = "https://dam-data.memo.mk"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://dam-data.memo.mk',
            'Referer': 'https://dam-data.memo.mk/index.php?action=auction-by-hour&lang=en'
        }
    
    def scrape_prices(self, target_date: Optional[str] = None, days_back: int = 0) -> List[Dict]:
        """Scrape hourly prices from MEMO website (dam-data.memo.mk)"""
        try:
            # Determine the date to scrape
            if target_date:
                scrape_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                scrape_date = datetime.now().date() - timedelta(days=days_back)
            
            date_str = scrape_date.strftime('%Y-%m-%d')
            self.logger.info(f"Scraping MEMO data for date: {date_str}")
            
            # The new target page handles 7-day windows. We'll request the specific date.
            return self._scrape_from_html(date_str, scrape_date)
            
        except Exception as e:
            self.logger.error(f"Error scraping MEMO data: {str(e)}")
            return []
    
    def _download_excel_file(self, date_str: str, scrape_date: datetime.date) -> List[Dict]:
        """Download and parse Excel file from MEMO results page"""
        try:
            # Build Excel file URL
            # Pattern: https://dam.memo.mk/wp-content/uploads/{year}/{month}/MarketResult_MKD_{YYYYMMDD}_EURO.xlsx
            year = scrape_date.year
            month = f"{scrape_date.month:02d}"
            date_file_str = scrape_date.strftime('%Y%m%d')
            
            excel_url = f"{self.base_url}/wp-content/uploads/{year}/{month}/MarketResult_MKD_{date_file_str}_EURO.xlsx"
            self.logger.info(f"Attempting to download Excel file: {excel_url}")
            
            # Download the file
            response = requests.get(excel_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                self.logger.info(f"Successfully downloaded Excel file for {date_str}")
                return self._parse_excel_file(response.content, date_str)
            else:
                self.logger.warning(f"Excel file not found at {excel_url} (Status: {response.status_code})")
                # Try alternative URL patterns
                return self._try_alternative_excel_urls(date_str, scrape_date)
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Error downloading Excel file: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error processing Excel file: {str(e)}")
            return []
    
    def _try_alternative_excel_urls(self, date_str: str, scrape_date: datetime.date) -> List[Dict]:
        """Try alternative URL patterns for Excel files"""
        year = scrape_date.year
        month = f"{scrape_date.month:02d}"
        date_file_str = scrape_date.strftime('%Y%m%d')
        
        # Calculate previous month/year for alternative paths
        prev_month_date = scrape_date.replace(day=1) - timedelta(days=1)
        prev_month = prev_month_date.month
        prev_year = prev_month_date.year
        
        # Try different month formats and paths - expanded list for better coverage
        alternative_urls = [
            # Standard patterns
            f"{self.base_url}/wp-content/uploads/{year}/{month:02d}/MarketResult_MKD_{date_file_str}_EURO.xlsx",
            f"{self.base_url}/wp-content/uploads/{year}/{month}/MarketResult_MKD_{date_file_str}_EURO.xlsx",
            f"{self.base_url}/wp-content/uploads/MarketResult_MKD_{date_file_str}_EURO.xlsx",
            # Try without EURO suffix
            f"{self.base_url}/wp-content/uploads/{year}/{month:02d}/MarketResult_MKD_{date_file_str}.xlsx",
            f"{self.base_url}/wp-content/uploads/{year}/{month}/MarketResult_MKD_{date_file_str}.xlsx",
            # Try different date formats
            f"{self.base_url}/wp-content/uploads/{year}/{month:02d}/MarketResult_{date_file_str}_EURO.xlsx",
            f"{self.base_url}/wp-content/uploads/{year}/{month}/MarketResult_{date_file_str}_EURO.xlsx",
            # Try root directory
            f"{self.base_url}/MarketResult_MKD_{date_file_str}_EURO.xlsx",
            f"{self.base_url}/MarketResult_{date_file_str}_EURO.xlsx",
            # Try with lowercase
            f"{self.base_url}/wp-content/uploads/{year}/{month:02d}/marketresult_mkd_{date_file_str}_euro.xlsx",
            # Try previous month (in case files are stored in previous month's folder)
            f"{self.base_url}/wp-content/uploads/{prev_year}/{prev_month:02d}/MarketResult_MKD_{date_file_str}_EURO.xlsx",
        ]
        
        for url in alternative_urls:
            try:
                self.logger.info(f"Trying alternative URL: {url}")
                response = requests.get(url, headers=self.headers, timeout=15)
                if response.status_code == 200:
                    self.logger.info(f"Found Excel file at alternative URL: {url}")
                    return self._parse_excel_file(response.content, date_str)
                else:
                    self.logger.debug(f"URL returned status {response.status_code}: {url}")
            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout trying URL: {url}")
                continue
            except requests.exceptions.RequestException as e:
                self.logger.debug(f"Request error for {url}: {str(e)}")
                continue
            except Exception as e:
                self.logger.debug(f"Error trying {url}: {str(e)}")
                continue
        
        self.logger.warning(f"Could not find Excel file for {date_str} after trying {len(alternative_urls)} URL patterns")
        return []
    
    def _parse_excel_file(self, excel_content: bytes, date_str: str) -> List[Dict]:
        """Parse Excel file and extract hourly prices"""
        try:
            excel_file = BytesIO(excel_content)
            
            # Read the "Delivery Date" sheet
            df = pd.read_excel(excel_file, sheet_name='Delivery Date ')
            
            # Find the header row (contains "Period" and "MCP (EURO)")
            header_row_idx = None
            for i in range(min(10, len(df))):
                row_values = ' '.join([str(v) for v in df.iloc[i].values if pd.notna(v)])
                if 'Period' in row_values and 'MCP' in row_values and 'EURO' in row_values:
                    header_row_idx = i
                    break
            
            if header_row_idx is None:
                self.logger.error("Could not find header row in Excel file")
                return []
            
            # Extract data starting from the row after header
            data_start_idx = header_row_idx + 1
            formatted_data = []
            
            # Process rows until we hit the baseload summary or end
            for i in range(data_start_idx, min(data_start_idx + 25, len(df))):
                row = df.iloc[i]
                
                # Get period (e.g., "00 - 01") and price
                period = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                price = row.iloc[1] if pd.notna(row.iloc[1]) else None
                
                # Skip summary rows (contain "Baseload" or similar)
                if 'baseload' in period.lower() or 'peak' in period.lower() or not period:
                    continue
                
                # Parse period to get hour number (e.g., "00 - 01" -> hour 1, "23 - 00" -> hour 24)
                hour_match = re.match(r'(\d{2})\s*-\s*(\d{2})', period)
                if hour_match:
                    start_hour = int(hour_match.group(1))
                    end_hour = int(hour_match.group(2))
                    
                    # Handle wrap-around: "23 - 00" means hour 24
                    if start_hour == 23 and end_hour == 0:
                        hour_num = 24
                    else:
                        # Hour 1 corresponds to period 00-01, Hour 2 to 01-02, etc.
                        hour_num = start_hour + 1
                    
                    if price is not None:
                        try:
                            price_float = float(price)
                            formatted_data.append({
                                'date': date_str,
                                'hour': f"H{hour_num}",
                                'price': price_float,
                                'source': 'memo'
                            })
                        except (ValueError, TypeError):
                            self.logger.warning(f"Could not parse price for period {period}: {price}")
                            continue
            
            if formatted_data:
                self.save_to_db(formatted_data)
                self.logger.info(f"Successfully parsed {len(formatted_data)} hourly prices from Excel file")
            
            return formatted_data
            
        except Exception as e:
            self.logger.error(f"Error parsing Excel file: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []
    
    def _parse_api_response(self, data: Dict, date_str: str) -> List[Dict]:
        """Parse API JSON response"""
        formatted_data = []
        # Adjust based on actual API structure
        for record in data.get('data', []):
            try:
                hour = f"H{record.get('hour', 0)}"
                price = float(record.get('price', 0))
                formatted_data.append({
                    'date': date_str,
                    'hour': hour,
                    'price': price,
                    'source': 'memo'
                })
            except (ValueError, KeyError) as e:
                self.logger.warning(f"Error parsing API record: {e}")
                continue
        return formatted_data
    
    def _scrape_from_html(self, date_str: str, scrape_date: datetime.date) -> List[Dict]:
        """Scrape prices from HTML page at dam-data.memo.mk"""
        try:
            url = f"{self.base_url}/index.php?action=auction-by-hour&lang=en"
            
            # Prepare POST data to select the date
            # The site uses a form with id="formAuctionByHourDataTables"
            # Date format expected by input[type=date] is YYYY-MM-DD
            payload = {
                'date': date_str,
                'submit': 'Search'
            }
            
            self.logger.info(f"Requesting data for {date_str} from {url}")
            response = requests.post(url, headers=self.headers, data=payload, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # There are usually 3 tables: Base Load, Peak Load, and HOURS.
            # The HOURS table usually comes last or has specific headers.
            tables = soup.find_all('table')
            if not tables:
                self.logger.warning("No tables found in response")
                return []
            
            # Find the table that contains "HOURS" or "HOUR" in headers (English version)
            hour_table = None
            for table in tables:
                header_text = table.get_text().lower()
                if 'hours' in header_text and ('mwh' in header_text or 'mkd' in header_text or '€' in header_text):
                    hour_table = table
                    break
            
            if not hour_table:
                # Fallback: the 3rd table is typically the hourly one
                if len(tables) >= 3:
                    hour_table = tables[2]
                else:
                    self.logger.warning("Could not identify the hourly data table")
                    return []
            
            # Parse the header row to find which column matches our date
            # The table has multiple dates across columns (usually 7 days)
            header_row = hour_table.find('tr')
            if not header_row:
                self.logger.warning("Hourly table has no header row")
                return []
            
            header_cells = [td.get_text().strip() for td in header_row.find_all(['th', 'td'])]
            
            # MEMO usually displays dates like "DD.MM.YYYY" or similar in this view.
            # Let's check for the date format.
            date_col_idx = -1
            target_formats = [
                scrape_date.strftime('%d.%m.%Y'),
                scrape_date.strftime('%d.%m.%y'),
                scrape_date.strftime('%Y-%m-%d'),
            ]
            
            for i, cell in enumerate(header_cells):
                for fmt in target_formats:
                    if fmt in cell:
                        date_col_idx = i
                        break
                if date_col_idx != -1:
                    break
            
            if date_col_idx == -1:
                self.logger.warning(f"Could not find column for date {date_str} in table headers: {header_cells}")
                # Sometimes it only shows the week starting from the selected date.
                # If we requested specifically for this date, it might be the first data column (idx 2, as 0=Hour, 1=Unit)
                if len(header_cells) > 2:
                    date_col_idx = 2
                    self.logger.info(f"Defaulting to column index {date_col_idx} as no explicit date match found")
                else:
                    return []
            
            formatted_data = []
            rows = hour_table.find_all('tr')[1:]  # Skip header
            
            current_hour_label = ""
            for i in range(0, len(rows)):
                row = rows[i]
                cells = [td.get_text().strip() for td in row.find_all(['th', 'td'])]
                
                if len(cells) <= date_col_idx:
                    continue
                
                # Column 0: Period (e.g. 00-01), Column 1: Unit (€/MWh or MWh)
                hour_range = cells[0].strip()
                unit = cells[1].strip()
                
                # The data alternates: one row for Price (€/MWh), one row for Quantity (MWh)
                # We only want Price.
                if '€' in unit or 'Price' in unit or 'MKD' in unit:
                    # Hour range parsing: "00 - 01" -> H1, ..., "23 - 00" -> H24
                    hour_match = re.match(r'(\d{2})\s*-\s*(\d{2})', hour_range)
                    if hour_match:
                        start_h = int(hour_match.group(1))
                        # H1 is 00-01, H2 is 01-02... H24 is 23-00
                        hour_num = start_h + 1
                        
                        price_str = cells[date_col_idx].replace(',', '').replace(' ', '')
                        try:
                            # In English version, decimals might be points. 
                            # But MEMO often uses commas for decimals regardless.
                            # If it contains a comma, replace it with a point.
                            if ',' in cells[date_col_idx]:
                                price_str = cells[date_col_idx].replace('.', '').replace(',', '.')
                            
                            price = float(price_str)
                            formatted_data.append({
                                'date': date_str,
                                'hour': f"H{hour_num}",
                                'price': price,
                                'source': 'memo'
                            })
                        except (ValueError, TypeError) as e:
                            self.logger.warning(f"Could not parse price '{price_str}' for hour {hour_num}: {e}")
                            continue
            
            if formatted_data:
                self.save_to_db(formatted_data)
                self.logger.info(f"Successfully scraped {len(formatted_data)} hourly prices from dam-data.memo.mk")
            
            return formatted_data
            
        except Exception as e:
            self.logger.error(f"Error scraping from HTML: {str(e)}")
            return []
    
    def _distribute_base_peak_prices(self, date_str: str, base_price: float, peak_price: float) -> List[Dict]:
        """
        Distribute base and peak prices across 24 hours.
        Peak hours: 8-20 (H8-H20)
        Base hours: 1-7, 21-24 (H1-H7, H21-H24)
        """
        formatted_data = []
        peak_hours = list(range(8, 21))  # Hours 8-20
        
        for hour in range(1, 25):
            if hour in peak_hours:
                price = peak_price
            else:
                price = base_price
            
            formatted_data.append({
                'date': date_str,
                'hour': f"H{hour}",
                'price': price,
                'source': 'memo'
            })
        
        return formatted_data
    
    def _extract_prices_from_row(self, cells, date_str: str) -> List[Dict]:
        """Extract price data from a table row"""
        prices = []
        # This is a placeholder - actual implementation depends on table structure
        # You may need to inspect the actual HTML structure of dam.memo.mk
        try:
            # Common pattern: date, then 24 hourly prices
            # Or: date, base price, peak price, then hourly breakdown
            for i, cell in enumerate(cells[1:], start=1):  # Skip first cell (usually date)
                text = cell.get_text().strip()
                # Try to extract numeric price
                price_match = re.search(r'[\d,]+\.?\d*', text.replace(',', '.'))
                if price_match:
                    try:
                        price = float(price_match.group().replace(',', '.'))
                        if 1 <= i <= 24:  # Valid hour range
                            prices.append({
                                'date': date_str,
                                'hour': f"H{i}",
                                'price': price,
                                'source': 'memo'
                            })
                    except ValueError:
                        continue
        except Exception as e:
            self.logger.debug(f"Error extracting prices from row: {e}")
        
        return prices
    
    def _extract_from_scripts(self, soup: BeautifulSoup, date_str: str, memo_date_str: str) -> List[Dict]:
        """Extract hourly price data from Highcharts chart scripts"""
        formatted_data = []
        scripts = soup.find_all('script')
        
        # First, find what date the chart is showing (from the table)
        chart_date = None
        tables = soup.find_all('table')
        for table in tables:
            headers = table.find_all(['th', 'td'])
            header_text = ' '.join([h.get_text().strip() for h in headers[:8]])
            if 'base price' in header_text.lower() and 'peak price' in header_text.lower():
                rows = table.find_all('tr')
                if len(rows) > 1:
                    # Get the first data row (most recent date)
                    first_row = rows[1]
                    cells = [td.get_text().strip() for td in first_row.find_all(['td', 'th'])]
                    if cells:
                        chart_date = cells[0]  # Delivery date from first column
                        break
        
        # Only extract chart data if it matches our target date
        if chart_date and (memo_date_str in chart_date or date_str in chart_date):
            self.logger.info(f"Chart date {chart_date} matches target date {date_str}")
        elif chart_date:
            self.logger.warning(f"Chart shows date {chart_date}, but requested {date_str}")
            # Still try to extract if it's the only data available
        
        for script in scripts:
            if script.string:
                text = script.string
                
                # Look for Highcharts configuration with "Price (€/MWh)" series
                price_label_pattern = r'["\']Price\s*\([€$€]?/?MWh\)["\']|["\']PriceEUR["\']'
                if re.search(price_label_pattern, text, re.IGNORECASE):
                    self.logger.info("Found Price series in chart data")
                    
                    # Extract the data array - look for the pattern more flexibly
                    # Pattern: "Price..." followed by "data":[...]
                    price_section = re.search(
                        r'["\']Price[^"\']*["\'][^}]*"data"\s*:\s*\[([\d\s,\.\-]+)\]',
                        text,
                        re.IGNORECASE | re.DOTALL
                    )
                    
                    if price_section:
                        arr_str = price_section.group(1)
                        try:
                            # Parse the price array
                            numbers = []
                            for num_str in arr_str.split(','):
                                num_str = num_str.strip()
                                # Handle negative numbers and decimals
                                if num_str.replace('.', '').replace('-', '').isdigit():
                                    numbers.append(float(num_str))
                            
                            # Verify it's 24 hourly prices
                            if len(numbers) == 24 and all(0 <= n <= 500 for n in numbers):
                                self.logger.info(f"Extracted 24 hourly prices from chart: {numbers[:5]}...{numbers[-5:]}")
                                
                                # Only use if date matches or if no date was found in table
                                if not chart_date or memo_date_str in chart_date or date_str in chart_date:
                                    # Create hourly records
                                    for hour in range(1, 25):
                                        formatted_data.append({
                                            'date': date_str,
                                            'hour': f"H{hour}",
                                            'price': numbers[hour - 1],  # Arrays are 0-indexed
                                            'source': 'memo'
                                        })
                                    self.logger.info(f"Successfully extracted 24 hourly prices from chart for {date_str}")
                                    return formatted_data  # Found it, return immediately
                                else:
                                    self.logger.warning(f"Chart data is for {chart_date}, not {date_str}")
                        except (ValueError, IndexError) as e:
                            self.logger.debug(f"Error parsing price array: {e}")
                            continue
        
        return formatted_data
    
    def _try_common_endpoints(self, date_str: str) -> List[Dict]:
        """Try common API endpoint patterns"""
        formatted_data = []
        common_endpoints = [
            f"{self.base_url}/api/day-ahead/{date_str}",
            f"{self.base_url}/api/prices/{date_str}",
            f"{self.base_url}/api/dam/{date_str}",
            f"{self.base_url}/data/prices/{date_str}.json",
        ]
        
        for endpoint in common_endpoints:
            try:
                response = requests.get(endpoint, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        formatted_data = self._parse_api_response(data, date_str)
                        if formatted_data:
                            self.logger.info(f"Found data at endpoint: {endpoint}")
                            break
                    except json.JSONDecodeError:
                        continue
            except:
                continue
        
        return formatted_data


# Example scraper template for a different website
class ExampleScraper(BasePriceScraper):
    """
    Example scraper template for a different website.
    Copy this class and modify it to create a new scraper.
    """
    
    def __init__(self, api_url: str = None):
        super().__init__("ExampleScraper")
        self.api_url = api_url or "https://example.com/api/prices"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
    
    def scrape_prices(self, target_date: Optional[str] = None, days_back: int = 0) -> List[Dict]:
        """
        Implement your scraping logic here.
        This is just a template - modify it for your specific website.
        """
        try:
            # Determine the date to scrape
            if target_date:
                scrape_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                scrape_date = datetime.now().date() - timedelta(days=days_back)
            
            date_str = scrape_date.strftime('%Y-%m-%d')
            self.logger.info(f"Scraping from {self.name} for date: {date_str}")
            
            # TODO: Implement your scraping logic here
            # Example: Make API request
            # response = requests.get(f"{self.api_url}?date={date_str}", headers=self.headers, timeout=30)
            # data = response.json()
            
            # TODO: Parse the response and format it
            # formatted_data = []
            # for record in data:
            #     formatted_record = {
            #         'date': date_str,
            #         'hour': f"H{record['hour']}",
            #         'price': float(record['price']),
            #         'volume': float(record.get('volume', 0)),
            #         'status': record.get('status', 'unknown')
            #     }
            #     formatted_data.append(formatted_record)
            
            # TODO: Save to database
            # if formatted_data:
            #     self.save_to_db(formatted_data)
            
            # Return empty list for now (template)
            self.logger.warning("ExampleScraper is a template - implement scrape_prices() method")
            return []
            
        except Exception as e:
            self.logger.error(f"Error scraping data: {str(e)}")
            return []
