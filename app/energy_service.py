import json
import requests
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from .models import session, EnergyGeneration
import logging

logger = logging.getLogger(__name__)

# 100.116.216.29

class EnergyDataService:
    def __init__(self, device_ip="192.168.1.100"):
        self.url = f"http://{device_ip}/getjp"
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "X-SL-CSRF-PROTECTION": "1",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": f"http://{device_ip}",
            "Pragma": "no-cache",
            "Referer": f"http://{device_ip}/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0",
        }

    def get_hourly_data(self, days_before):
        # Define the payload
        payload_dict = {
            "141": {
                "32000": {
                    "108": None, "118": None, "119": None,
                    "145": None, "149": None, "158": None
                }
            },
            "152": None, "161": None, "162": None, "480": None,
            "776": {str(days_before): None},  # Requesting data for specific days
            "777": {"1": None},
            "801": {"100": None}
        }

        # Convert payload to JSON string with no extra spaces
        json_payload = json.dumps(payload_dict, separators=(",", ":"))
        payload = f"preval=none;{json_payload}"

        try:
            # Send the request
            response = requests.post(self.url, headers=self.headers, data=payload)
            response.raise_for_status()
            
            # Parse the JSON response
            response_json = response.json()
            intervals = response_json.get("776", {}).get(f"{days_before}", [])

            hourly_data = defaultdict(float)
            total_kwh = 0
            prev_total = 0

            for entry in intervals:
                time_stamp = entry[0]  # Time in HH:MM format
                curr_total = sum(x[1] for x in entry[1])  # Sum second values in pairs

                # Convert energy to kWh
                wh_value = curr_total - prev_total
                kwh_value = wh_value / 1000  # Convert to kWh

                # Extract hour from timestamp
                hour = time_stamp.split(":")[0]  # Get HH part

                # Store in hourly bucket
                hourly_data[hour] += kwh_value
                total_kwh += kwh_value
                prev_total = curr_total

            # Format hourly values
            sorted_hourly_data = {k: round(v, 3) for k, v in sorted(hourly_data.items())}
            total_kwh = round(total_kwh, 3)

            logger.info(f"Retrieved energy data for {days_before} days ago: {total_kwh} kWh")
            return sorted_hourly_data, total_kwh

        except Exception as e:
            logger.error(f"Error retrieving energy data: {str(e)}")
            return None, None

    def save_data_to_db(self, days_before):
        """Fetch and save energy data for a specific day"""
        hourly_data, total_kwh = self.get_hourly_data(days_before)
        
        if not hourly_data:
            logger.error(f"No data retrieved for {days_before} days ago")
            return False
        
        # Calculate the date
        target_date = datetime.now().date() - timedelta(days=days_before)
        
        # Save each hour's data
        for hour_str, kwh in hourly_data.items():
            # Convert to H1, H2 format to match price data
            hour_formatted = f"H{int(hour_str)}"
            
            try:
                # Check if record already exists
                existing = session.query(EnergyGeneration).filter_by(
                    date=target_date, hour=hour_formatted
                ).first()
                
                if existing is None:
                    # Create new record
                    energy_record = EnergyGeneration(
                        date=target_date,
                        hour=hour_formatted,
                        energy_kwh=kwh
                    )
                    session.add(energy_record)
                else:
                    # Update existing record
                    existing.energy_kwh = kwh
                
                session.commit()
                logger.info(f"Saved energy data for {target_date}, {hour_formatted}: {kwh} kWh")
                
            except IntegrityError:
                session.rollback()
                logger.warning(f"Duplicate entry for {target_date}, {hour_formatted}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error saving energy data: {str(e)}")
                
        return True 