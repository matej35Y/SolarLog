"""
SolarLog Cloud Bridge
Runs on your local Mac, syncs SolarLog energy data + market prices to InsForge.
Every 15 minutes: fetch SolarLog → push to cloud + scrape HUPX & MEMO prices.
"""
import json
import math
import re
import requests
import time
import logging
import os
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
    PLANT_TZ = ZoneInfo("Europe/Skopje")
except Exception:
    PLANT_TZ = None

def get_plant_now():
    """Return current datetime in the solar plant's timezone (Europe/Skopje)."""
    if PLANT_TZ:
        return datetime.now(PLANT_TZ)
    return datetime.now()

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logging.warning("beautifulsoup4 not installed — MEMO scraping disabled. Run: pip3 install beautifulsoup4")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("bridge")

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv(".env.bridge")

INSFORGE_URL      = os.getenv("INSFORGE_URL", "https://z9dt4nnj.eu-central.insforge.app")
INSFORGE_ANON_KEY = os.getenv("INSFORGE_ANON_KEY", "")
INSFORGE_API_KEY  = os.getenv("INSFORGE_API_KEY", "")  # Admin key; keep server-side only.
DEVICE_IP         = os.getenv("ENERGY_DEVICE_IP",           "192.168.1.100")
TAILSCALE_IP      = os.getenv("ENERGY_DEVICE_TAILSCALE_IP", "desktop-l3cv8h8:8085")
USE_TAILSCALE     = os.getenv("USE_TAILSCALE_FIRST", "True").lower() == "true"
CANDIDATES_RAW    = os.getenv("SOLARLOG_CANDIDATES", "desktop-l3cv8h8:8085,desktop-l3cv8h8:8080,100.116.216.29:8085,100.116.216.29:8080,192.168.1.100")
CACHE_FILE        = ".device_cache"

CYCLE_MINUTES = 15   # how often to re-run the full sync


def calculate_hourly_energy(intervals):
    """Derive hourly kWh from per-inverter yield deltas and reset-interval power."""
    hourly = defaultdict(float)
    previous_channels = None
    previous_time = None

    for timestamp, channels in sorted(intervals, key=lambda item: item[0]):
        sample_time = datetime.strptime(timestamp, "%H:%M:%S")
        if previous_channels is not None:
            elapsed_seconds = (sample_time - previous_time).total_seconds()
            if elapsed_seconds < 0:
                elapsed_seconds += 24 * 60 * 60
            if elapsed_seconds > 0:
                hour = f"H{sample_time.hour + 1}"
                for index, current in enumerate(channels):
                    if index >= len(previous_channels):
                        continue

                    previous = previous_channels[index]
                    current_yield = float(current[1])
                    previous_yield = float(previous[1])
                    if current_yield >= previous_yield:
                        energy_wh = current_yield - previous_yield
                    else:
                        powers = []
                        for power in (previous[0], current[0]):
                            power = float(power)
                            if math.isfinite(power):
                                powers.append(max(0.0, power))
                        energy_wh = (
                            sum(powers) / len(powers) * elapsed_seconds / 3600.0
                            if powers
                            else 0.0
                        )
                    hourly[hour] += energy_wh / 1000.0

        previous_channels = channels
        previous_time = sample_time

    return {
        f"H{hour}": round(hourly.get(f"H{hour}", 0.0), 4)
        for hour in range(1, 25)
    }


def ensure_tailscale():
    """Check if Tailscale is running on Mac; if stopped, start it up."""
    try:
        res = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=4)
        output = (res.stdout + " " + res.stderr).lower()
        if "stopped" in output or "not running" in output or res.returncode != 0:
            logger.info("  ⚠️ Tailscale daemon appears stopped. Starting Tailscale...")
            for bin_path in ["/Applications/Tailscale.app/Contents/MacOS/Tailscale", "tailscale"]:
                try:
                    subprocess.run([bin_path, "up", "--accept-routes=true"], capture_output=True, text=True, timeout=8)
                    time.sleep(2)
                    break
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"Tailscale check: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  InsForge REST client (direct /api/database/records/ endpoint)
# ═══════════════════════════════════════════════════════════════════════════════
class InsForgeClient:
    def __init__(self, url: str, anon_key: str, admin_key: str = None):
        self.base    = url.rstrip("/")
        self.read_headers  = {"Authorization": f"Bearer {anon_key}",  "Content-Type": "application/json"}
        self.write_headers = {"Authorization": f"Bearer {admin_key or anon_key}", "Content-Type": "application/json"}

    def _records_url(self, table: str) -> str:
        return f"{self.base}/api/database/records/{table}"

    def get_latest_date(self, table: str) -> str:
        """Fetch the max date recorded in table, returning YYYY-MM-DD or None."""
        try:
            r = requests.post(
                f"{self.base}/api/database/advance/rawsql",
                headers=self.write_headers,
                json={"query": f"SELECT max(date) as max_date FROM {table}"},
                timeout=15
            )
            r.raise_for_status()
            rows = r.json().get("rows", [])
            if rows:
                val = rows[0].get("max_date") or rows[0].get("max")
                if val:
                    return str(val).split("T")[0]
        except Exception as e:
            logger.warning(f"  ↳ Could not fetch latest date from {table}: {e}")
        return None

    def get_incomplete_energy_dates(self, days_back: int = 7) -> list:
        """Find any dates in the last N days that have incomplete (<24 rows) or near-zero (<1.0 kWh) energy data."""
        try:
            query = f"SELECT date::text, count(*) as count, coalesce(sum(energy_kwh), 0) as total FROM energy_generation WHERE date >= (CURRENT_DATE - INTERVAL '{days_back} days') GROUP BY date HAVING count(*) < 24 OR sum(energy_kwh) < 1.0"
            r = requests.post(
                f"{self.base}/api/database/advance/rawsql",
                headers=self.write_headers,
                json={"query": query},
                timeout=15
            )
            r.raise_for_status()
            rows = r.json().get("rows", [])
            return [str(r.get("date")).split("T")[0] for r in rows if r.get("date") is not None]
        except Exception as e:
            logger.warning(f"  ↳ Could not check incomplete energy dates: {e}")
            return []

    def upsert(self, table: str, records: list, conflict_cols: str) -> bool:
        """Insert records in a single bulk batch with retries; on conflict update the value column."""
        if not records:
            return True
        cols = list(records[0].keys())
        cols_str = ", ".join(cols)
        
        row_values = []
        for rec in records:
            vals = []
            for c in cols:
                v = rec.get(c)
                if isinstance(v, str):
                    vals.append("'" + v.replace("'", "''") + "'")
                elif v is None:
                    vals.append("NULL")
                else:
                    vals.append(str(v))
            row_values.append(f"({', '.join(vals)})")

        if table == "hourly_prices":
            update_expr = "price = EXCLUDED.price"
        else:
            update_expr = "energy_kwh = EXCLUDED.energy_kwh"

        sql = (
            f"INSERT INTO {table} ({cols_str}) VALUES\n"
            + ",\n".join(row_values)
            + f"\nON CONFLICT ({conflict_cols}) DO UPDATE SET {update_expr}"
        )
        for attempt in range(1, 4):
            try:
                r = requests.post(
                    f"{self.base}/api/database/advance/rawsql",
                    headers=self.write_headers,
                    json={"query": sql},
                    timeout=20
                )
                r.raise_for_status()
                logger.info(f"  ✓ {table}: {len(records)} rows synced (1 batch)")
                return True
            except Exception as e:
                if attempt < 3:
                    logger.warning(f"  ⚠️ bulk upsert attempt {attempt}/3 failed: {e}. Retrying in 3s...")
                    time.sleep(3)
                else:
                    logger.warning(f"  ↳ bulk upsert failed after 3 attempts: {e}")
                    return False


# ═══════════════════════════════════════════════════════════════════════════════
#  SolarLog hardware fetcher
# ═══════════════════════════════════════════════════════════════════════════════
class SolarLogFetcher:
    def __init__(self, ip: str, ts_ip: str = None):
        self.ip     = ip
        self.ts_ip  = ts_ip
        self.candidates = [c.strip() for c in CANDIDATES_RAW.split(",") if c.strip()]
        
        # Build priority list
        priority = []
        if USE_TAILSCALE and ts_ip:
            priority.append(ts_ip)
            # Add port 8080 / 8085 alternate
            if ":8085" in ts_ip:
                alt = ts_ip.replace(":8085", ":8080")
                if alt not in priority: priority.append(alt)
            elif ":8080" in ts_ip:
                alt = ts_ip.replace(":8080", ":8085")
                if alt not in priority: priority.append(alt)

        if ip and ip not in priority:
            priority.append(ip)

        for c in self.candidates:
            if c not in priority:
                priority.append(c)
        
        self.priority_list = priority
        self.active = self._get_cached_ip() or priority[0]

    def _get_cached_ip(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    cached = f.read().strip()
                    if cached: return cached
            except: return None
        return None

    def _save_cached_ip(self, ip):
        try:
            with open(CACHE_FILE, "w") as f:
                f.write(ip)
        except: pass

    def _discover_device(self) -> bool:
        """Try all candidates until one responds with status 200."""
        logger.info("  🔍 Discovering SolarLog hardware...")
        ensure_tailscale()

        probe_payload = 'preval=none;{"777":{"1":null}}'
        candidates_to_try = [self.active] + [c for c in self.priority_list if c != self.active]
        
        for ip in candidates_to_try:
            url = f"http://{ip}/getjp"
            logger.info(f"    Trying {ip}...")
            for attempt in range(3):
                try:
                    r = requests.post(url, headers=self._headers(), data=probe_payload, timeout=6)
                    if r.status_code == 200:
                        logger.info(f"    ✨ Found SolarLog at {ip}!")
                        self.active = ip
                        self._save_cached_ip(ip)
                        return True
                    elif r.status_code == 503:
                        logger.info(f"    SolarLog @ {ip} returned 503 (device busy/initializing), waiting 3s...")
                        time.sleep(3)
                        continue
                except Exception:
                    break
        
        logger.error("  ✗ Hardware Discovery FAILED. Is the device connected to the network?")
        return False

    def _headers(self):
        return {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "X-SL-CSRF-PROTECTION": "1",
            "User-Agent": "SolarLogBridge/2.0",
        }

    def fetch_day(self, days_back: int = 0, base_date: datetime = None) -> list:
        """Return list of {date, hour, energy_kwh} dicts for one day."""
        payload = f'preval=none;{{\"776\":{{"{days_back}":null}}}}'
        r = None

        for attempt in range(3):
            url = f"http://{self.active}/getjp"
            try:
                r = requests.post(url, headers=self._headers(), data=payload, timeout=25)
                if r.status_code == 503:
                    logger.warning(f"  ⚠️ SolarLog @ {self.active} busy (503), retrying in 4s (attempt {attempt+1}/3)...")
                    time.sleep(4)
                    continue
                r.raise_for_status()
                break
            except Exception as e:
                logger.warning(f"  ⚠️ Fetch failed on {self.active} (attempt {attempt+1}/3): {e}")
                ensure_tailscale()
                if not self._discover_device():
                    if attempt == 2:
                        return []
                time.sleep(2)
        else:
            return []

        if r is None or r.status_code != 200:
            return []

        try:
            logger.info(f"  ↳ SolarLog @ {self.active}  (days_back={days_back})")
            intervals = r.json().get("776", {}).get(str(days_back), [])
            if not intervals:
                logger.info(f"    No intervals returned for days_back={days_back} (nighttime / device off).")
                return []

            hourly = calculate_hourly_energy(intervals)

            anchor = base_date if base_date is not None else get_plant_now()
            target = (anchor - timedelta(days=days_back)).strftime("%Y-%m-%d")
            rows   = [{"date": target, "hour": h, "energy_kwh": v}
                      for h, v in hourly.items()]
            logger.info(f"    {len(rows)} hourly buckets, {sum(r['energy_kwh'] for r in rows):.2f} kWh total")
            return rows

        except Exception as e:
            logger.error(f"  ✗ SolarLog parse failed: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════════════
#  HUPX price scraper  (labs.hupx.hu JSON API)
# ═══════════════════════════════════════════════════════════════════════════════
class HUPXScraper:
    API = "https://labs.hupx.hu/data/v1/dam_aggregated_trading_data"

    def scrape(self, date_str: str) -> list:
        url = f"{self.API}?filter=DeliveryDay__gte__{date_str},DeliveryDay__lte__{date_str}"
        try:
            logger.info(f"  ↳ HUPX  {date_str}")
            r   = requests.get(url, timeout=20)
            r.raise_for_status()
            raw = r.json().get("data", [])
            rows = [
                {
                    "date":   rec["DeliveryDay"][:10],
                    "hour":   f"H{int(rec['ProductH'])}",
                    "price":  float(rec["Price"]),
                    "source": "hupx",
                }
                for rec in raw
            ]
            logger.info(f"    {len(rows)} price records")
            return rows
        except Exception as e:
            logger.error(f"  ✗ HUPX scrape failed: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════════════
#  MEMO price scraper  (dam-data.memo.mk HTML table)
# ═══════════════════════════════════════════════════════════════════════════════
class MEMOScraper:
    URL = "https://dam-data.memo.mk/index.php?action=auction-by-hour&lang=en"
    HEADERS = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://dam-data.memo.mk",
        "Referer": "https://dam-data.memo.mk/index.php?action=auction-by-hour&lang=en",
    }

    def scrape(self, date_str: str) -> list:
        if not BS4_AVAILABLE:
            logger.warning("  ✗ MEMO skipped (beautifulsoup4 not installed)")
            return []
        try:
            logger.info(f"  ↳ MEMO  {date_str}")
            r = requests.post(
                self.URL, headers=self.HEADERS,
                data={"date": date_str, "submit": "Search"}, timeout=20
            )
            r.raise_for_status()
            soup   = BeautifulSoup(r.content, "html.parser")
            tables = soup.find_all("table")

            # table[2] = hourly breakdown; header row has dates like "Thursday 16.04.2026"
            if len(tables) < 3:
                logger.warning("    Unexpected page structure — fewer than 3 tables")
                return []

            hour_table = tables[2]
            rows       = hour_table.find_all("tr")
            header     = [c.get_text().strip() for c in rows[0].find_all(["th", "td"])]

            # Find which column = our target date  (format: DD.MM.YYYY)
            target_fmt = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
            col_idx    = -1
            for i, cell in enumerate(header):
                if target_fmt in cell:
                    col_idx = i
                    break

            if col_idx == -1:
                logger.warning(f"    Date {target_fmt} not found in headers: {header}")
                return []

            records = []
            for row in rows[1:]:
                cells = [c.get_text().strip() for c in row.find_all(["th", "td"])]
                if len(cells) <= col_idx:
                    continue
                # Only price rows (€/MWh), skip quantity rows (MWh)
                unit = cells[1] if len(cells) > 1 else ""
                if "€" not in unit and "Price" not in unit and "MKD" not in unit:
                    continue

                hour_range = cells[0]   # e.g. "00 - 01"
                m = re.match(r"(\d{2})\s*-\s*(\d{2})", hour_range)
                if not m:
                    continue
                start_h  = int(m.group(1))
                hour_num = start_h + 1   # "00 - 01" → H1

                raw_price = cells[col_idx]
                # MEMO uses comma as decimal separator → convert
                if "," in raw_price:
                    raw_price = raw_price.replace(".", "").replace(",", ".")
                else:
                    raw_price = raw_price.replace(",", "")
                try:
                    price = float(raw_price)
                except ValueError:
                    continue

                records.append({
                    "date":   date_str,
                    "hour":   f"H{hour_num}",
                    "price":  price,
                    "source": "memo",
                })

            logger.info(f"    {len(records)} hourly prices")
            return records
        except Exception as e:
            logger.error(f"  ✗ MEMO scrape failed: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════════════
#  Main sync loop
# ═══════════════════════════════════════════════════════════════════════════════
def run_cycle(db: InsForgeClient, solar: SolarLogFetcher,
              hupx: HUPXScraper, memo: MEMOScraper):
    now      = get_plant_now()
    today    = now.strftime("%Y-%m-%d")
    today_dt = datetime.strptime(today, "%Y-%m-%d")

    logger.info("═" * 50)
    logger.info(f"  Cycle start:  {now.strftime('%Y-%m-%d %H:%M:%S')} (plant time)")

    # 1. Energy data: always sync today (0), yesterday (1), and day before yesterday (2)
    logger.info("[ SolarLog Energy ]")
    latest_energy_date = db.get_latest_date("energy_generation")
    days_to_fetch = {0, 1, 2}

    if latest_energy_date:
        try:
            latest_dt = datetime.strptime(latest_energy_date, "%Y-%m-%d")
            gap = (today_dt - latest_dt).days
            if gap > 2:
                backfill_count = min(gap, 14)
                logger.info(f"  Gap detected: latest cloud data is {latest_energy_date} ({gap} days ago). Backfilling past {backfill_count} days…")
                for d in range(backfill_count + 1):
                    days_to_fetch.add(d)
            else:
                logger.info(f"  Cloud data up to date ({latest_energy_date}).")
        except Exception as e:
            logger.warning(f"  Could not calculate energy date gap: {e}")
    else:
        logger.info("  No existing energy data found in cloud. Fetching past 7 days…")
        for d in range(7):
            days_to_fetch.add(d)

    # Check for any incomplete / zero days in recent days (e.g. from interrupted cycles or failed syncs)
    try:
        incomplete = db.get_incomplete_energy_dates(days_back=7)
        for inc_date in incomplete:
            inc_dt = datetime.strptime(inc_date, "%Y-%m-%d")
            d_back = (today_dt - inc_dt).days
            if 0 <= d_back <= 14:
                logger.info(f"  Detected incomplete energy data on {inc_date} (days_back={d_back}). Re-fetching.")
                days_to_fetch.add(d_back)
    except Exception as e:
        logger.debug(f"  Incomplete check note: {e}")

    # Fetch older days first so history is filled, then today last
    for days_back in sorted(days_to_fetch, reverse=True):
        rows = solar.fetch_day(days_back, base_date=today_dt)
        if rows:
            db.upsert("energy_generation", rows, "date, hour")

    # 2. Market Prices: check latest date in cloud and determine missing dates
    logger.info("[ Market Prices: HUPX & MEMO ]")
    latest_price_date = db.get_latest_date("hourly_prices")
    dates_to_fetch = {today}

    if latest_price_date:
        try:
            latest_p_dt = datetime.strptime(latest_price_date, "%Y-%m-%d")
            gap = (today_dt - latest_p_dt).days
            if gap > 0:
                backfill_count = min(gap, 14)
                logger.info(f"  Gap detected: latest cloud price is {latest_price_date} ({gap} days ago). Backfilling past {backfill_count} days…")
                for d in range(backfill_count + 1):
                    dates_to_fetch.add((today_dt - timedelta(days=d)).strftime("%Y-%m-%d"))
        except Exception as e:
            logger.warning(f"  Could not calculate price date gap: {e}")
    else:
        for d in range(7):
            dates_to_fetch.add((today_dt - timedelta(days=d)).strftime("%Y-%m-%d"))

    # Day-ahead prices (tomorrow) published around 13:00 CET
    if now.hour >= 13:
        tomorrow = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        dates_to_fetch.add(tomorrow)

    for date_str in sorted(dates_to_fetch):
        # HUPX
        h_rows = hupx.scrape(date_str)
        if h_rows:
            db.upsert("hourly_prices", h_rows, "date, hour, source")
        
        # MEMO
        m_rows = memo.scrape(date_str)
        if m_rows:
            db.upsert("hourly_prices", m_rows, "date, hour, source")

    logger.info(f"  Cycle done.  Next run in {CYCLE_MINUTES} min.")


def main():
    logger.info("SolarLog Bridge v2 starting up…")
    logger.info(f"  InsForge:  {INSFORGE_URL}")
    logger.info(f"  SolarLog:  {TAILSCALE_IP if USE_TAILSCALE else DEVICE_IP}")
    logger.info(f"  Cycle:     every {CYCLE_MINUTES} min")

    ensure_tailscale()

    db    = InsForgeClient(INSFORGE_URL, INSFORGE_ANON_KEY, INSFORGE_API_KEY)
    solar = SolarLogFetcher(DEVICE_IP, TAILSCALE_IP)
    hupx  = HUPXScraper()
    memo  = MEMOScraper()

    while True:
        try:
            run_cycle(db, solar, hupx, memo)
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in cycle: {e}")

        # Sleep in 5-second intervals tracking wall-clock time.
        # When macOS wakes up from sleep/suspend, wall-clock time will have advanced,
        # triggering an immediate cycle instead of freezing inside a long sleep.
        cycle_seconds = CYCLE_MINUTES * 60
        start_wait = time.time()
        try:
            while time.time() - start_wait < cycle_seconds:
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            break


if __name__ == "__main__":
    main()
