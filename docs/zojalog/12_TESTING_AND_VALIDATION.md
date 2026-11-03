# 12 — Testing and Validation

**Evidence:** every file in `tests/` read **[V]**; function inventories from the AST **[V]**; onboarding validation runs listed in §3 were actually executed **[V-run]**.

## 1. State of testing
**There is no automated test suite.** No pytest/unittest config, no assertions, no CI config in the repo, no frontend tests (`npm run lint` exists via ESLint only). `tests/` contains **manual diagnostic scripts** that print results. Several are broken or have side effects on production data.

| File | What it does | Problems |
|---|---|---|
| `tests/test_dns.py` | Resolves the Tailscale hostname and POSTs a probe to `:8085/getjp`; retries with `.local` | Payload contains Python `None` (not JSON `null`) → invalid body; hits real network |
| `tests/test_energy.py` | Calls `EnergyDataService.get_hourly_data(0/1)` and prints | `sys.path.append(<tests dir>)` doesn't add repo root → `import app…` fails unless `PYTHONPATH=.`; importing `app` needs `.insforge/project.json`; hits hardware |
| `tests/test_long_timeout.py` | GETs the LAN IP and a logger hostname with 30 s timeout | Manual connectivity probe |
| `tests/test_memo_scraper.py` | `MEMOScraper().scrape_prices('2026-02-26')`, prints "SUCCESS/WARNING" | No assertions; **writes to the production DB** (scraper `save_to_db`); same `sys.path` issue |
| `tests/test_scraper_direct.py` | Calls `_extract_data_from_pdfs()` and `_get_dummy_data()` | **Those methods don't exist** → `AttributeError`; also would write via `scrape_prices()` |
| `tests/test_scraper_factory.py` | Exercises `ScraperFactory` (list/get/singleton/invalid) and prints ✅ | Closest to a real test; no assertions; stale hint text (mentions removed `app/scraper.py`); importing it needs `.insforge/project.json` |
Scripts that look like tests but are operational: `scripts/debug_connections.py` (probes three addresses), `scripts/scraper_usage_example.py`, `scripts/restart_scraper.py`, `scripts/fill_missing_data.py` (**write production DB**). `scripts/migrate_add_source.py` is dead (imports a non-existent `engine`).

## 2. Safe-run rules
- Anything calling `scrape_prices()` (FastAPI scrapers) or `EnergyDataService.save_data_to_db()` writes to production. Don't run without explicit approval.
- Pure functions are safe to test offline: `bridge.calculate_hourly_energy`, the frontend `useMemo` maths (extract to functions first), `hour_to_number`, MEMO/HUPX parsers against saved fixtures.
- `bridge.py` imports at module level are light, but importing `app.models.insforge_client` requires `.insforge/project.json` (CWD-relative) — stub it in tests.

## 3. Validation performed during onboarding (2026-11-03)
| Check | Method | Result |
|---|---|---|
| `repeat_every` semantics | Read installed `fastapi_utils/tasks.py` (v0.8.0, project `.venv`) | Wrapper only schedules a loop and returns → 3 loops at startup; each `/api/prices/refresh` adds one (R-B1) |
| Route inventory | AST parse of `app/main.py` | 27 routes (19 non-debug incl. 3 UI, 8 debug) + 3 startup hooks |
| Hourly-energy algorithms | Executed real `calculate_hourly_energy` (AST-extracted) and real `EnergyDataService.get_hourly_data` (DB modules stubbed, HTTP faked) on 3 synthetic cases | Matches [05 §5](05_SOLAR_DOMAIN_AND_CALCULATIONS.md): bridge 95 Wh vs legacy 0 Wh on a counter reset; `HH:00` sample lands in next hour |
| React day navigation | Re-implemented `handlePrevDay/NextDay` verbatim in Node, run with `TZ=Europe/Skopje`, `UTC`, `America/New_York` | Skopje: prev 11-03→**11-01**, next stuck at 11-03; UTC/NY correct (R-F1) |
| CSS duplication | `diff app/static/css/styles.css frontend/src/styles.css` | identical |
| Legacy SQLite | Read-only copy, schema + counts + date ranges | see [04 §5](04_DATABASE_AND_DATA_INTEGRITY.md) |
| Bridge runtime | Parsed `bridge.log` (24,804 lines) | see [06 §5](06_HARDWARE_AND_DATA_COLLECTION.md) |
| Dead code in `MEMOScraper` | `grep` for every helper | 8 helpers unreferenced / only reachable from unreferenced code |
| Unused npm deps | script over `package.json` vs imports | 7 unused (MUI, emotion, axios, dayjs, router) |
| Git state | `git status/log/ls-tree/cat-file` with `--no-optional-locks`, `core.fsmonitor=false` | refactor uncommitted; env/db files tracked |

### 3b. Second verification pass (2026-11-03, local tree + GitHub) — what was actually run
| Check | Method | Result |
|---|---|---|
| Local `app/main.py` vs GitHub `main` | `diff -u` | identical except 4 import lines (routes, logic, line anchors unchanged) |
| Local services vs GitHub | `diff -u` (`solarlog_client.py` vs `energy_service.py`, `hupx_scraper.py` vs `scraper.py`) | only imports/comment + the two future-date guards in `solarlog_client.py`; scrapers byte-for-byte same logic |
| Scripts/tests vs GitHub root copies | `diff` | only import-path changes |
| `bridge.py` read in full; `App.jsx` read in full (key lines skipped); CSS tokens, class counts, states | read + script | all claims in 05/06/08/09 confirmed (anchors L48, L93, L233, L270, L439; App.jsx L79, L114, L142–170, L195–282, L285–413, L500, L959–967) |
| CSS duplication | `cmp` | byte-identical (28,980 B) |
| `eq()` mutation of the SDK filter builder | read `postgrest-js` 1.21.4 | mutates and returns `this` |
| R-F1 date navigation | Node 22 under 3 time zones | reproduced under `Europe/Skopje` |
| `repeat_every` | read fastapi-utils 0.8.0 `tasks.py` | `ensure_future(loop())`, returns `None` |
| SQLAlchemy 2.0.38 SQLite `DATE` bind | read `dialects/sqlite/base.py` | raises `TypeError` for `str` (R-B9, GitHub `main` only) |
| `bridge.log` | `awk` per cycle-date | doc 06 §5 counts confirmed; 3B split 8/10 + 1 network failure; 0 `Gap detected` |
| SQLite snapshots (committed + working) | read-only copies, SQL | see [04 §5](04_DATABASE_AND_DATA_INTEGRITY.md), [16 §5](16_ONBOARDING_VERIFICATION_LEDGER.md) |
| Module import graph | `ast` over `app/`, `scripts/`, `tests/` | [02 §8](02_ARCHITECTURE_AND_DATA_FLOW.md) |
| Git state | read-only `git` with `--no-optional-locks` | 17 modified / 29 deleted / 71 untracked; 6 local branches; 58 checkpoint refs |
**Still not validated (second pass):** live InsForge schema/grants/rows; real SolarLog payloads and timestamp semantics; browser rendering at any width; `npm run build/lint`; deployed Vercel/FastAPI instances; the launchd plist; contents of untracked env files.

**Not validated (first pass, still open unless listed in 3b):** live InsForge schema/grants/data; real SolarLog payloads; any UI rendering in a browser; any endpoint response; Vercel/FastAPI deployments; `npm run build/lint`; unit behaviour of scrapers against live sites (not run — they write to DB).

## 4. Recommended validation approach for future changes
1. **Calculation changes:** add pure-function tests with the synthetic cases in [05 §5](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) plus real captured intervals (store sanitized fixtures under `tests/fixtures/`).
2. **Scraper changes:** save representative HUPX JSON (incl. a DST `3A/3B` day) and MEMO HTML as fixtures; test parsers offline; never hit production DB in tests (inject a fake `upsert`).
3. **Frontend changes:** `cd frontend && npm run lint && npm run build`; check Daily + Monthly at ≥1024/768/480 px; test date navigation under `TZ=Europe/Skopje`, `UTC`, `America/New_York`; verify empty/error/loading states.
4. **API changes:** grep consumers (`templates/`, `static/js/`, `frontend/`) before changing JSON shapes ([03 §8](03_BACKEND_AND_API.md)).
5. **DB changes:** verify against live schema first; dry-run on a copy; never run destructive SQL without approval.
6. Report exactly what was run and what was not.
