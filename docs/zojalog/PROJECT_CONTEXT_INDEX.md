# ZojaLog — Project Context Index (master map)

**Purpose:** let a future engineer (human or AI) find any fact about ZojaLog without guessing. Start here, then follow the links. `CLAUDE.md` (repo root) is the short entry point and rules; this file is the map; `01…15` hold the detail.
**Verified:** 2026-11-03 · branch `feature/refactor-architecture` @ `3282893` + large uncommitted working tree · `origin/main` @ `a5d5698`. **Second pass 2026-11-03:** re-verified against the live working tree and GitHub `main` — evidence in [16](16_ONBOARDING_VERIFICATION_LEDGER.md), summary in [17](17_ONBOARDING_COMPLETION_REPORT.md).
**Evidence tags:** **[V]** verified in source/runtime · **[I]** inferred · **[U]** unknown / needs access. Onboarding made **no** changes to source, DB, infra or git.

## How to use this knowledge system
1. Read `CLAUDE.md` → this index → the doc(s) for the area → **the actual source** (docs can drift; code wins).
2. Before changing a component, check *Depends on* here and the impact table in [02 §6](02_ARCHITECTURE_AND_DATA_FLOW.md).
3. After changing it, update the matching doc, [13](13_KNOWN_LIMITATIONS_AND_RISKS.md) if risks change, [14](14_ARCHITECTURAL_DECISIONS.md) for decisions, [15](15_CHANGELOG.md) for significant changes.

### Documents
| File | Contents |
|---|---|
| [01 Product & system overview](01_PRODUCT_AND_SYSTEM_OVERVIEW.md) | purpose, users, terminology, raw vs calculated data, operating snapshot |
| [02 Architecture & data flow](02_ARCHITECTURE_AND_DATA_FLOW.md) | 3 paths, Mermaid diagrams, dependency/impact map |
| [03 Backend & API](03_BACKEND_AND_API.md) | FastAPI app, 27 routes, startup loops, response shapes |
| [04 Database & integrity](04_DATABASE_AND_DATA_INTEGRITY.md) | Postgres schema/RLS, MockSession, legacy SQLite, integrity mechanisms |
| [05 Solar domain & calculations](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) | energy algorithms (run-verified), revenue, aggregation differences |
| [06 Hardware & data collection](06_HARDWARE_AND_DATA_COLLECTION.md) | SolarLog protocol, bridge cycle, reliability from logs |
| [07 Scrapers & price sources](07_SCRAPERS_AND_PRICE_SOURCES.md) | HUPX, MEMO, factory, DST defect, dead code |
| [08 Frontend & design system](08_FRONTEND_AND_DESIGN_SYSTEM.md) | React SPA, legacy UI, tokens/components/states |
| [09 Features & workflows](09_APPLICATION_FEATURES_AND_WORKFLOWS.md) | **feature → code map**, what doesn't exist, cheat-sheets |
| [10 Infrastructure & operations](10_INFRASTRUCTURE_AND_OPERATIONS.md) | inventory, deploy artefacts, run/log/runbooks |
| [11 Security & configuration](11_SECURITY_AND_CONFIGURATION.md) | env names, auth model, findings |
| [12 Testing & validation](12_TESTING_AND_VALIDATION.md) | state of tests, onboarding checks, how to validate |
| [13 Limitations, risks, questions](13_KNOWN_LIMITATIONS_AND_RISKS.md) | risk register R-xx, open questions Q-xx |
| [14 Architectural decisions](14_ARCHITECTURAL_DECISIONS.md) | ADR-001…010 |
| [15 Changelog](15_CHANGELOG.md) | doc corrections, project timeline |
| [16 Verification ledger](16_ONBOARDING_VERIFICATION_LEDGER.md) | **evidence log**: what was checked against which source, GitHub-vs-working-tree differences, data-integrity findings with queries, review of the 3 legacy docs |
| [17 Completion report](17_ONBOARDING_COMPLETION_REPORT.md) | onboarding report: product, architecture, data flow, design, business logic, readiness, unknowns |

### Quick routing for common tasks
| Task | Go to |
|---|---|
| "Dashboard shows zeros/€0" | [09 §5](09_APPLICATION_FEATURES_AND_WORKFLOWS.md), [06 §5](06_HARDWARE_AND_DATA_COLLECTION.md), R-D3/R-D5 |
| Add a KPI/chart | [08 §6](08_FRONTEND_AND_DESIGN_SYSTEM.md), [05 §7](05_SOLAR_DOMAIN_AND_CALCULATIONS.md), [09](09_APPLICATION_FEATURES_AND_WORKFLOWS.md) |
| Change energy/revenue logic | [05 §9](05_SOLAR_DOMAIN_AND_CALCULATIONS.md), [06 §7](06_HARDWARE_AND_DATA_COLLECTION.md) |
| Add a price source | [07 §5](07_SCRAPERS_AND_PRICE_SOURCES.md) |
| Touch the DB | [04 §7](04_DATABASE_AND_DATA_INTEGRITY.md) |
| Bridge down / 401 | [10 §6](10_INFRASTRUCTURE_AND_OPERATIONS.md) |
| Is X safe to run? | `CLAUDE.md` rule 3, [12 §2](12_TESTING_AND_VALIDATION.md) |
| "Which tree / branch / snapshot is authoritative?" | [16 §3](16_ONBOARDING_VERIFICATION_LEDGER.md), R-O1/R-O7/R-O8 in [13](13_KNOWN_LIMITATIONS_AND_RISKS.md) |
| Historical data looks wrong (hours shifted, spikes, junk prices) | R-D13…R-D15 in [13](13_KNOWN_LIMITATIONS_AND_RISKS.md), [16 §5](16_ONBOARDING_VERIFICATION_LEDGER.md) |

---
## Topic index (34 topics)
Format: **what/why** · *components* · `source` · docs · depends on (topic #).

### 1. Product overview and terminology
Tracks hourly production of one solar plant and values it at HUPX/MEMO day-ahead prices; terms: `Hn` labels, kWh vs EUR/MWh, cumulative yield, bridge, source. · *whole system* · `README.md`, UI copy · [01](01_PRODUCT_AND_SYSTEM_OVERVIEW.md) · depends: –.

### 2. System architecture
Three paths: production (bridge → InsForge → React), legacy FastAPI, legacy SQLite; `public_dashboard` aside. · *bridge, InsForge, React, FastAPI* · `scripts/bridge.py`, `frontend/src/App.jsx`, `app/main.py` · [02](02_ARCHITECTURE_AND_DATA_FLOW.md) · depends: 11, 13, 5.

### 3. Repository structure
```
ZojaLog/
├─ CLAUDE.md                      project memory (this system's entry point)      [new]
├─ AGENTS.md                      InsForge block for coding agents
├─ README.md                      (outdated: says SQLite)
├─ DESIGN.md                      Mintlify-inspired reference — NOT the shipped design
├─ Dockerfile, railway.json       FastAPI deploy artefacts (incomplete deps)
├─ requirements.txt               3 packages only
├─ quick_restart.sh               runs scripts/restart_scraper.py (writes prod DB)
├─ skills-lock.json, .claude|.agents|.augment|… /skills   InsForge agent skills (symlinks)
├─ .env*, .insforge/project.json  secrets — never read/commit (some already tracked!)
├─ hupx_prices.db                 legacy SQLite snapshot (tracked path; working copy 622,592 B ≠ HEAD copy 819,200 B — see 04 §5)
├─ bridge.log, bridge.err.log     bridge runtime logs (git-ignored)
├─ .device_cache                  last good SolarLog address (bridge)
├─ app/                           legacy FastAPI application
│  ├─ main.py                     27 routes, startup loops, analysis maths
│  ├─ core/config.py              Settings
│  ├─ models/{database.py,insforge_client.py}   MockSession + raw SQL client
│  ├─ services/{solarlog_client.py,hupx_scraper.py,scraper_factory.py}
│  ├─ templates/{index,daily,monthly}.html      legacy Jinja UI
│  ├─ static/{css/styles.css,js/daily.js,js/monthly.js}
│  └─ api/                        empty package
├─ scripts/                       bridge.py (production), service.sh, init_schema.sql,
│                                 migrate_*.py, fill_missing_data.py, restart_scraper.py, …
├─ tests/                         6 manual diagnostic scripts (no suite)
├─ docs/{MEMO_INTEGRATION.md,SCRAPER_GUIDE.md}  stale guides ; docs/zojalog/  ← this system
├─ frontend/                      React 19 + Vite 5 SPA
│  ├─ src/{main.jsx,App.jsx,index.css,styles.css,App.css(unused),assets}
│  ├─ src/{pages,components,hooks,theme}/       empty
│  ├─ public_dashboard/index.html standalone dashboard (other InsForge host)
│  ├─ vite.config.js, vercel.json, package.json, eslint.config.js, dist/ (ignored)
└─ venv/, .venv/                  two Python 3.13 environments
```
**Git topology [V, 2026-11-03]:** branch `feature/refactor-architecture` @ `3282893` (17 modified, 29 deleted, 71 untracked files vs HEAD). 4 local branches are **not on origin**; `origin/main` @ `a5d5698` is a *different, older codebase* (flat `app/`, Bootstrap UI, SQLite; no bridge/React/docs). Local branch `matej35y-solarlog-doc-planning` @ `7150ab8` holds the three AI-written legacy docs (they describe only the old tree — [15 §A](15_CHANGELOG.md)). 58 local `refs/copilot/checkpoints/*` commits exist (R-O8). Module import graph: [02 §8](02_ARCHITECTURE_AND_DATA_FLOW.md).
· [02](02_ARCHITECTURE_AND_DATA_FLOW.md), [10](10_INFRASTRUCTURE_AND_OPERATIONS.md) · depends: 2.

### 4. Runtime initialization
- **Bridge:** `main()` → `ensure_tailscale()`, build `InsForgeClient`, `SolarLogFetcher` (candidate list + cache), scrapers → infinite `run_cycle` + 15-min sleep. `scripts/bridge.py` L516–543.
- **FastAPI:** module import (config, scraper, `EnergyDataService`, templates, static) + 3 startup hooks. `app/main.py` L1–100.
- **React:** `main.jsx` → `App` → `Dashboard` effects (latest date, fetch, 5-min timer).
· [03 §2–3](03_BACKEND_AND_API.md), [06 §3](06_HARDWARE_AND_DATA_COLLECTION.md), [08 §2](08_FRONTEND_AND_DESIGN_SYSTEM.md) · depends: 24.

### 5. Frontend architecture
Single-file React component tree, no router/state lib; direct InsForge SDK; three UIs coexist. · *React, legacy Jinja, public_dashboard* · `frontend/src/App.jsx`, `app/templates/*`, `app/static/js/*` · [08](08_FRONTEND_AND_DESIGN_SYSTEM.md) · depends: 4, 10, 23.

### 6. UI/UX and design system
Light theme, brand `#0aaf72`, Inter + JetBrains Mono, `sl-*` components, KPI/chart/table card anatomy. Authoritative: `:root` in `styles.css`. · *CSS, templates, React* · `frontend/src/styles.css`, `index.css`, `app/static/css/styles.css` · [08 §5–6](08_FRONTEND_AND_DESIGN_SYSTEM.md) · depends: 5.

### 7. Backend architecture
Legacy FastAPI: routes + background loops + scrapers + MockSession; not in the production read path. · `app/**` · [03](03_BACKEND_AND_API.md) · depends: 10, 12, 14, 24.

### 8. FastAPI endpoints
27 routes (3 UI, 8 debug incl. 3 that write fabricated data). Only `/api/analysis/by-date` and `/by-month` have in-repo consumers. · `app/main.py` · [03 §4](03_BACKEND_AND_API.md) · depends: 7, 18–21.

### 9. SQLite database
Legacy only: **two different `hupx_prices.db` files** — working copy (2026-04-01→08-28; 7,155 price + 2,490 energy rows) and the HEAD-committed copy (2025-01-22→2026-04-15; 10,847 + 8,625 rows; contains `H0` labels and anomalies, R-D13…R-D16 — **not in production, ignored by owner decision**). Production is **Postgres on InsForge**. · `hupx_prices.db`, `scripts/migrate_to_insforge.py` · [04 §5](04_DATABASE_AND_DATA_INTEGRITY.md) · depends: –.

### 10. Data models
Tables `hourly_prices`, `energy_generation`; Python shells `HourlyPrice`, `EnergyGeneration`. · `scripts/init_schema.sql`, `app/models/database.py` · [04 §1, §3](04_DATABASE_AND_DATA_INTEGRITY.md) · depends: 9, 2.

### 11. SolarLog hardware integration
HTTP `POST /getjp` with `preval=none;{json}`; key `776` history; discovery via Tailscale/LAN candidates. · `scripts/bridge.py::SolarLogFetcher`, `app/services/solarlog_client.py` · [06](06_HARDWARE_AND_DATA_COLLECTION.md), [05 §2](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) · depends: 25.

### 12. EnergyDataService
Legacy hardware client + hourly calc + `save_data_to_db` (updates don't persist). · `app/services/solarlog_client.py` · [05 §4](05_SOLAR_DOMAIN_AND_CALCULATIONS.md), [06 §1–2](06_HARDWARE_AND_DATA_COLLECTION.md) · depends: 11, 17, 10.

### 13. Data collection and synchronization
Bridge cycle: energy (today+yesterday, ≤14-day gap backfill), prices (today, gaps, tomorrow after 13:00), upsert. · `scripts/bridge.py::run_cycle` · [06 §3](06_HARDWARE_AND_DATA_COLLECTION.md) · depends: 11, 14, 17.

### 14. Electricity price scraping
HUPX JSON API and MEMO HTML POST; DST defect; FastAPI scrapers persist as side effect. · `scripts/bridge.py`, `app/services/hupx_scraper.py` · [07](07_SCRAPERS_AND_PRICE_SOURCES.md) · depends: 15.

### 15. ScraperFactory and source configuration
Registry `hupx|memo|example`, singleton cache, `SCRAPER_NAME`. Bridge doesn't use it. · `app/services/scraper_factory.py`, `app/core/config.py` · [07 §4](07_SCRAPERS_AND_PRICE_SOURCES.md) · depends: 14, 24.

### 16. Solar-energy business logic
Revenue = spot × energy; hour labels; production-hours concept; missing = 0. · `main.py`, `App.jsx`, `public_dashboard`, `bridge.py` · [05](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) · depends: 17–21.

### 17. Cumulative readings and energy calculations
Counter deltas per channel, reset handling, first-sample baseline, bucket `H{hour+1}`. · `bridge.py::calculate_hourly_energy` L48, `solarlog_client.py::get_hourly_data` L102 · [05 §3–5](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) · depends: 11.

### 18. Hourly analytics
24-row hourly table: kWh, price, revenue, share-of-peak. · `App.jsx::dailyAnalysis` L285; `main.py` L531–577 · [05 §6–7](05_SOLAR_DOMAIN_AND_CALCULATIONS.md), [09 F1](09_APPLICATION_FEATURES_AND_WORKFLOWS.md) · depends: 16, 17, 14.

### 19. Daily analytics
Day totals/averages (three "Avg. price" definitions). · `App.jsx` L285–331; `main.py::get_price_energy_analysis` L448; `public_dashboard::calcSummary` · [05 §7](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) · depends: 18.

### 20. Monthly analytics
Per-day rows + month totals; day inclusion rules differ per implementation. · `App.jsx::monthlyAnalysis` L334; `main.py::get_monthly_analysis` L649; `public_dashboard::aggregateMonthly` · [05 §7](05_SOLAR_DOMAIN_AND_CALCULATIONS.md), [09 F2](09_APPLICATION_FEATURES_AND_WORKFLOWS.md) · depends: 19.

### 21. Revenue calculations
`kWh/1000 × EUR/MWh`, summed; estimate only; missing price ⇒ 0. · same files as 18–20 · [05 §6](05_SOLAR_DOMAIN_AND_CALCULATIONS.md), [14 ADR-007](14_ARCHITECTURAL_DECISIONS.md) · depends: 14, 17.

### 22. Chart.js implementations
React: `react-chartjs-2` combo bar+line, dual axes; legacy: Chart.js 4.4 CDN with area/bar/line; `public_dashboard` inline. · `App.jsx` L416–547, `daily.js` L166–289, `monthly.js` L177+ · [08 §3–5](08_FRONTEND_AND_DESIGN_SYSTEM.md) · depends: 5, 6.

### 23. API communication
React → InsForge SDK (`from().select().eq/gte/lte`); legacy UI → `fetch('/api/analysis/…')`; `public_dashboard` → REST `/api/database/records/<t>`; bridge → `/api/database/advance/rawsql`. · `App.jsx`, `static/js/*`, `bridge.py`, `insforge_client.py` · [02](02_ARCHITECTURE_AND_DATA_FLOW.md), [04 §2](04_DATABASE_AND_DATA_INTEGRITY.md), [03 §4–5](03_BACKEND_AND_API.md) · depends: 7, 10.

### 24. Configuration and environment variables
Names: see `CLAUDE.md` / [11 §1](11_SECURITY_AND_CONFIGURATION.md). `.env*` never to be read/committed. · `app/core/config.py`, `bridge.py` top, `App.jsx` L13–14, `.env.example` · [11](11_SECURITY_AND_CONFIGURATION.md) · depends: –.

### 25. Infrastructure and networking
Mac + launchd, Tailscale, SolarLog LAN, InsForge, Vercel (config only), GitHub. · `scripts/service.sh`, `bridge.py::ensure_tailscale`, `frontend/vercel.json` · [10 §1–2](10_INFRASTRUCTURE_AND_OPERATIONS.md) · depends: 11.

### 26. Deployment and operation
How to run each part, runbooks, deploy-artefact defects (deps, `.dockerignore`). · `Dockerfile`, `railway.json`, `scripts/service.sh`, `frontend/package.json` · [10 §3–6](10_INFRASTRUCTURE_AND_OPERATIONS.md) · depends: 24, 25.

### 27. Security
No auth; open CORS; SQL injection; permissive RLS; tracked env files; hard-coded keys. · `app/main.py` L28, `app/models/database.py`, `scripts/init_schema.sql`, git history · [11](11_SECURITY_AND_CONFIGURATION.md) · depends: 24, 10.

### 28. Error handling and troubleshooting
Scrapers/bridge swallow errors and return empty; FastAPI wraps in 500; UI shows generic errors; log signatures in [06 §5](06_HARDWARE_AND_DATA_COLLECTION.md). · `main.py`, `bridge.py`, `App.jsx` L79, L217 · [03 §6](03_BACKEND_AND_API.md), [06 §6](06_HARDWARE_AND_DATA_COLLECTION.md), [09 §5](09_APPLICATION_FEATURES_AND_WORKFLOWS.md) · depends: 13, 14.

### 29. Testing and validation
No automated suite; broken/side-effecting diagnostics; onboarding checks and recommended practice. · `tests/*` · [12](12_TESTING_AND_VALIDATION.md) · depends: –.

### 30. Technical limitations
Hourly only; single plant; estimate-only revenue; no timestamps/TZ; DST; client-side aggregation. · [13 §G](13_KNOWN_LIMITATIONS_AND_RISKS.md) · depends: 10, 16.

### 31. Known risks and unresolved questions
Risk register R-S/D/B/O/F/X/T and open questions Q-01…17. · [13](13_KNOWN_LIMITATIONS_AND_RISKS.md) · depends: all.

### 32. Development workflows
1) understand request → 2) read `CLAUDE.md`/this index/docs → 3) trace real code → 4) check dependencies ([02 §6](02_ARCHITECTURE_AND_DATA_FLOW.md)) → 5) plan (files, unchanged parts, DB/API impact, regressions, validation) → 6) focused change → 7) validate ([12 §4](12_TESTING_AND_VALIDATION.md)) → 8) report (what/why/files/tested/unverified/docs) → 9) update docs. **Git:** `git -c core.fsmonitor=false --no-optional-locks status` first; refactor is uncommitted (R-O1); no pull/checkout/stash/reset/commit/push without approval. Commands: [10 §4](10_INFRASTRUCTURE_AND_OPERATIONS.md). · depends: 31.

### 33. Architectural decisions
ADR-001…010 (storage, schema keys, bridge ingestion, client-side analytics, Tailscale, MockSession, revenue model, shared CSS, scraper split, price sources). · [14](14_ARCHITECTURAL_DECISIONS.md) · depends: 2.

### 34. Change history and documentation maintenance
Doc changelog, corrections to README/guides/DESIGN.md, project timeline, update rules. · [15](15_CHANGELOG.md) · depends: –.

---
## Files to refresh in a claude.ai Project (if you mirror docs there)
Upload/replace: `CLAUDE.md`, `docs/zojalog/PROJECT_CONTEXT_INDEX.md` and `01…17`. Files amended in the 2026-11-03 second pass are listed in [15 §A](15_CHANGELOG.md). Local edits do **not** update the web Project; the Project attached to the onboarding session ("How to use Claude") is a generic sample and was **not** written to.
