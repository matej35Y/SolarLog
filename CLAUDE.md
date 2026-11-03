# ZojaLog — Claude Code project memory

> Entry point to the ZojaLog knowledge system. Keep this file short. Detail lives in `docs/zojalog/`.
> Evidence tags used everywhere: **[V]** verified in source/runtime · **[I]** inferred · **[U]** unknown / not verifiable from the repo.
> Last full verification: 2026-11-03, two passes (branch `feature/refactor-architecture`, HEAD `3282893` + large uncommitted tree; second pass re-checked every area against code — evidence: `docs/zojalog/16_*`).

## What ZojaLog is
A monitoring and valuation tool for one solar plant. It reads hourly energy production from a **SolarLog** data logger (HTTP `/getjp`), collects day-ahead electricity prices from **HUPX** (Hungary, JSON API) and **MEMO** (North Macedonia, HTML scrape), stores both as hourly rows, and shows production, price and estimated revenue per hour / day / month.
Names in the wild: repo `SolarLog` (GitHub `matej35Y/SolarLog`), README "Solar Earnings Tracker", React UI brand "SolarLogZOJA", config `APP_NAME` "HUPX Price API". All are the same product.

## Verified architecture — three coexisting paths
1. **PRODUCTION (what actually feeds the dashboard) [V]**: `scripts/bridge.py` (a long-running process on the owner's Mac, launchd service, every 15 min) → SolarLog hardware over Tailscale/LAN + HUPX/MEMO scrapers → **InsForge Postgres** via raw-SQL REST (`/api/database/advance/rawsql`, admin key, `INSERT … ON CONFLICT DO UPDATE`). The **React/Vite app** (`frontend/`) reads InsForge **directly** with `@insforge/sdk` + anon key and computes all analytics **in the browser**. It never calls FastAPI.
2. **Legacy/local FastAPI app [V]**: `app/main.py` (27 routes) + Jinja UI (`/ui`, `/ui/daily`, `/ui/monthly`) + `EnergyDataService` (direct hardware fetch) + `app/services/hupx_scraper.py`. Talks to the same InsForge DB through a hand-written fake SQLAlchemy session (`app/models/database.py`). Deployment status **[U]**; `requirements.txt` is incomplete so the Dockerfile image cannot start it.
3. **Legacy SQLite snapshot [V]**: `hupx_prices.db` (prices 2026-04-01→08-28, energy →08-27). Read-only history; superseded by InsForge.
Also: `frontend/public_dashboard/index.html` — standalone vanilla-JS dashboard pointing at a **different** InsForge host **[U status]**.
**Trees differ:** GitHub `origin/main` (`a5d5698`) is an *older, different codebase* (flat `app/`, Bootstrap UI, SQLite; no bridge/React/docs). The 3 AI-written docs on local branch `matej35y-solarlog-doc-planning` describe only that old tree — **do not use them for the working tree** (`docs/zojalog/15_CHANGELOG.md`).

## Stack
Python 3.13 (`.venv`) · FastAPI 0.115 · uvicorn · pydantic-settings · fastapi-utils · requests · BeautifulSoup · pandas · Jinja2 · InsForge (Postgres BaaS) · React 19 + Vite 5 + Chart.js 4 (react-chartjs-2) + lucide-react · Vercel config for the SPA · Tailscale · macOS launchd.

## Core business concepts (details: `docs/zojalog/05_*`)
- Hour labels `H1…H24`; **H1 = 00:00–01:00 local**. Energy rows are **kWh per hour**; prices are **EUR/MWh**.
- **Revenue(hour) = energy_kWh / 1000 × price_EUR_per_MWh.** Day/month revenue = sum of hourly revenue.
- Production values come from SolarLog **cumulative yield counters (Wh)**; hourly kWh = counter deltas, never raw power.
- Missing price is treated as **0** by every UI/API → revenue silently understated (see risks).
- Price `source` ∈ {`hupx`,`memo`}; energy has no source. Frontend default source = `hupx`.

## Non-negotiable safety rules
1. **Never** reset/delete/overwrite/fabricate/silently recalculate historical production or price data. DB-destructive work needs explicit authorization + recovery plan.
2. **Never read, print, copy or commit** `.env*`, `.insforge/project.json`, keys or tokens. Do not paste keys into code/docs. (Env files are already tracked in git history — see risk R-S4.)
3. **Do not call** `/api/debug/add-test-data`, `/api/debug/add-april-data`, `/api/debug/add-mar14-prices` (they write fabricated rows to production), and do not run anything that scrapes/writes unless explicitly asked: `tests/test_memo_scraper.py`, `tests/test_scraper_direct.py`, `scripts/fill_missing_data.py`, `scripts/restart_scraper.py`, `scripts/scraper_usage_example.py`, `scripts/migrate_*.py`, and any `HUPXScraper/MEMOScraper.scrape_prices()` call — **scrapers persist to the production DB as a side effect**.
4. **Git first**: run `git -c core.fsmonitor=false --no-optional-locks status` before editing. The refactor (`app/core|models|services`, `scripts/`, `tests/`, `frontend/`, `docs/`) is **uncommitted/untracked**; `origin/main` has moved (PR #1 touched legacy UI files also modified locally). Never `pull/checkout/stash/reset/commit/push` without explicit authorization.
5. **Business logic is duplicated** in 4 places — change them together or not at all: `app/main.py` (analysis endpoints), `frontend/src/App.jsx`, `frontend/public_dashboard/index.html`, and the two hourly-energy calculators (`scripts/bridge.py::calculate_hourly_energy` vs `app/services/solarlog_client.py::get_hourly_data`). Production energy uses the **bridge** one.
6. **Design**: authoritative tokens = `:root` in `frontend/src/styles.css` (byte-identical copy in `app/static/css/styles.css` — keep in sync). **`DESIGN.md` (Mintlify-inspired, `#18E299`, Geist Mono) is NOT the shipped design.** Shipped brand is `#0aaf72`, Inter + JetBrains Mono. Reuse `sl-*` classes; don't introduce new visual styles.
7. **Historical data**: production (InsForge) starts **2026-04-01** (verified live 2026-11-03). Older history in the HEAD-committed `hupx_prices.db` (labels `H0…H23`, spike rows, junk prices; R-D13…R-D15) is **deliberately ignored — owner decision, no migration** (ADR-012); don't delete that file and don't relabel/clean stored data without approval. Next phase = rules for *future* ingestion only, no code until a plan is agreed. Local `refs/copilot/*` checkpoint refs hold `.env*` snapshots; scanned: **no credentials** (R-S10) — still avoid `git push --mirror`.
8. **Dates/timezones**: don't call `toISOString()` on a local-midnight `Date` (breaks day navigation east of UTC — verified bug R-F1). Use noon-anchored or string-based date math.
9. Validate: don't claim anything was tested unless it was run; report unverified items.

## Commands
```bash
# Bridge (production ingester) — run from repo root (reads ./.env.bridge, ./.device_cache)
python3 scripts/bridge.py
./scripts/service.sh {start|stop|restart|status|logs}   # launchd label com.solarlog.bridge (plist not in repo)

# FastAPI legacy app — from repo root, requires .insforge/project.json; NOTE vite proxy expects :8000
source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

# React frontend
cd frontend && npm install && npm run dev        # also: build | lint | preview
# env (names only): VITE_INSFORGE_URL, VITE_INSFORGE_ANON_KEY
```
Env var **names** — FastAPI: `DEBUG_MODE, CACHE_TIMEOUT, SCRAPER_NAME, ENERGY_DEVICE_IP, ENERGY_DEVICE_TAILSCALE_IP, USE_TAILSCALE_FIRST`; bridge: `INSFORGE_URL, INSFORGE_ANON_KEY, INSFORGE_API_KEY, ENERGY_DEVICE_IP, ENERGY_DEVICE_TAILSCALE_IP, USE_TAILSCALE_FIRST, SOLARLOG_CANDIDATES`.
There is **no automated test suite** (`tests/` = manual, partly broken diagnostics; see doc 12).

## Documentation map — read before changing code
Start at **`docs/zojalog/PROJECT_CONTEXT_INDEX.md`** (master map: 34 topics → files → source). Then:

| If you are touching… | Read first |
|---|---|
| any user-visible feature | `09_APPLICATION_FEATURES_AND_WORKFLOWS.md` (feature → code map) |
| energy/price/revenue maths | `05_SOLAR_DOMAIN_AND_CALCULATIONS.md` |
| bridge, hardware, Tailscale | `06_HARDWARE_AND_DATA_COLLECTION.md` |
| HUPX/MEMO scraping | `07_SCRAPERS_AND_PRICE_SOURCES.md` |
| tables, SQL, RLS, migrations | `04_DATABASE_AND_DATA_INTEGRITY.md` |
| FastAPI routes | `03_BACKEND_AND_API.md` |
| React/Jinja UI, CSS, charts | `08_FRONTEND_AND_DESIGN_SYSTEM.md` |
| deploy/run/ops | `10_INFRASTRUCTURE_AND_OPERATIONS.md`, `11_SECURITY_AND_CONFIGURATION.md` |
| "is this safe/known?" | `13_KNOWN_LIMITATIONS_AND_RISKS.md` (risk register R-xx) |
| "how do we know this is true?" / which tree or snapshot | `16_ONBOARDING_VERIFICATION_LEDGER.md` (evidence log), `17_ONBOARDING_COMPLETION_REPORT.md` |

## Maintaining knowledge
- New fact → put it in the matching doc, not here. Rule changed → edit the doc (no contradictory copies). Doc error found → fix it and log it in `15_CHANGELOG.md`.
- Update `PROJECT_CONTEXT_INDEX.md` when a topic/file moves; this file only for durable project-wide rules; `14_ARCHITECTURAL_DECISIONS.md` for decisions; `15_CHANGELOG.md` for significant changes.
- If docs are mirrored into a claude.ai Project, list which files changed — local edits do **not** update the web Project.
- InsForge-specific work: see `AGENTS.md` (InsForge skill block); skills live in `.claude/skills` (symlinks).
