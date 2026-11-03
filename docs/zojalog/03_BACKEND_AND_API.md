# 03 — Backend and API (legacy FastAPI app)

**Scope:** `app/` (FastAPI). This is **not** the production read path (React talks to InsForge directly) — see [02](02_ARCHITECTURE_AND_DATA_FLOW.md). Deployment status **[U]**.
**Evidence:** source read in full **[V]**; `repeat_every` behaviour verified in the installed library (`.venv/.../fastapi_utils/tasks.py`, v0.8.0) **[V]**; endpoint runtime results were **not** exercised (no calls made to the DB/hardware) so response claims below are from code reading.

## 1. Layout
```
app/
  main.py                      all routes, startup tasks, analysis maths (1,273 lines)
  core/config.py               pydantic-settings `Settings` (env_file=".env")
  models/database.py           HourlyPrice, EnergyGeneration, MockQuery/MockSession (fake SQLAlchemy)
  models/insforge_client.py    execute_sql() → InsForge /api/database/advance/rawsql
  services/solarlog_client.py  EnergyDataService (hardware client + hourly calc + save)
  services/hupx_scraper.py     BasePriceScraper, HUPXScraper, MEMOScraper, ExampleScraper
  services/scraper_factory.py  ScraperFactory registry/singletons
  templates/ index|daily|monthly.html     Jinja pages (legacy UI)
  static/css/styles.css, static/js/daily.js|monthly.js
  api/__init__.py              empty
```
Installed (`.venv`, Python 3.13.2): fastapi 0.115.8, starlette 0.45.3, uvicorn 0.34.0, fastapi_utils 0.8.0, pydantic 2.10.6, pydantic_settings 2.8.0, SQLAlchemy 2.0.38 (only `IntegrityError` is used), pandas 2.2.3, beautifulsoup4 4.13.3, requests 2.32.3, jinja2 3.1.6, python-dotenv 1.0.1. **`requirements.txt` lists only requests, python-dotenv, beautifulsoup4** (R-B7) — exactly `scripts/bridge.py`'s third-party imports, not the FastAPI app's.

## 2. Initialisation (module import side effects, `main.py` L1–56)
1. `logging.basicConfig(INFO)`; `FastAPI(title=settings.APP_NAME)`.
2. `CORSMiddleware(allow_origins=["*"], allow_credentials=True, allow_methods/headers=["*"])` (L28–34).
3. Global `price_cache = {last_updated, data}` (in-memory, per process).
4. `scraper = ScraperFactory.get_scraper(settings.SCRAPER_NAME)` (default `hupx`).
5. `energy_service = EnergyDataService(device_ip, tailscale_ip, use_tailscale_first)` from settings.
6. `Jinja2Templates("app/templates")`, `StaticFiles("app/static")` — **paths are CWD-relative; run from repo root.**
7. Importing `app.models.insforge_client` opens `.insforge/project.json` (CWD-relative) and reads `oss_host` + `api_key` at import time (R-B6).

### Configuration (`app/core/config.py`) — names only
`APP_NAME`, `DEBUG_MODE`(unused elsewhere), `CACHE_TIMEOUT`(3600 s), `SCRAPER_NAME`("hupx"), `ENERGY_DEVICE_IP`, `ENERGY_DEVICE_TAILSCALE_IP`, `USE_TAILSCALE_FIRST`(True). Defaults for the two IPs are hard-coded in source; actual values come from `.env` (not read).

## 3. Background tasks (L58–100) — important quirk
Three startup hooks exist: `startup_event` (calls `await update_price_cache()`), `update_price_cache` and `update_all_data`, the latter two decorated with `@repeat_every(seconds=CACHE_TIMEOUT)`.
**Verified:** `repeat_every`'s wrapper only does `asyncio.ensure_future(loop())` and returns `None` immediately. Consequences:
- At startup **three** perpetual loops start (2× price scrape, 1× price scrape + 7-day energy fetch). Each runs immediately, then every `CACHE_TIMEOUT`.
- Every call to `GET /api/prices/refresh` or `GET /api/debug/fetch-today-data` spawns **another** perpetual loop and returns "success" before any scrape finishes (R-B1).
- Loop bodies are `async def` but call blocking `requests`; they run on the event loop and stall all requests while scraping/fetching (R-B2).
- `update_all_data` loops `days_back in range(7)` calling `energy_service.save_data_to_db()` (hardware, up to 30 s timeouts × retries × 2 IPs each).

## 4. Endpoint inventory (27 routes, extracted from the AST)
`Consumers` = code in this repo that calls it (grep of templates/JS/frontend). Anything marked "none" is manual/curl only.
| # | Method & path | Function @line | Reads | Side effects (writes/hardware/scrape) | Consumers |
|---|---|---|---|---|---|
| 1 | GET `/` | `root` @104 | cache meta | none | none |
| 2 | GET `/api/scrapers` | `list_scrapers` @116 | factory registry | none | none |
| 3 | GET `/api/scrapers/switch/{name}` | `switch_scraper` @127 | – | **Does not switch** (only validates; needs `.env` + restart) | none |
| 4 | GET `/api/prices/current` | `get_current_prices` @144 | `price_cache` | 503 if cache empty | none |
| 5 | GET `/api/prices/refresh` | `refresh_prices` @156 | – | spawns extra loop (R-B1); always reports success | none |
| 6 | GET `/api/prices/by-date/{date}?source=` | `get_prices_by_date` @170 | DB `hourly_prices` | **scrapes + writes DB if empty**; raw `date`/`source` interpolated into SQL (R-S2) | none |
| 7 | GET `/api/prices/by-dates?dates=a,b` | `get_prices_by_dates` @230 | in-memory cache only | 404 inside `try` is re-wrapped as 500 | none |
| 8 | GET `/api/prices/from-db` | `get_prices_from_db` @259 | full table, no `source` in output | none | none |
| 9 | POST `/api/prices/fill-gaps` | `fill_missing_data_gaps` @273 | DB (1 query/day) | **scrapes (default scraper only) + writes DB** | none |
| 10 | GET `/api/prices/missing-dates` | `get_missing_dates` @345 | DB (1 query/day) | none | none |
| 11 | GET `/api/energy/fetch/{days_back}` | `fetch_energy_data` @379 | hardware | **writes DB** | none |
| 12 | GET `/api/energy/direct/{date}` | `get_energy_direct_from_hardware` @389 | hardware | none; future date returns 200 `{"error":…}` | none |
| 13 | GET `/api/energy/by-date/{date}` | `get_energy_by_date` @421 | DB `energy_generation` (raw `date` in SQL) | 404 if none | none |
| 14 | GET `/api/analysis/by-date/{date}?source=` | `get_price_energy_analysis` @448 | DB + hardware | **hardware fetch + DB write for that day on every call**; scrape+write if no prices | `templates/index.html` (hupx), `static/js/daily.js` |
| 15 | GET `/api/available-dates` | `get_available_dates` @625 | DB distinct dates | likely **fails**: `MockQuery` returns raw JSON strings and the handler calls `.strftime` on them (AttributeError) **[I]** | none |
| 16 | GET `/api/analysis/by-month/{YYYY-MM}?source=` | `get_monthly_analysis` @649 | DB (2+ queries/day) | scrape+write per day lacking prices (HUPX, then MEMO if no source) | `static/js/monthly.js` |
| 17–19 | GET `/ui`, `/ui/daily`, `/ui/monthly` | `ui_home/daily/monthly` @849/854/859 | templates | none | browser |
| 20 | GET `/api/debug/energy-data` | `debug_energy_data` @864 | all energy rows | none | none |
| 21 | GET `/api/debug/add-test-data` | `add_test_data` @899 | – | ⚠ **writes fabricated energy for today** | none |
| 22 | GET `/api/debug/check-data/{date}` | `debug_check_data` @939 | DB | none | none |
| 23 | GET `/api/debug/add-mar14-prices` | `add_march14_prices` @978 | – | ⚠ **writes hard-coded 2025-03-14 prices** | none |
| 24 | GET `/api/debug/test-energy-connection` | `test_energy_connection` @1049 | hardware ×7 days | none | none |
| 25 | GET `/api/debug/test-network-connectivity` | `test_network_connectivity` @1102 | sockets/HTTP to both IPs | none | none |
| 26 | GET `/api/debug/fetch-today-data` | `fetch_today_data` @1182 | – | spawns loop (R-B1) + hardware + DB write | none |
| 27 | GET `/api/debug/add-april-data` | `add_april_data` @1221 | – | ⚠ **writes fabricated prices+energy for 2025-04-01** | none |

All of the above are unauthenticated; CORS is wide open (R-S1). **Do not call rows 21, 23, 27.**

## 5. Response shapes (as coded)
**`/api/analysis/by-date/{date}`**: `{date, hourly_data:[{hour, energy_kwh, price_per_mwh, value}], summary:{total_energy_kwh, total_energy_mwh, total_value, average_price_per_mwh, arithmetic_avg_price_per_mwh, working_hours_avg_price_per_mwh, working_hours_count}}`. Empty case returns a *different* summary (`weighted_avg_price_per_mwh` instead of `average_price_per_mwh`, no `total_energy_mwh`) plus `message`. `hourly_data` contains only hours where `energy>0 or price>0`.
**`/api/analysis/by-month/{ym}`**: `{ "YYYY-MM-DD": {total_value, total_energy_mwh, avg_working_hour_price, working_hours}, …, "month_summary": {total_value, total_energy_mwh, days_with_data, avg_working_hour_price, total_working_hours} }` or `{status:"no_data", message, details}`. Days with no energy rows or no prices are **omitted**; future days skipped; the whole month is computed per request (N+1 queries).
Metric definitions per implementation: [05](05_SOLAR_DOMAIN_AND_CALCULATIONS.md).

## 6. Error handling & logging
Handlers catch `Exception` and return HTTP 500 `detail=str(e)`; scrapers swallow errors and return `[]` — "no data" and "failed" are indistinguishable to callers. Logging is INFO to stderr with very verbose per-hour logging in the analysis handler. No structured logs, no request IDs.

## 7. Services
- **EnergyDataService** — doc [06](06_HARDWARE_AND_DATA_COLLECTION.md) / [05](05_SOLAR_DOMAIN_AND_CALCULATIONS.md).
- **Scrapers/Factory** — doc [07](07_SCRAPERS_AND_PRICE_SOURCES.md).
- **MockSession/InsForge client** — doc [04](04_DATABASE_AND_DATA_INTEGRITY.md).

## 8. Before changing anything here
1. Check consumers: only rows 14 and 16 are used by repo code (legacy Jinja UI). Changing their JSON breaks `index.html`, `daily.js`, `monthly.js` silently (JS reads fields like `summary.arithmetic_avg_price_per_mwh`, `month_summary.avg_working_hour_price`).
2. These two endpoints duplicate the React/`public_dashboard` calculations — keep rules aligned ([05](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) §6).
3. Any DB write here goes through `MockSession` (non-persisting updates, global state): see R-D1, R-B3.
4. Do not "fix" the schedule loops without deciding whether this app is even meant to ingest data (the bridge already does) — see [14](14_ARCHITECTURAL_DECISIONS.md) ADR-003.
