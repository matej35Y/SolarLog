import json
import requests
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from app.models.database import session, EnergyGeneration
import logging

logger = logging.getLogger(__name__)

# desktop-l3cv8h8:8085

class EnergyDataService:
    def __init__(self, device_ip="192.168.1.100", tailscale_ip=None, use_tailscale_first=False):
        self.device_ip = device_ip
        self.tailscale_ip = tailscale_ip
        self.use_tailscale_first = use_tailscale_first
        self.current_ip = tailscale_ip if use_tailscale_first else device_ip
        self._update_url_and_headers(self.current_ip)
        logger.info(f"EnergyDataService initialized with device IP: {device_ip}, Tailscale IP: {tailscale_ip}, Using Tailscale first: {use_tailscale_first}")
    
    def _update_url_and_headers(self, ip):
        """Update URL and headers for a specific IP address"""
        self.url = f"http://{ip}/getjp"
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "X-SL-CSRF-PROTECTION": "1",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": f"http://{ip}",
            "Pragma": "no-cache",
            "Referer": f"http://{ip}/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0",
        }
    
    def _try_connection_with_fallback(self, payload, days_before):
        """Try connecting with primary IP, fallback to secondary if available"""
        ips_to_try = []
        
        if self.use_tailscale_first and self.tailscale_ip:
            ips_to_try = [self.tailscale_ip, self.device_ip]
        elif self.tailscale_ip:
            ips_to_try = [self.device_ip, self.tailscale_ip]
        else:
            ips_to_try = [self.device_ip]
        
        last_error = None
        for ip in ips_to_try:
            try:
                logger.info(f"Trying to connect via {ip} (days_back={days_before})...")
                self._update_url_and_headers(ip)
                
                max_retries = 2 if ip == ips_to_try[0] else 1  # More retries for primary IP
                retry_delay = 2
                
                for attempt in range(max_retries):
                    try:
                        response = requests.post(
                            self.url, 
                            headers=self.headers, 
                            data=payload, 
                            timeout=30,
                            allow_redirects=True
                        )
                        response.raise_for_status()
                        logger.info(f"Successfully connected via {ip}")
                        self.current_ip = ip  # Remember which IP worked
                        return response
                    except requests.exceptions.Timeout:
                        if attempt < max_retries - 1:
                            logger.warning(f"Timeout connecting to {ip} (attempt {attempt + 1}/{max_retries}), retrying...")
                            import time
                            time.sleep(retry_delay)
                        else:
                            raise
                    except requests.exceptions.ConnectionError as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Connection error to {ip} (attempt {attempt + 1}/{max_retries}): {str(e)}, retrying...")
                            import time
                            time.sleep(retry_delay)
                        else:
                            raise
                            
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                logger.warning(f"Failed to connect via {ip}: {str(e)}")
                if ip != ips_to_try[-1]:  # Not the last IP to try
                    logger.info(f"Trying fallback IP...")
                    continue
                else:
                    raise
        
        # If we get here, all IPs failed
        if last_error:
            raise last_error
        raise Exception("No IP addresses available to try")

    def get_hourly_data(self, days_before):
        if days_before < 0:
            logger.info(f"Skipping hardware fetch for future date ({days_before} days back)")
            return {}, 0
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
            # Try connection with automatic fallback between local and Tailscale IPs
            response = self._try_connection_with_fallback(payload, days_before)
            
            # Parse the JSON response
            response_json = response.json()
            intervals = response_json.get("776", {}).get(f"{days_before}", [])

            if not intervals:
                logger.warning(f"Device returned empty intervals for {days_before} days ago")
                return {}, 0

            hourly_data = defaultdict(float)
            total_kwh = 0
            prev_total = None  # Start with None to skip the first cumulative yield reading spike

            # It's better to sort intervals by time to ensure cumulative calculation is correct
            sorted_intervals = sorted(intervals, key=lambda x: x[0])

            # IMPORTANT: For SolarLog, if intervals is for the whole day, the first record 
            # should be compared against the previous day's last record OR we should handle 
            # the case where the first record of the day is already large.
            # However, if it resets at midnight, prev_total=0 is fine.
            
            for entry in sorted_intervals:
                time_stamp = entry[0]  # Time in HH:MM format
                curr_total = sum(x[1] for x in entry[1])  # Sum second values in pairs

                # Convert energy to kWh
                if prev_total is not None:  # Only calculate difference after the first record
                    wh_value = curr_total - prev_total
                    if wh_value < 0:
                        logger.warning(f"Negative energy value detected at {time_stamp}: {wh_value} Wh. Device might have reset.")
                        wh_value = 0
                    
                    kwh_value = wh_value / 1000  # Convert to kWh

                    # Extract hour from timestamp
                    hour_int = int(time_stamp.split(":")[0])  
                    # If timestamp is 00:05, it belongs to the first hour of the day (H1)
                    # If timestamp is 01:00, it's the end of the first hour or start of second?
                    # Most systems use HH:MM as the "end of interval".
                    # So 00:00 to 00:59 is Hour 1.
                    hour_key = hour_int + 1
                    
                    # Store in hourly bucket
                    hourly_data[hour_key] += kwh_value
                    total_kwh += kwh_value
                
                prev_total = curr_total

            # Format hourly values
            formatted_hourly_data = {str(k): round(v, 3) for k, v in sorted(hourly_data.items())}
            total_kwh = round(total_kwh, 3)

            logger.info(f"Retrieved energy data for {days_before} days ago: {total_kwh} kWh across {len(formatted_hourly_data)} hours")
            return formatted_hourly_data, total_kwh

        except Exception as e:
            logger.error(f"Error retrieving energy data from {self.url}: {str(e)}")
            return None, None

    def fetch_multiple_days(self, days_list):
        """Fetch energy data for multiple days"""
        results = {}
        for days_back in days_list:
            try:
                hourly_data, total_kwh = self.get_hourly_data(days_back)
                if hourly_data is not None:
                    results[days_back] = {
                        "success": True,
                        "data": hourly_data,
                        "total_kwh": total_kwh
                    }
                else:
                    results[days_back] = {
                        "success": False,
                        "error": "Connection failed"
                    }
            except Exception as e:
                results[days_back] = {
                    "success": False,
                    "error": str(e)
                }
        return results
    
    def save_data_to_db(self, days_before):
        """Fetch and save energy data for a specific day"""
        if days_before < 0:
            logger.info(f"Skipping energy data save for future date ({days_before} days back)")
            return True
        try:
            hourly_data, total_kwh = self.get_hourly_data(days_before)
            
            if hourly_data is None:
                logger.error(f"Failed to retrieve data for {days_before} days ago due to connection or parsing error")
                return False
            
            if not hourly_data:
                logger.warning(f"No production data available for {days_before} days ago (possibly night time or device off)")
                # We still return True because there was no "error", just no data
                return True
        except requests.exceptions.Timeout:
            logger.error(f"Timeout connecting to energy device at {self.device_ip} for {days_before} days ago")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to energy device at {self.device_ip}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error fetching energy data: {str(e)}")
            return False
        
        # Calculate the date
        target_date = datetime.now().date() - timedelta(days=days_before)
        
        # Save each hour's data
        for hour_num, kwh in hourly_data.items():
            # Convert to H1, H2 format to match price data
            hour_formatted = f"H{hour_num}"
            
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