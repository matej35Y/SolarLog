# 07 — Scrapers and Price Sources

**Evidence:** code read in full **[V]**; dead-code claims confirmed by grep **[V]**; bridge log shows live behaviour **[V]**. No scrapers were run during onboarding (they write to the production DB).

## 1. Two implementations of the same scrapers
| | Bridge (`scripts/bridge.py`) | FastAPI (`app/services/hupx_scraper.py`) |
|---|---|---|
| Classes | `HUPXScraper.scrape(date)`, `MEMOScraper.scrape(date)` (plain classes) | `BasePriceScraper` → `HUPXScraper`, `MEMOScraper`, `ExampleScraper` via `ScraperFactory` |
| Persistence | **returns rows**; `run_cycle` upserts | **writes to DB itself** (`save_to_db`) as a side effect of `scrape_prices()` |
| MEMO date column missing | returns `[]` | **falls back to column index 2** (L534–536) → may store another day's prices under the requested date (R-D4) |
| Production? | **Yes** | legacy |

## 2. HUPX (Hungary)
- Endpoint: `https://labs.hupx.hu/data/v1/dam_aggregated_trading_data?filter=DeliveryDay__gte__D,DeliveryDay__lte__D` (JSON, GET).
- Mapping per record: `date = DeliveryDay[:10]`, `hour = "H" + int(ProductH)`, `price = float(Price)` (EUR/MWh), plus `Volume`, `Status` in the FastAPI version only. Source tag `hupx`.
- **Defect (R-D3):** `int(ProductH)` raises for DST values like `'3B'`. In both implementations the comprehension/loop is inside one `try`, so the **entire day's HUPX list is dropped** (bridge) or the offending record skipped (FastAPI `except (ValueError, KeyError): continue` → only that record). Bridge log: 19 attempts for **2026-10-25** — 18 `'3B'` failures + 1 network failure, **0 successes** (re-verified 2026-11-03). The bridge never retries a past date unless the price-date gap logic triggers.
- Open question **[U]:** the European day-ahead market moved to 15-minute products in 2025; whether this HUPX endpoint still returns hourly aggregates (current code assumes `ProductH` = hour number and 24 rows/day) was not verified. Bridge logs show "24 price records" per date, which supports hourly output at present.

## 3. MEMO (North Macedonia)
- Active path: `POST https://dam-data.memo.mk/index.php?action=auction-by-hour&lang=en` with form `date=YYYY-MM-DD&submit=Search`; parse HTML with BeautifulSoup.
- Table choice: bridge uses `tables[2]`; FastAPI first looks for a table whose text has "hours" + (mwh|mkd|€), else `tables[2]`.
- Date column: header cell containing `DD.MM.YYYY` (FastAPI also tries `DD.MM.YY` and ISO).
- Rows: only rows whose unit cell contains `€`, `Price` or `MKD`; period `"00 - 01"` → `H1` (start hour + 1), `"23 - 00"` → `H24`; decimals: if value contains `,` then `.` is thousands and `,` decimal.
- Source tag `memo`. The page shows ~7 days per query; the scraper picks the requested date's column.
- **Dead code in `MEMOScraper` (unreferenced or only reachable from unreferenced methods) [V]:** `_download_excel_file`, `_try_alternative_excel_urls`, `_parse_excel_file`, `_parse_api_response`, `_distribute_base_peak_prices` (would fake hourly prices from base/peak!), `_extract_prices_from_row`, `_extract_from_scripts`, `_try_common_endpoints`. Only `scrape_prices → _scrape_from_html` is live. Do not wire the dead helpers in without review (`_distribute_base_peak_prices` fabricates data).
- `docs/MEMO_INTEGRATION.md` describes MEMO as a "template implementation" — **outdated**.

## 4. ScraperFactory (`app/services/scraper_factory.py`)
Class-level registry `{'hupx': HUPXScraper, 'memo': MEMOScraper, 'example': ExampleScraper}` and singleton instance cache. API: `register_scraper(name, cls)` (must subclass `BasePriceScraper`), `get_scraper(name=None)` (default `'hupx'`; unknown ⇒ `ValueError` listing names), `list_scrapers()`, `get_default_scraper()`. FastAPI picks `settings.SCRAPER_NAME` at import and exposes `/api/scrapers`; `/api/scrapers/switch/{name}` only validates (restart + `.env` change required). The bridge does **not** use the factory.
`docs/SCRAPER_GUIDE.md` references `app/scraper.py` / `app/scraper_factory.py` (old paths) — **outdated**; real files are `app/services/hupx_scraper.py` and `app/services/scraper_factory.py`.

## 5. Adding a new source — checklist
1. Implement in **both** places if it must work in production: a bridge class (returns rows) and, only if the legacy API still matters, a `BasePriceScraper` subclass registered in `ScraperFactory`.
2. Output contract: `{date:'YYYY-MM-DD', hour:'H1'..'H24', price: float EUR/MWh, source:'<tag ≤16 chars>'}`.
3. Add the tag to the UI selectors (`App.jsx` source `<select>`, legacy templates `<option>`, `public_dashboard`), and decide DST behaviour.
4. `source` is part of the primary key; choose a stable tag.
5. Handle failure explicitly (return `[]` + log; never invent prices).

## 6. What can go wrong / what to check before changing
- Site markup/API changes → scrape returns `[]` silently; verify via `bridge.log` lines `↳ HUPX / MEMO` and "N price records".
- Wrong-date risk in FastAPI MEMO fallback (R-D4).
- DST days (R-D3) — next transitions: 2027-03-28 (23 h) and 2027-10-31 (25 h).
- Scrapers are blocking (`requests`, 20–30 s timeouts); in FastAPI they run on the event loop (R-B2).
- Any call to `scrape_prices()` in FastAPI/scripts **writes to the production DB** (see CLAUDE.md rule 3).
