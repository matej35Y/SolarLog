import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import logging
from io import StringIO
import re
from .models import HourlyPrice, session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HUPXScraper:
    def __init__(self):
        self.url = "https://hupx.hu/en/market-data/dam/weekly-data"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def scrape_prices(self):
        try:
            logger.info("Starting to scrape HUPX data...")
            response = requests.get(self.url, headers=self.headers)
            response.raise_for_status()
            
            logger.info("Successfully got response from HUPX website")
            logger.info(f"Response status code: {response.status_code}")
            
            html_io = StringIO(response.text)
            tables = pd.read_html(html_io)
            logger.info(f"Found {len(tables)} tables on the page")
            
            # Find the table with hourly prices
            hourly_prices_df = None
            for i, table in enumerate(tables):
                logger.info(f"Table {i} columns: {table.columns.tolist()}")
                if 'Hours' in table.columns:
                    hourly_prices_df = table
                    logger.info(f"Found hourly prices table at index {i}")
                    break

            if hourly_prices_df is None:
                raise Exception("Hourly prices table not found")

            logger.info("Hourly prices table shape: {}".format(hourly_prices_df.shape))
            logger.info("Sample of data:\n{}".format(hourly_prices_df.head()))

            # Clean and format the data
            formatted_data = self._format_data(hourly_prices_df)
            
            logger.info(f"Successfully formatted {len(formatted_data)} price records")
            self.save_to_db(formatted_data)
            return formatted_data

        except Exception as e:
            logger.error(f"Error scraping HUPX data: {str(e)}")
            raise

    def _format_data(self, df):
        try:
            logger.info("Starting data formatting...")
            
            # Keep only the Hours column and date columns
            date_columns = [col for col in df.columns if col != 'Hours']
            logger.info(f"Date columns found: {date_columns}")

            # Rename Hours column and format hour numbers
            df['hour'] = df['Hours'].apply(lambda x: f"H{x}" if str(x).isdigit() else x)
            df = df.drop('Hours', axis=1)

            # Filter out non-hourly rows (like 'Base' or 'Peak')
            df = df[df['hour'].str.startswith('H', na=False)]
            logger.info(f"Number of hourly rows after filtering: {len(df)}")

            # Melt the dataframe to convert dates from columns to rows
            melted_df = df.melt(
                id_vars=['hour'],
                var_name='date',
                value_name='price'
            )
            
            logger.info("Sample of melted data:\n{}".format(melted_df.head()))

            # Extract day and month from the date string (e.g., "Fri 21/02" -> "21/02")
            melted_df['date'] = melted_df['date'].apply(lambda x: re.search(r'\d{2}/\d{2}', x).group())
            
            # Convert date format from DD/MM to YYYY-MM-DD
            current_year = datetime.now().year
            melted_df['date'] = pd.to_datetime(melted_df['date'] + f'/{current_year}', format='%d/%m/%Y')
            melted_df['date'] = melted_df['date'].dt.strftime('%Y-%m-%d')

            # Sort by date and hour
            melted_df['hour_num'] = melted_df['hour'].str.extract(r'(\d+)').astype(int)
            melted_df = melted_df.sort_values(['date', 'hour_num'])
            melted_df = melted_df.drop('hour_num', axis=1)

            # Convert price to float and round to 2 decimal places
            melted_df['price'] = pd.to_numeric(melted_df['price'], errors='coerce').round(2)

            # Convert to dictionary format
            formatted_data = melted_df.to_dict('records')

            logger.info(f"Available dates: {melted_df['date'].unique()}")
            logger.info(f"Sample of formatted data: {formatted_data[:2]}")

            return formatted_data

        except Exception as e:
            logger.error(f"Error formatting data: {str(e)}")
            raise

    def save_to_db(self, data):
        for record in data:
            # Convert date string to a date object
            date_obj = datetime.strptime(record['date'], '%Y-%m-%d').date()
            
            # Check if the record already exists
            existing_record = session.query(HourlyPrice).filter_by(date=date_obj, hour=record['hour']).first()
            
            if existing_record is None:
                # Create a new HourlyPrice object
                price_record = HourlyPrice(
                    date=date_obj,
                    hour=record['hour'],
                    price=record['price']
                )
                
                # Add to session
                session.add(price_record)
            else:
                logger.info(f"Record for {record['hour']} on {record['date']} already exists. Skipping.")

        # Commit the session to save data
        session.commit()
        logger.info("Data saved to database successfully")