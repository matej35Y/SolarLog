# 15 — Changelog (project history and documentation maintenance)

Add an entry here when a **significant project-level change** is completed or when documentation errors are corrected. Newest first. Dates are absolute.

## A. Documentation changelog
### 2026-11-05 (fifth pass, 17:50 addendum) — owner follow-up
Docs edited: `CLAUDE.md` and `06` (bridge host wording), `13` (R-O12; Q-18/19/22/24/25 annotated; Q-26…Q-28), `14` (ADR-014), `18` (§6), `15`. Facts from the owner: inverter page = 13 inverters, 585 kWp DC; MEMO is the primary source; the InsForge key was reset on 11-02 without updating the static-PC copy; the Mac is abroad (UTC+2); intended host = 24/7 Windows PC. Checked: MEMO returned 24 rows for 2026-10-25 and HUPX failed on `'3B'` every cycle that day; `service.sh` log path points at a stale folder. No code, DB or git state changed.

### 2026-11-05 (fifth pass) — owner answers triaged against evidence
Docs edited: new `18_OWNER_ANSWERS_AND_DECISIONS.md`; `13` (R-D18, R-D19, R-O9, R-O10, R-O11; Q-02/04/05/07/08/10/11/12/13/15/17 annotated; Q-18…Q-25 added); `14` (ADR-013); `PROJECT_CONTEXT_INDEX.md`; `15`. Facts: peak hourly 546.4 kWh and 22 % of producing hours above 357 kWh (the answers' 350 kW ceiling would flag them); `bridge.py` has no `--dry-run`; prices are re-scraped every cycle (≈ 52 requests/day/source, not < 10); the Mac clock (now UTC+2) and the logger clock (CET) differ, mislabelling data for one hour each night (R-O9); bridge uptime 29 %; 401 burst began mid-run on 2026-11-02 00:32; HUPX still returns 24 hourly records. Still unverified: live schema/RLS/grants, plist, nameplate, benchmark, coverage 2026-08-28→09-17. The uploaded answers file sits untracked in `docs/zojalog/` and contains hostnames/IPs — must not be committed. No code, DB or git state changed; edits are uncommitted.

### 2026-11-03 (fourth pass, 23:11) — live InsForge results and scope decision
Docs edited: `CLAUDE.md` (rule 7), `04`, `05`, `13` (R-D3/R-D13/R-D14/R-D15/R-O7, Q-01/Q-06/Q-14), `14` (ADR-012), `16` (§11), `17` (§N and updates), `PROJECT_CONTEXT_INDEX.md`, `15`. Facts: production starts 2026-04-01; no `H0`, no spikes (max 546.4 kWh), no `-9999`; HUPX 2026-10-25 absent (confirmed). Owner decisions: ignore old SQLite history, no migration, minimal changes, no code yet. Schema/RLS/grants still unverified. No code, DB or git state changed.

### 2026-11-03 (third pass, evening) — checkpoint-ref credential review; live-InsForge attempt
Docs edited: `CLAUDE.md` (rule 7), `11` and `13` (R-S10 downgraded to Low — verified, Q-01/Q-14 status), `15`, `16` (§10). **R-S10 result:** the 58 `refs/copilot/checkpoints/*` commits contain no credentials (90 unique blobs; 0 hits; details in 11). **Live InsForge:** a read-only probe from the device sandbox was refused by the egress allowlist (`403` on the InsForge host) before any request reached InsForge — free-plan usage untouched; the same checks were packaged as `zojalog_readonly_check.py` (12 anon-key GETs, budget 16, tested against a local mock) and `zojalog_schema_check.sql` for the owner to run. Q-01, Q-06, Q-14 remain open until then. Those two helper files were delivered in chat and are **not** in the repository.

### 2026-11-03 (second pass) — independent re-verification against the live working tree and GitHub
No source code, database, infrastructure or git state was changed (read-only `git`, copies of SQLite files). Edited: `CLAUDE.md`, `PROJECT_CONTEXT_INDEX.md`, `02`, `03`, `04`, `05`, `06`, `07`, `08`, `09`, `10`, `11`, `12`, `13`, `14`, `15`; added `16_ONBOARDING_VERIFICATION_LEDGER.md`, `17_ONBOARDING_COMPLETION_REPORT.md`. Result: docs 01–15 were **accurate** on every point re-checked (no factual error found); additions are new findings (R-D13…R-D17, R-B9, R-O7, R-O8, R-F13, R-F14, R-S10, R-X1), re-rated R-S4, and corrected details (MockSession size 228 lines; 3B failure split 8/10 + 1 network failure; `requirements.txt` = bridge imports).
**Review of the three Copilot-written legacy docs** (`ZOJALOG_COMPLETE_TECHNICAL_DOCUMENTATION.md` 20,762 B, `CLAUDE_PROJECT_ONBOARDING.md` 6,341 B, `ZOJALOG_ARCHITECTURE.md` 2,811 B; commit `7150ab8`, 2026-11-03 21:00, parent `a5d5698`, local only). They document **only the old GitHub-`main` tree** (SQLite + Bootstrap + FastAPI) as if it were the whole system. Not edited (other branch); do not use as a source for the working tree.
| Aspect | Verdict |
|---|---|
| Routes, energy delta formula, revenue formula, config defaults, CSS values/colors, templates, `railway.json` | ✅ accurate for GitHub `main` (reused knowledge already lives in 03, 05, 07, 08) |
| Scope | ❌ omit the production path (bridge → InsForge → React), the MockSession layer, the `sl-*` design system and the `public_dashboard` |
| "`hupx_prices.db` has no `hourly_prices` table" | ❌ not reproducible: the HEAD-committed file (819,200 B) and the working-tree file (622,592 B) both contain both tables |
| MEMO "tries Excel and alternative URL patterns" | ❌ those paths are dead code; only the HTML POST is live (07 §3) |
| `/api/prices/refresh` "calls `update_price_cache()`" | ⚠ it spawns an additional perpetual loop (R-B1) |
| `migrate_add_source.py` "updates the unique constraint" | ❌ it only adds the column and prints a warning (R-D16) |
| API table | ⚠ lists 21 of 27 routes and describes `add-test-data` as a benign helper; it overwrites today's real energy rows on GitHub `main` |
| "Bootstrap-based design should be extended" | ❌ true only for GitHub `main`; the working tree ships `sl-*` / React (08) |

### 2026-11-03 — Initial knowledge system (engineering onboarding)
Created (no source code, database, infrastructure, or git state was changed):
`CLAUDE.md`; `docs/zojalog/PROJECT_CONTEXT_INDEX.md`; `01_PRODUCT_AND_SYSTEM_OVERVIEW.md`; `02_ARCHITECTURE_AND_DATA_FLOW.md`; `03_BACKEND_AND_API.md`; `04_DATABASE_AND_DATA_INTEGRITY.md`; `05_SOLAR_DOMAIN_AND_CALCULATIONS.md`; `06_HARDWARE_AND_DATA_COLLECTION.md`; `07_SCRAPERS_AND_PRICE_SOURCES.md`; `08_FRONTEND_AND_DESIGN_SYSTEM.md`; `09_APPLICATION_FEATURES_AND_WORKFLOWS.md`; `10_INFRASTRUCTURE_AND_OPERATIONS.md`; `11_SECURITY_AND_CONFIGURATION.md`; `12_TESTING_AND_VALIDATION.md`; `13_KNOWN_LIMITATIONS_AND_RISKS.md`; `14_ARCHITECTURAL_DECISIONS.md`; `15_CHANGELOG.md`.
Basis: direct source investigation. The three earlier documents named in the onboarding brief (`ZOJALOG_COMPLETE_TECHNICAL_DOCUMENTATION.md`, `CLAUDE_PROJECT_ONBOARDING.md`, `ZOJALOG_ARCHITECTURE.md`) **were not present** anywhere in the project folder (searched root, `docs/`, agent directories), so nothing was reused from them (**correction, second pass: they exist as committed files on the local branch `matej35y-solarlog-doc-planning` @ `7150ab8` — see the entry above and the review table**); every statement was verified against code/runtime or tagged [I]/[U].

### Corrections to pre-existing documentation (found 2026-11-03)
| Document | Incorrect / stale statement | Reality |
|---|---|---|
| `README.md` | Storage is SQLite; stack HTML+Bootstrap+Chart.js; data refreshed "via simulated page refresh" | Production DB is InsForge Postgres; primary UI is React/Vite; bridge ingests every 15 min; legacy UI uses custom CSS (no Bootstrap observed in templates) |
| `docs/SCRAPER_GUIDE.md` | Scrapers live in `app/scraper.py`, factory in `app/scraper_factory.py` | `app/services/hupx_scraper.py`, `app/services/scraper_factory.py` |
| `docs/MEMO_INTEGRATION.md` | MEMO scraper is a template; run `python3 migrate_add_source.py`; UI offers "All Sources" | MEMO HTML scraper is live; migration script is dead (imports missing `engine`); UI label is "All" |
| `DESIGN.md` | Describes the design system (Mintlify-inspired, `#18E299`, Geist Mono) | Shipped tokens are `#0aaf72`, Inter + JetBrains Mono ([08](08_FRONTEND_AND_DESIGN_SYSTEM.md)) |
| `frontend/README.md` | – | Unmodified Vite template text |
| `tests/test_scraper_factory.py` hints | mention `app/scraper.py` | removed file |
| `scripts/service.sh` | log path `…/Desktop/bomba/bridge.log` | active log is `ZojaLog/bridge.log` |
| `Dockerfile` / `railway.json` | imply a deployable FastAPI service | `requirements.txt` incomplete; no `.dockerignore` |
These files were **not edited** (outside onboarding scope); the docs above supersede them.

## B. Project timeline (from git, logs and build artefacts)
| Date | Event | Evidence |
|---|---|---|
| 2025-03-12 | Initial commits (`first commit`, `najjak`, `kuka`) — FastAPI + SQLite prototype; `.env`, DBs committed | `git log` |
| 2025-04-25 | five "Update README.md" commits | `git log` |
| 2025-10-04 | Selenium-based HUPX scraping prototype run (artefacts `hupx_scraper.log`, `hupx_data.db`; no `selenium` in requirements) | files |
| 2026-04-14 | `Improving 1`; merge main (keep remote README); branch `feature/refactor-architecture` created at `3282893` | `git log`, reflog |
| ~2026-03 → 2026-10 (approximate, from file mtimes **[I]**) | **Uncommitted** refactor: `app/core|models|services`, InsForge client/schema, `scripts/bridge.py`, React `frontend/`, `public_dashboard`, `AGENTS.md`, `DESIGN.md`, tests relocation | working tree (untracked), file contents |
| 2026-04-01 → 08-28 | Period covered by the legacy SQLite snapshot | `hupx_prices.db` |
| 2026-10-02 | Bridge log begins (service start 12:59); `frontend/dist` built | `bridge.log`, `ls` |
| 2026-10-25 | DST fall-back: HUPX `3B` parse failures (18) | `bridge.log` |
| 2026-11-02 | PR #1 "Add date and month navigation controls" merged into `origin/main` (`a5d5698`) — legacy Jinja UI only; same day: 717 × `401 Unauthorized` from InsForge; `.env.bridge` and `bridge.py` were modified later that day (credential fix **[I]**) | `git`, `bridge.log`, file mtimes |
| 2026-10-31 → 11-03 | 58 local `refs/copilot/checkpoints/*` commits created by 3 Copilot sessions | `git for-each-ref` |
| 2026-11-03 21:00 | Copilot commits the 3 legacy docs on local branch `matej35y-solarlog-doc-planning` (`7150ab8`) | `git show` |
| 2026-11-03 | Onboarding / knowledge system created (first pass); independent re-verification (second pass) | this file |

## C. Maintenance rules
1. Any behaviour change ⇒ update the matching doc (05/06/07/…); a new feature ⇒ [09](09_APPLICATION_FEATURES_AND_WORKFLOWS.md); new risk ⇒ [13](13_KNOWN_LIMITATIONS_AND_RISKS.md) (new `R-xx` ID); decision ⇒ [14](14_ARCHITECTURAL_DECISIONS.md); topic/file moves ⇒ `PROJECT_CONTEXT_INDEX.md`.
2. Re-run the verification commands in [12 §3](12_TESTING_AND_VALIDATION.md) when touching the corresponding area.
3. If docs are mirrored into a claude.ai Project, re-upload changed files — local edits do not update the web Project.
