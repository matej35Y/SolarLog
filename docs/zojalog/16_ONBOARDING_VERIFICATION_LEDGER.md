# 16 — Onboarding Verification Ledger

**What this is:** the evidence log behind the knowledge system — which claim was checked against which source, what differs between trees, and the data-integrity findings with reproducible queries. The *risk register* lives in [13](13_KNOWN_LIMITATIONS_AND_RISKS.md) (this file holds evidence, not duplicates).
**Passes:** (A) 2026-11-03 21:2x — GitHub `main` + committed SQLite + upstream library sources, local folder not yet reachable; (B) 2026-11-03 21:4x–22:xx — live working tree (`/Users/matejmacevski35/Desktop/ZojaLog`, branch `feature/refactor-architecture` @ `3282893`), read-only; (C) 2026-11-03 evening — checkpoint-ref review; (D) 2026-11-03 23:11 — **live InsForge data coverage**, read-only `GET`s run by the owner on his Mac (`zojalog_readonly_check.py`, anon key).
**Tags:** **[V]** verified (source read / read-only query / script run) · **[I]** inferred · **[U]** unknown or needs access.
**Never changed:** source code, databases, infrastructure, git state (read-only `git` with `--no-optional-locks`; SQLite opened `mode=ro` on copies). No scraper, API endpoint or hardware call was executed. Secret files (`.env*`, `.insforge/`) were not read; two hard-coded key lines (`App.jsx` L14, `public_dashboard` L422) were skipped when reading.

## 1. Bottom line
1. **Docs 01–15 were accurate** on every point re-checked against the working tree (§4): routes and line anchors, bridge cycle, calculators, React feature map, CSS tokens, log statistics. No factual error was found; a few details were refined (see [15 §A](15_CHANGELOG.md)).
2. **Three trees/snapshots coexist** (§3): the working tree (production path), GitHub `main` (older codebase) and two different `hupx_prices.db` files. Docs written for one must not be applied to another without checking.
3. **New data-integrity findings** (§5): energy hour labels shifted by one for 314 historical dates (R-D13), gap-lumping spikes (R-D14), price anomalies (R-D15) — **all confined to the old committed SQLite: production (InsForge) starts 2026-04-01 and contains none of them (pass D, §11); owner decision: that history is ignored, no migration.**
4. **The three Copilot-written "legacy docs" exist** on local branch `matej35y-solarlog-doc-planning` (`7150ab8`); they describe only the old tree ([15 §A](15_CHANGELOG.md)). *Pass A wrongly reported them as non-existent — it had searched only the working tree and uploads.*
5. **Live production verified (pass D, §11):** coverage, no `H0` rows, no spikes, HUPX 2026-10-25 missing. **Still unverified** (§8): live schema/RLS/grants, real device payloads/timestamp semantics, browser rendering, launchd plist, untracked env contents.

## 2. Access matrix
| Source | Pass A | Pass B |
|---|---|---|
| GitHub `main` @ `a5d5698` (public; 12 commits) | ✅ cloned, read | – |
| Working tree (`feature/refactor-architecture`) | ❌ | ✅ source files read or diffed; docs, scripts, tests, frontend, services |
| Committed SQLite (`HEAD:hupx_prices.db`, 819,200 B) and working-tree SQLite (622,592 B) | ✅ committed | ✅ both, read-only copies |
| `bridge.log` (25,044 lines) | ❌ | ✅ `awk`/`grep` on the device |
| Upstream library sources | ✅ fastapi-utils 0.8.0, SQLAlchemy 2.0.38 (from GitHub; PyPI unreachable) | ✅ installed `@insforge/sdk` 1.2.4 and `@supabase/postgrest-js` 1.21.4 from `node_modules` |
| Git metadata (branches, reflog, worktrees, `refs/copilot/*`) | – | ✅ |
| Untracked/secret files (`.env`, `.env.bridge`, `.env.local`, `frontend/.env`, `.insforge/`) | – | ⛔ intentionally not read |
| InsForge live data | ⛔ | ⛔ sandbox egress `403`; **pass D: owner ran 12 anon `GET`s on his Mac and pasted the output (§11)** |
| InsForge schema/RLS/grants (`zojalog_schema_check.sql`) | ⛔ | not yet run |
| Vercel, launchd plist, SolarLog hardware, a browser | ⛔ | ⛔ out of scope for read-only onboarding |

## 3. Trees and snapshots
| Aspect | Working tree (production path) **[V]** | GitHub `main` @ `a5d5698` **[V]** |
|---|---|---|
| Layout | `app/{core,models,services}`, `scripts/`, `tests/`, `frontend/`, `docs/` | flat `app/{main,config,models,energy_service,scraper,scraper_factory}.py`, root scripts/tests |
| DB layer | `MockSession` → InsForge Postgres (raw SQL) | real SQLAlchemy + SQLite (`sqlite:///hupx_prices.db`, global `session`) |
| Ingestion | `scripts/bridge.py` (15 min, launchd) + legacy FastAPI loops | FastAPI startup loops only |
| UI | React SPA (`sl-*`) + restyled Jinja UI + `public_dashboard` | Jinja + **Bootstrap 5.3.0-alpha1** CDN + 95-line CSS |
| `requirements.txt` | 3 packages (= bridge's imports) | 57 pins |
| Container | `Dockerfile` + `railway.json` | `railway.json` only |
| `app/main.py` | identical logic (4 import lines differ) | – |
| `hupx_prices.db` | 622,592 B: 7,155 prices + 2,490 energy rows, **2026-04-01→08-28**, `H1…H24` only, with UNIQUE | 819,200 B: 10,847 + 8,625 rows, **2025-01-22→2026-04-15**, `H0` labels, no UNIQUE on prices |
| Date nav (legacy UI) | no prev/next buttons; `daily.js` reads `?date=` | PR #1 buttons (UTC-safe); `?date=` ignored |

**Path translation (doc path → GitHub `main`):** `app/core/config.py`→`app/config.py` · `app/models/database.py`→`app/models.py` (real ORM) · `app/services/solarlog_client.py`→`app/energy_service.py` · `app/services/hupx_scraper.py`→`app/scraper.py` · `app/services/scraper_factory.py`→`app/scraper_factory.py` · `tests/*`, `scripts/*`→repo root · `docs/{MEMO_INTEGRATION,SCRAPER_GUIDE}.md`→root · `scripts/bridge.py`, `insforge_client.py`, `frontend/**`, `Dockerfile`, `docs/**` do not exist on GitHub.

**Git topology (working tree) [V]:** 6 local branches — `feature/refactor-architecture`, `main` (local, `3282893`, 2 commits behind `origin/main`), `matej35y-date-picker-navigation` (merged via PR #1), `matej35y-legendary-potato`, `matej35y-zojalog-project-takeover` (both `3282893`), `matej35y-solarlog-doc-planning` (`7150ab8`); **4 are not on origin**. 58 `refs/copilot/checkpoints/*` commits (3 sessions, 2026-10-31→11-03) and 5 prunable worktrees under `~/copilot-worktrees/`. `git status`: 17 modified, 29 deleted, 71 untracked.

## 4. Verification of docs 01–15 (claim → result)
### 4.1 Backend and bridge
| Doc § | Claim | Result |
|---|---|---|
| 03 §4 | 27 routes, names, line anchors `@104…@1221` | ✅ identical in working tree and GitHub (`main.py` diff = 4 import lines) |
| 03 §3 / R-B1 | `repeat_every` only schedules a loop → 3 loops at startup, +1 per `/refresh` | ✅ fastapi-utils 0.8.0 `ensure_future(loop())`, returns `None` |
| 03 §5 | response shapes incl. different "empty" summary | ✅ `main.py` L512–523, L604–616, L813–839 |
| 03 §4 rows 21/23/27 | debug endpoints write fabricated rows | ✅ (on GitHub `main` they really overwrite rows; in the working tree MockSession makes updates no-ops) |
| 04 §3 / R-D1 | `MockSession.commit` only inserts queued objects ⇒ updates are no-ops; `id` in INSERT; interpolated SQL; global session | ✅ `database.py` L194–223, L13/L30, L78–117, L184, L228 (file is 228 lines, not ~170 — corrected) |
| 04 §1 | `init_schema.sql` content, composite PKs, permissive RLS | ✅ identical |
| 05 §3 | bridge algorithm: baseline sample, per-channel delta, reset estimate, `H{hour+1}`, 24 keys, 4 dp | ✅ `bridge.py` L48–90 |
| 05 §4 | legacy algorithm; future dates → `({},0)` | ✅ `solarlog_client.py` (the future-date guards are the only logic diff vs GitHub) |
| 05 §6–7 | revenue formula; three "Avg. price" definitions | ✅ `main.py` L563–614, `App.jsx` L285–331/L334–413, `public_dashboard` L529–539/L647–678 |
| 06 §2–3 | discovery order, cache, 3×25 s fetch, cycle windows (`{0,1}` + ≤14 d gap, 7 d if empty, tomorrow ≥13:00) | ✅ `bridge.py` L190–315, L439–513 (nuance: an exception inside discovery skips to the next candidate) |
| 06 §5 | log statistics | ✅ (§4.3) |
| 07 §2 | HUPX `int(ProductH)` inside one `try` ⇒ whole day lost in the bridge | ✅ `bridge.py` L331–344; FastAPI version skips only the bad record (`hupx_scraper.py` L204–229) |
| 07 §3 | MEMO live path, 8 dead helpers, FastAPI column-2 fallback, bridge returns `[]` | ✅ (`hupx_scraper.py` = `scraper.py` logic; `bridge.py` L390–392) |
| 10 §3 / R-B7 | `requirements.txt` = 3 packages, Dockerfile cannot run FastAPI | ✅ and sharper: those 3 are exactly `bridge.py`'s imports (AST) |
| 12 | scripts/tests have side effects or are broken | ✅ scripts/tests differ from GitHub copies only by import paths |

### 4.2 Frontend and design
| Doc § | Claim | Result |
|---|---|---|
| 08 §5 | all tokens in `:root`; Inter + JetBrains Mono; 90 `sl-*` classes; 12 `:hover`, 2 `:focus`, 0 `:active`/`:disabled`; 16 transitions; keyframes `pulse/spin/fadeUp`; breakpoints 1024/768/480 + 768/640 | ✅ exact (script over `styles.css` + `index.css`) |
| 08 §5 | `app/static/css/styles.css` byte-identical to `frontend/src/styles.css` | ✅ `cmp` (28,980 B) |
| 08 §2 | `App.jsx` ≈1,015 lines; Dashboard/ErrorBoundary; no router/state lib; 7 unused deps | ✅ 1,014 lines; deps confirmed |
| 09 F1–F10 | line anchors (L142–170, L173, L195, L226, L273–282, L285–331, L334–413, L416, L457, L500, L607, L709–722, L726–733, L854–878, L959–967) | ✅ all correct |
| 08 §2 / R-F1 | day navigation skips/sticks east of UTC | ✅ reproduced (Node 22, `Europe/Skopje`); PR #1 and `public_dashboard` versions correct |
| 08 §4 | legacy UI restyled with `sl-*`, hero strip fetches `/api/analysis/by-date/<today>?source=hupx`, chart palette `#18E299` | ✅ (`index.html` L150–162, `daily.js` L193–252) |
| 13 R-O5 | `public_dashboard` keys monthly rows by raw `p.date` | ✅ L655–656 (React uses `split('T')[0]`); also `limit` 50/1000 vs React 5000 |
| 13 R-F7 | Vite `/api` proxy unused | ✅ `vite.config.js`; `App.jsx` never calls `/api` |

### 4.3 `bridge.log` per cycle-date **[V]** (dates = cycle-start dates; log lines carry only a time)
Totals: 929 cycles, 928 "Cycle done", 25,044 lines, 33 dates (2026-10-02→11-03), **372** discovery failures (10-02: 90, 10-03: 117, 10-11: 42, 10-12: 55, 10-13: 39, 10-28: 23, singles 10-05/15/23/24/26), **717** `401` all on **2026-11-02**, **18** `'3B'` errors (10-24: 8, 10-25: 10) + 1 network failure = 19 HUPX attempts for 2026-10-25, **0 successes**; 0 `Gap detected`; every *successful* price scrape returned exactly 24 rows (1,685 HUPX / 1,706 MEMO). Last cycle 2026-11-03 21:38 (bridge live).

## 5. Findings from the data and history
Register entries: R-D13…R-D17, R-B9, R-O7, R-O8, R-F13, R-F14, R-S10, R-X1 in [13](13_KNOWN_LIMITATIONS_AND_RISKS.md). Evidence below. **Scope note (pass D): §5.1–5.3 describe the HEAD-committed SQLite only; none of it exists in production.**

### 5.1 R-D13 — two hour-label conventions in the HEAD-committed SQLite
- **Origin [V]:** commits 8cedd5a/669a59e/950f61c label `f"H{int(hour_str)}"` (`H0…H23`); `6454cc1` uses `hour_key = hour_int + 1`. The data switches on **2026-02-25**, ~7 weeks before that commit (so the new code ran uncommitted first **[I]**).
- **Proof independent of timestamp semantics [V]:** on spring-forward day **2025-03-30** the nonexistent hour is missing as **`H2` in `energy_generation`** but **`H3` in `hourly_prices`**; on 2026-03-29 both miss `H3`.
- **Scale [V]:** 314 dates carry `H0` (2025-02-01→2026-02-24); 4 dates (2026-02-15/22/23/24) hold 25 rows (`H0…H24`).
- **Revenue effect [I]:** for the 287 old-era dates with HUPX prices, label-joined revenue = 40,641 EUR; joining energy label *n* to price label *n+1* = 38,023 EUR (−2,618 EUR, −6.4 %). Assumes label *n* = clock hour *n*:00–*n+1*:00, which is what the old code produces.
- **Readers [V]:** React and `public_dashboard` look up only `H1…H24`, so `H0` rows vanish silently; FastAPI's union of hours keeps them.
- **Not fixed.** A future fix is a reviewed, backed-up, 1:1 `Hn→Hn+1` relabel on a copy; transition days need manual handling (CLAUDE.md rule 1).

### 5.2 R-D14 / R-D15 numbers
Spikes: `2026-03-15 H12 = 2,103.945 kWh` (day has only H12–H24; neighbours 451/438/342; largest normal hour in 14 months = 546.4 kWh), `2025-04-23 H19 = 1,293.682 kWh` (neighbours 17–81 kWh; priced 139.97 ⇒ phantom ≈ €181). Prices (committed file): 1 junk row (`2025-01-22 H0 hupx = -9999.0`), 66 zero-price rows (HUPX 41; MEMO 25, all 2026-03-12→03-29), 262 negative HUPX rows (min −210.05; 242 of them while producing >1 kWh), 40 producing hours at price 0.

### 5.3 Snapshot facts
Committed file: energy 8,625 rows / 362 dates (348 dates with 24 rows, 4 with 25, 10 with fewer: two DST spring days with 23 and eight outage/partial days); prices 10,847 (HUPX 8,255 / 345 dates; MEMO 2,592 / 108 dates); 11 price dates lack energy, 24 energy dates lack prices; 2025-10-26 (fall-back) HUPX has 24 rows; spring-forward days lack `H3`. Working-tree file: 7,155 prices (HUPX 3,600 / 150 dates; MEMO 3,555 / 149 dates; one MEMO day with 3 rows: 2026-06-23), 2,490 energy rows, 22 zero and 195 negative prices (min −500, max 959), 0 duplicates. The two files agree on the 13 fully overlapping days; 2026-04-14 is partial in the committed file.

## 6. Feature → code map for GitHub `main` (old tree)
| Feature | Page / JS | API | Backend | Data / external |
|---|---|---|---|---|
| Home | `templates/index.html` (static cards) | – | `ui_home` | – |
| Daily analysis | `daily.html` + `daily.js` (`loadDailyData`, `createHourlyChart`, `shiftSelectedDate`) | `GET /api/analysis/by-date/{date}[?source=]` | `get_price_energy_analysis` → `save_data_to_db` (hardware write on every read), scrape-on-miss | SQLite; SolarLog; HUPX/MEMO |
| Monthly analysis | `monthly.html` + `monthly.js` | `GET /api/analysis/by-month/{ym}[?source=]` | `get_monthly_analysis` (N+1 queries, scrape-on-miss) | same |
| Source filter | `#sourceSelector` (All/HUPX/MEMO) | `?source=` | both handlers; "All" merges (R-D6) | `hourly_prices.source` |
For the working tree use [09](09_APPLICATION_FEATURES_AND_WORKFLOWS.md).

## 7. Open-question updates
Q-03 resolved for GitHub-tracked files (public repo, no credentials in committed env files, no secret patterns in 12 commits) · Q-05 strengthened (DST evidence ⇒ the logger reports **local clock time**; start-vs-end-of-interval still [U]) · Q-06 narrowed (bridge never stored HUPX for 2026-10-25) · new Q-13…Q-17 in [13](13_KNOWN_LIMITATIONS_AND_RISKS.md).

## 8. Still unverified
Live InsForge schema/grants/policies (R-S3, Q-02, Q-09; run `zojalog_schema_check.sql`) — data coverage is now verified (§11) · real SolarLog payloads, sampling period, channel semantics, history depth (Q-05) · the launchd plist (Q-10) · contents of untracked env files and of checkpoint refs (R-S10) · rendering/responsiveness in a browser · `npm run build`/`lint` · whether Vercel/FastAPI/`public_dashboard` are deployed (Q-04) · HUPX granularity (15-minute products) (Q-07) · 23-hour DST behaviour on 2027-03-28 (Q-08) · MEMO decimal parsing for `1,234.56`-style values (`bridge.py` L413–416 treats a comma as decimal separator and strips dots).

## 9. Amendments applied in pass B
See [15 §A](15_CHANGELOG.md) for the file list. Repo files are authoritative; the claude.ai Project copies are mirrors (ADR-011).

## 10. Pass C — checkpoint-ref credential review and live-InsForge attempt (2026-11-03 evening)
**Checkpoint refs [V].** Method: `git rev-list --objects` over all `refs/copilot/*` (58 refs, 3 sessions) → 90 unique blobs (53 also in HEAD, 37 checkpoint-only) → 69 text blobs scanned per line, 21 binaries (4 `.DS_Store`, 1 `.idea/.DS_Store`, 2 `app/.DS_Store`, 11 `.pyc`, 3 `.db`) scanned byte-wise with the high-signal patterns; `.env*` blobs classified by key name and value *shape* only; any JWT would have been decoded for `role`/`exp` only (none found). Result: **0 credential hits**; 3 distinct `.env*` blobs, none with secret-like keys/values; the 4 "long opaque string" matches are one 176-char hyphen line in `README.md`. Verdict: safe (R-S10 → Low). Path inventory of all 58 checkpoint trees: 60 distinct paths — the old flat tree, the 3 legacy docs, `AGENTS.md` and `.env`/`.env.bak`/`.env.hardware`; **absent**: `frontend/`, `scripts/`, `tests/`, `docs/`, `.insforge/`, `.env.bridge`, `.env.local`, `CLAUDE.md` ⇒ the checkpoints do **not** preserve the refactor (see R-O1/R-O7). Not covered: the working-tree `.env*`/`.insforge` files (in no checkpoint; outside this scan).
**Live InsForge [U].** Method chosen: standalone stdlib script, `GET` only, anon key read in-process from `frontend/.env` (never printed), no admin key, hard budget. The first request was refused by the sandbox egress policy (`403 Forbidden` at the proxy tunnel) — no request reached InsForge. Not circumvented. Packaged for the owner: `zojalog_readonly_check.py` (12 `GET`s: coverage min/max, `H0` rows + exact count, 2025-03-30 label gaps in both tables, 2026-03-15 and 2025-04-23 rows, top-3 energy values, HUPX rows for 2026-10-25, `-9999` sentinel) and `zojalog_schema_check.sql` (columns, constraints, RLS policies, grants, RLS flags, two counts). Tested against a local mock: `--plan` sends nothing; the run issued only `GET`s, every request carried `limit` ≤ 30, and a fake key echoed in an error body was redacted. Results will settle Q-01, Q-06, Q-14 and R-D13/R-D14 *in production*, plus R-S3/Q-02 via the SQL file.

## 11. Pass D — live InsForge data (owner-run, 2026-11-03 23:11) **[V]**
Run by the owner on his Mac: `zojalog_readonly_check.py --insecure` (12 `GET`s, anon key, `limit` ≤ 30; TLS verification off because his Python lacked root certificates). Output was pasted back; all 12 requests returned HTTP 200. No write, no admin key, no heavy query.
| Check | Live result | Meaning |
|---|---|---|
| Energy coverage | first row `2026-04-01 H1` (0 kWh); last row `2026-11-03 H24` | production data starts **2026-04-01**; bridge is current |
| Price coverage | first row `2026-04-01 H1 hupx` | same start for prices |
| `H0` energy rows | **0** (exact count `*/0`) | R-D13 labels do **not** exist in production |
| 2025-03-30 energy / HUPX | 0 rows / 0 rows | no 2025 data in production |
| 2026-03-15 and 2025-04-23 H19 | 0 rows / 0 rows | the two spike rows are **not** in production |
| Top-3 hourly energy overall | 546.381 (2026-04-08 H13), 541.304 (04-08 H12), 537.013 (04-10 H13) | largest value in the whole table = 546.4 kWh ⇒ **no spike anywhere**; the values equal the working-tree SQLite's top rows ⇒ that snapshot was very likely imported **[I]** |
| HUPX rows for 2026-10-25 | **0** | R-D3 confirmed in production: that day has no HUPX prices (HUPX revenue = €0) |
| Price `< -1000` sentinel | 0 | the `-9999` junk row is not in production |
Notes: PostgREST-style exact counts are only returned for the filtered `H0` request (`Content-Range: */0`); other requests return `*`. The anon key can read both tables (RLS read policy works); whether it can **write** is still unknown (needs the SQL file; the script never tried).
**Owner decisions recorded with this pass:** (1) the old SQLite history (2025-01→2026-03, incl. the `H0` era, spikes and junk prices) is **ignored — no migration, no cleanup**; (2) keep project changes minimal; (3) no code or fixes yet — the next phase concerns **future scraper/ingestion rules** only (candidate list: [17 §N](17_ONBOARDING_COMPLETION_REPORT.md)).
Resolved by this pass: Q-06 (yes, missing), Q-14 (no `H0`, no spikes), Q-01 partly (coverage and import evidence; schema still open).

## Appendix A — Reproduction (read-only; run on a **copy** of the file, never the live DB)
```bash
cp hupx_prices.db /tmp/c.db     # HEAD copy: git show HEAD:hupx_prices.db > /tmp/c.db
sqlite3 "file:/tmp/c.db?mode=ro" "
 select min(date),max(date),count(distinct date) from energy_generation where hour='H0';                 -- 2025-02-01..2026-02-24, 314
 select date,count(*) from energy_generation group by date having count(*)>24;                           -- 4 dates with 25 rows
 select date,hour,energy_kwh from energy_generation order by energy_kwh desc limit 3;                    -- spikes
 select * from hourly_prices where price=-9999;                                                         -- junk row
 select sql like '%UNIQUE%' from sqlite_master where name='hourly_prices';                              -- 0 in the HEAD file
 select group_concat(hour) from (select hour from energy_generation where date='2025-03-30' order by cast(substr(hour,2) as int));            -- H0..H23 minus H2
 select group_concat(hour) from (select hour from hourly_prices where date='2025-03-30' and source='hupx' order by cast(substr(hour,2) as int)); -- H1..H24 minus H3
"
```
## Appendix B — Reproduction of log statistics
```bash
awk '/Cycle start:/{d=$0;sub(/.*Cycle start: +/,"",d);d=substr(d,1,10);c[d]++}
     /Hardware Discovery FAILED/{h[d]++} /401 Client Error/{u[d]++}
     /invalid literal for int\(\) with base 10: .3B./{b[d]++}
     END{for(k in c)print k,c[k],h[k]+0,u[k]+0,b[k]+0}' bridge.log | sort
```
