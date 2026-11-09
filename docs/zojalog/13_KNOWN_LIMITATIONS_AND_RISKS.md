# 13 — Known Limitations, Risks and Unresolved Questions

Register as of **2026-11-03**. Status: **[V]** verified in source/runtime · **[I]** inferred from evidence · **[U]** needs access not available in onboarding. "Direction" = suggestion only; **nothing here has been changed**.
Severity: Critical / High / Medium / Low (impact × likelihood in this single-owner system).

## A. Security → full detail in [11](11_SECURITY_AND_CONFIGURATION.md)
| ID | Sev | Summary | Status |
|---|---|---|---|
| R-S1 | Critical* | Unauthenticated GET debug endpoints write fabricated rows (`add-test-data`, `add-april-data`, `add-mar14-prices`); open CORS (*if FastAPI reachable) | [V] |
| R-S2 | Critical* | SQL injection via interpolated `source`/`date` in `MockQuery` against admin raw-SQL endpoint | [V code] |
| R-S3 | High | RLS write policies not role-scoped; anon key public → anon write possible depending on GRANTs | [U] |
| R-S4 | **Low-Med** (re-rated 2026-11-03) | `.env*` (non-credential content verified for the committed copies), 3 `.db` files tracked on a **public** `origin/main`; working-tree `.env` unread — see [11](11_SECURITY_AND_CONFIGURATION.md) | [V]/[U] |
| R-S5 | Medium | Hard-coded anon keys/URLs/addresses in source | [V] |
| R-S6 | Medium | Admin key on an always-on Mac; 401 burst 2026-11-02 | [V] |
| R-S7 | Medium | No `.dockerignore` | [V] |
| R-S8/9 | Low | Debug endpoints leak internal addresses; logger is plain HTTP | [V] |
| R-S10 | **Low** (verified) | 58 local Copilot checkpoint refs contain `.env*` file names; content scanned 2026-11-03 — **no credentials** (only bool/int/host:port/private-IP values); not pushed unless `--mirror`/bundles are used — [11](11_SECURITY_AND_CONFIGURATION.md) | [V] |

## B. Data integrity and calculations → [05](05_SOLAR_DOMAIN_AND_CALCULATIONS.md), [06](06_HARDWARE_AND_DATA_COLLECTION.md), [07](07_SCRAPERS_AND_PRICE_SOURCES.md)
| ID | Sev | Summary | Evidence | Direction |
|---|---|---|---|---|
| R-D1 | High | FastAPI path never persists updates: `MockSession.commit` only inserts queued objects; mutate-then-commit is a no-op (`solarlog_client.py` L260, `hupx_scraper.py` L139, debug endpoints) [V] | `database.py` L194–223 | Use upserts (as the bridge) or retire the path |
| R-D2 | Medium | FastAPI inserts include `id`; `init_schema.sql` has no `id` → writes likely fail on current schema [I] | `database.py` L13, L30 vs schema | Verify live schema |
| R-D3 | High | DST fall-back: HUPX `ProductH='3B'` → `int()` fails. Bridge loses the **whole day** of HUPX prices (19 attempts for **2026-10-25** in the log: 18 `'3B'` failures + 1 network failure, **0 successes**); never retried after rollover → the bridge never stored HUPX rows for that day; **confirmed live 2026-11-03: 0 HUPX rows for 2026-10-25 in InsForge**; React then shows €0 revenue for HUPX that day. FastAPI skips only the bad record | `bridge.py` L334, `hupx_scraper.py` L207, log | Parse `ProductH` tolerant of `nA/nB`; decide backfill (needs approval). Next DST: 2027-03-28, 2027-10-31 |
| R-D4 | Medium | FastAPI MEMO falls back to column 2 if the date column isn't found → may store another day's prices under the requested date | `hupx_scraper.py` L530–539 | Return `[]` like the bridge |
| R-D5 | Medium | Missing price ⇒ 0 everywhere: revenue understated, zero included in "average price" | `App.jsx` L292–296, L365–375; `main.py` L532/L557; `public_dashboard` `buildHourly` | Treat as NULL/flag; show warning |
| R-D6 | Medium | Source "All" merges HUPX+MEMO into one dict; arbitrary winner | `main.py` L531–532, L740–741 | Require a source |
| R-D7 | Medium | Two hourly-energy algorithms differ (reset handling, zero fill, key format); only bridge feeds prod | [05 §5](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) | Keep one |
| R-D8 | Medium | Bridge overwrites today/yesterday every cycle and ≤14 days on gaps; hours absent from device response become 0.0 | `bridge.py` L162–165, L87–90 | Don't change algorithm without approval; consider write-protect for old days |
| R-D9 | Medium | Interior gaps older than yesterday are never backfilled (only `max(date)` compared) | `bridge.py` L453–463, L482–495 | Per-date gap detection (approved backfill) |
| R-D10 | Low-Med | `HH:00` sample bucketed into hour `HH+1` (one 5-min interval/hour may be attributed to the next hour if stamps are interval ends) [U semantics] | both calculators; run-verified | Confirm timestamp semantics with device/UI comparison |
| R-D11 | Low | 25-hour/23-hour DST days not representable by `H1..H24`; 23-hour behaviour untested | – | Define policy |
| R-D12 | Low | No audit/`updated_at`; cannot tell when a value was overwritten | schema | Add columns (approval) |
| R-D13 | Low (re-scoped 2026-11-03) | Energy `hour` labels use two conventions in the **HEAD-committed SQLite only** (`H0…H23` for 314 dates 2025-02-01→2026-02-24; prices `H1…H24`; ≈ −6.4 % revenue if aligned **[I]**). **Live check: InsForge has no `H0` rows and no data before 2026-04-01 — production is unaffected.** Owner decision 2026-11-03: the old history is ignored, no migration | [V] production; [V] SQLite | Reuse as an ingestion guard idea only: reject labels outside `H1…H24` ([17 §N](17_ONBOARDING_COMPLETION_REPORT.md)) |
| R-D14 | Medium (re-scoped) | Gap lumping: a sample gap books its whole delta into the later sample's hour; the two spike rows (`2026-03-15 H12 = 2,103.9 kWh`, `2025-04-23 H19 = 1,293.7 kWh`) exist **only in the old SQLite — the live table's maximum is 546.4 kWh**. The bridge has the same structure and no outlier guard, so it can recur; `fix_h1_production.py` zeroes every `H1` row — never run | [V] live top-3; [I] recurrence | Candidate ingestion rule: plausibility check + log, never silent clamp |
| R-D15 | Medium | Price anomalies in the old SQLite (junk `-9999.0` row — **absent in production**; zero-price rows; negative-price hours → negative revenue). The negative/zero price policy (Q-15) still matters for future ingestion | [V]; policy [U] (Q-15) | Decide missing-vs-zero and negative-price rules |
| R-D16 | Low-Med | HEAD-committed SQLite `hourly_prices` has no UNIQUE (working-tree file does) | [V] | Application-level only |
| R-D17 | Low | `save_to_db` replaces only exact-0.0 prices; revisions from the source are never applied | [V] `hupx_scraper.py` L137–141 | – |
| R-D18 | Medium | Price scraping is not skip-aware: every 15-min cycle re-scrapes HUPX + MEMO for today (+ tomorrow after 13:00 Mac time + gap days) and upserts 24 rows per source; energy rows of today and yesterday are rewritten each cycle. `bridge.log`: 1,832 requests per source in 35 days (≈ 52/day average, up to ~140/day while awake) [V] | `bridge.py::run_cycle`; [18 C-5](18_OWNER_ANSWERS_AND_DECISIONS.md) | Skip dates already complete; do not rewrite frozen days (Phase 1 candidate; owner's free-plan budget) |
| R-D19 | Medium | Coverage 2026-08-28 → ~2026-09-17 is **unverified**: the SQLite snapshots end 08-27/28, the bridge log starts 10-02 and back-fills ≤ 14 days, and the live check recorded only first/last row [U] | [16 §11](16_ONBOARDING_VERIFICATION_LEDGER.md), [18 N-3](18_OWNER_ANSWERS_AND_DECISIONS.md) | Owner-run per-day coverage query (Q-23); no write |

## C. Backend / runtime
| ID | Sev | Summary | Evidence |
|---|---|---|---|
| R-B1 | High | `@repeat_every` misuse: 3 loops at startup; each `/api/prices/refresh` / `debug/fetch-today-data` call spawns another loop and returns before the scrape | `main.py` L58–100, L156, L1182; lib source |
| R-B2 | Medium | Blocking `requests` on the event loop; `/api/analysis/by-date` calls the hardware on every request (up to 30 s × retries × 2 IPs) | `main.py` L467 |
| R-B3 | Medium | Global `MockSession` with shared `_pending_adds`; `save_to_db` calls `rollback()` first → cross-request clobbering | `database.py` L184, `hupx_scraper.py` L96 |
| R-B4 | Low | `/api/prices/by-dates` & `/current` depend on an in-memory cache (today only); a 404 inside `try` is re-wrapped as 500; `/api/available-dates` likely fails (`.strftime` on strings) [I] | `main.py` L230–256, L625–645 |
| R-B6 | Medium | `insforge_client` reads `.insforge/project.json` (CWD-relative) at import | `insforge_client.py` L10 |
| R-B7 | High (deploy) | `requirements.txt` lists 3 packages (exactly the bridge's imports); app needs fastapi, uvicorn, fastapi-utils, pydantic-settings, SQLAlchemy, Jinja2, pandas… ⇒ Dockerfile/Railway can't start the app | files |
| R-B8 | Low | Dead MEMO helpers incl. `_distribute_base_peak_prices` that would fabricate hourly prices | grep |
| R-B9 | Medium | **GitHub `main` only:** `GET /api/prices/by-date/{date}` and `/api/energy/by-date/{date}` compare a `Date` column to a raw `str`; SQLAlchemy 2.0.38's SQLite `DATE` bind raises `TypeError` ⇒ expected HTTP 500 (working tree uses string-interpolating MockSession instead — R-S2) | lib [V], effect [I] |

## D. Operations
| ID | Sev | Summary |
|---|---|---|
| R-O1 | High | **Refactor is uncommitted/untracked** (`app/core|models|services`, `scripts/`, `tests/`, `frontend/`, `docs/`); local branches at `3282893` (2026-04-14); `origin/main` = `a5d5698` (PR #1 touching legacy UI files that are also locally modified) ⇒ conflicts on merge; single-disk loss risk [V]. Re-verified 2026-11-03: 4 local branches are not on origin (`feature/refactor-architecture`, `matej35y-legendary-potato`, `matej35y-solarlog-doc-planning`, `matej35y-zojalog-project-takeover`); `git status` = 17 modified, 29 deleted, 71 untracked files |
| R-O2 | Medium | Single-instance bridge on one Mac; outages in October (hardware discovery failures on 11 days, network on 10-11→13, 10-28) with no alerts; "Live" pill static ⇒ stale data looks live [V] |
| R-O3 | Low | `service.sh` LOG_FILE points to `…/Desktop/bomba/bridge.log` (different folder) [V]; plist not inspected [U] |
| R-O5 | Medium | `public_dashboard` points at another InsForge host; unknown if alive/same schema [U]. Its monthly view keys by raw `p.date` while React normalizes with `split('T')[0]` — if the API returns ISO timestamps, monthly values would be zeros [U] |
| R-O6 | Low | Two virtualenvs (`.venv`, `venv`), both Py 3.13.2; Dockerfile uses 3.11 |
| R-O7 | Low (accepted 2026-11-03) | The HEAD-committed `hupx_prices.db` (2025-01-22→2026-04-15) holds history that is **not in InsForge** (production starts 2026-04-01, verified live). Owner decision: ignore it, no migration. It still exists only inside git — keep it (nothing was deleted or changed) **[V]** |
| R-O8 | Medium | Git hygiene: 58 `refs/copilot/checkpoints/*` commits, 5 prunable stale worktrees, 4 unpushed branches, a legacy-docs branch that describes only the old tree. The checkpoint refs snapshot only that old flat tree (60 distinct paths; no `scripts/`, `frontend/`, `docs/`) — **they are not a backup of the refactor**. No deletion was performed **[V]** |
| R-X1 | Low | `pubspec.yaml` (Flutter manifest `energy_price_app`) exists on `origin/main` with no Flutter code anywhere; deleted in the working tree. Intent unknown (Q-16) **[V]** |
| R-O9 | High | **Date labels come from the Mac clock, the logger indexes days on its own clock.** `fetch_day` uses `datetime.now() - days_back`; the logger is on CET/CEST. Since the Mac is now UTC+2, 2026-11-05 00:04–00:49 cycles wrote D−1's data under D and D's under D+1 until the logger rolled over at 01:05; wrong values persist if the Mac sleeps in that window. The 13:00 rule fires at 12:00 CET [V logs, I effects]. See [18 N-1](18_OWNER_ANSWERS_AND_DECISIONS.md) |
| R-O10 | Medium | Bridge ran only 974 of ~3,283 possible 15-min cycles (29 %) between 2026-10-02 and 11-05: the host Mac is awake only part of the time; completeness depends on back-fill, freshness is irregular [V] |
| R-O11 | Medium | Owner-supplied maintenance steps include `python3 scripts/bridge.py --dry-run`; `bridge.py` has no argument parsing, so that command would start a normal **writing** run [V]. Do not use; a real dry-run mode would be new code |
| R-O12 | High | **Which machine runs the production bridge is unverified.** Evidence [V]: the live log is in the Mac repo folder, uses the Mac clock (UTC+2) and reaches the logger via the Windows PC's Tailscale address; uptime 29 %. Owner statement: it should run on the 24/7 Windows PC, independent of the Mac, and he reset the InsForge key on 2026-11-02 without updating the static-PC copy ⇒ a second copy likely exists there and may be failing with 401 [I]. Two instances would double-write (idempotent, but the Mac one mislabels dates for 1 h/night, R-O9). Also `service.sh` points at a stale folder name (`bomba`) |

## E. Frontend
| ID | Sev | Summary | Evidence |
|---|---|---|---|
| R-F1 | Medium | React day navigation skips/sticks east of UTC (run-verified under `Europe/Skopje`) | `App.jsx` L158–170 |
| R-F2 | Low | Initial default date uses UTC | L116–117 (overwritten by latest DB date) |
| R-F3 | Medium | "Avg. Price" means three different things (React: producing hours; legacy: all priced hours; public: price>0 hours); React monthly label "Weighted spot avg" is unweighted | [05 §7](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) |
| R-F4 | Medium | Business logic duplicated in 3 UIs/back-end | – |
| R-F7 | Low | 7 unused npm deps; Vite `/api` proxy unused; empty `pages/components/hooks/theme`; unused `App.css` | grep |
| R-F9 | Low | `styles.css` duplicated byte-for-byte in two places | diff |
| R-F10 | Low | Legacy charts use an older dark palette on the light theme (`#18E299`) | `daily.js` L193–205 |
| R-F11 | Low | `DESIGN.md` doesn't describe the shipped design | [08](08_FRONTEND_AND_DESIGN_SYSTEM.md) |
| R-F12 | Medium | No empty/stale states in React; zeros look like real data | – |
| R-F13 | Low | GitHub `main` legacy monthly "View Details" links `/ui/daily?date=…` but `daily.js` there ignores query params (the working-tree `daily.js` honours it, L30–32) | [V] |
| R-F14 | Low | React *Peak Power* KPI floors at 1.0 kWh/h (`maxEnergy` initial value 1, `App.jsx` L309) — no-production day shows 1.0 | [V] code |

## F. Testing → [12](12_TESTING_AND_VALIDATION.md)
R-T1 (High): no automated tests; broken diagnostic scripts; some tests write to production.

## G. Technical limitations (by design)
Hourly resolution only; one plant, no multi-device model; revenue = spot × energy (no tariff/fees/curtailment/imbalance); two price sources; no timestamps/time zones stored; no authentication; Chart/KPI definitions fixed in code; client-side aggregation (loads whole month of rows into the browser).

## H. Unresolved questions (cannot be settled from the repo)
| ID | Question | How to settle |
|---|---|---|
| Q-01 | ~~Live InsForge row counts / date range / SQLite imported?~~ **Partly resolved 2026-11-03:** production starts 2026-04-01 (energy to 2026-11-03 H24); its top-3 energy values equal the working-tree SQLite's, so that snapshot was very likely imported **[I]**. **Still open:** column types, PKs, `id` column, RLS/grants | owner runs `zojalog_schema_check.sql` in the InsForge SQL editor |
| Q-02 | Can `anon` INSERT/UPDATE/DELETE? (GRANTs vs permissive policies) | admin check; **do not test by writing** **2026-11-05 owner answer:** anon is `SELECT`-only, service key writes — *unverified*: the listing given equals repo `init_schema.sql`, which also has a role-less `FOR ALL USING (true)` policy ([18 C-7](18_OWNER_ANSWERS_AND_DECISIONS.md)); still needs the SQL output (Q-20) |
| Q-03 | ~~Contents/sensitivity of tracked `.env*`; repo visibility~~ **Resolved for GitHub-tracked files (2026-11-03):** public repo; committed env files hold no credentials. Still open: working-tree `.env`/`.env.bridge`/`.env.local` (unread by design) and checkpoint-ref contents (R-S10) | owner review |
| Q-04 | Which pieces are deployed: Vercel URL, FastAPI host, `public_dashboard` host? | owner **2026-11-05 owner answer:** React SPA on Vercel (URL not given); `public_dashboard` legacy → retire; FastAPI unmaintained → superseded. Not independently verified |
| Q-05 | SolarLog timestamp semantics (start vs end of interval), sampling period, channel meaning, history depth (`days_back` max) | device UI/export comparison **2026-11-05:** logger clock = CET/CEST **[V]** ([18 N-1](18_OWNER_ANSWERS_AND_DECISIONS.md)); owner says end-of-interval stamps, 5-min samples, 30–90 d history — stamp convention contradicts the code's bucketing ([18 C-2](18_OWNER_ANSWERS_AND_DECISIONS.md)); still open: needs a ground-truth day |
| Q-06 | ~~Are HUPX rows for 2026-10-25 missing in production?~~ **Resolved 2026-11-03: yes, 0 rows.** Fixing it is an ingestion-rule decision (R-D3); no code or backfill yet | – |
| Q-07 | Does the HUPX endpoint still return hourly (not 15-min) products? (logs show 24 rows/day) | sample the API **Resolved 2026-11-05:** yes — hourly; logs show 24 HUPX records/day (still for 2026-11-06); owner: hourly DAM products |
| Q-08 | Behaviour on 23-hour (spring-forward) day for HUPX, MEMO and energy buckets | observe 2027-03-28 or test with fixtures **2026-11-05 owner rule:** 25 h → `H3B`; 23 h → no `H3`. Behaviour on 2027-03-28 still unobserved |
| Q-09 | Does InsForge return `numeric` as JSON numbers or strings? (frontends coerce with `Number()`, FastAPI multiplies directly) | read-only query |
| Q-10 | launchd plist contents (paths, env, restart policy) | owner **2026-11-05:** plist output still not supplied; owner: managed via `scripts/service.sh`, pauses while the Mac sleeps (uptime 29 %, R-O10) |
| Q-11 | Plant specifics: README says SolarLog Base-2000 | owner **2026-11-05:** nameplate **not given**; the answers' estimate (~350 kW) is contradicted by data (peak 546.4 kWh/h, [18 C-1](18_OWNER_ANSWERS_AND_DECISIONS.md)) → Q-18 |
| Q-12 | Intended future of FastAPI app (retire vs keep) | owner decision **2026-11-05 owner answer:** FastAPI app is an unmaintained legacy prototype, superseded; retire. Execution (debug endpoints, removal) = later, needs approval |
| Q-13 | Which tree is canonical, and may the refactor be pushed to a **new** branch (after a secrets review) as a backup? | owner decision **2026-11-05 owner answer:** work on a dedicated branch (`feature/ingestion-v2`); backup/push authorization and secrets review **not yet given** |
| Q-14 | ~~Are the old `H0…H23` rows and spike rows in InsForge?~~ **Resolved 2026-11-03: no `H0` rows, no spikes, no pre-2026-04 data.** Old history deliberately ignored (owner decision) | – |
| Q-15 | Product rule for negative-price hours (negative revenue vs curtailment) and for price 0 vs "missing" | owner **2026-11-05 owner answer:** negative prices stored/shown as real values; missing price = no row, never 0 (UI "—"); the `memo_fallback` idea is not adopted ([18 C-9](18_OWNER_ANSWERS_AND_DECISIONS.md), ADR-013) |
| Q-16 | Is the Flutter `pubspec.yaml` a planned mobile app or dead? | owner |
| Q-17 | Keep, archive or prune the legacy-docs branch, the Copilot checkpoint refs and stale worktrees? | owner **2026-11-05 owner answer:** Copilot worktrees may be pruned (`git worktree prune`); nothing executed — needs explicit go |
| Q-18 | **Blocker.** Plant nameplate: AC and DC capacity, number of inverters/channels (basis for any plausibility ceiling; data implies ≥ ~550 kW AC) | owner **2026-11-05 (17:50) owner screenshot of the SolarLog inverter page:** 13 inverters, generator (DC) power 11 × 50 kWp + 15 + 20 = **585 kWp**; AC ratings not shown [U]. Observed max 546.4 kWh/h = 93 % of 585 ⇒ consistent. Default plausibility ceiling candidate ≈ 600 kWh/h. The page has SAVE/RECALC buttons — never press them (they edit logger yield values) |
| Q-19 | **Blocker.** Which price is the legal/contractual benchmark for invoice validation: MEMO or HUPX? Does real settlement differ from gross spot (discount, balancing, fees)? | owner (the answers' checklist left it unchecked) **2026-11-05 owner answer:** MEMO is the one mainly used; HUPX only for comparison. UI default source is still `hupx` — change to `memo`? (owner decision, Q-27) |
| Q-20 | Live schema, primary keys, `id` column, RLS policies, grants (can `anon` write?) | owner runs `zojalog_schema_check.sql`, pastes output |
| Q-21 | launchd plist: label, `KeepAlive`, working dir, env key names (no values), log paths | owner terminal commands (masked) |
| Q-22 | Which timezone is the host Mac meant to be in, and will it travel / sleep? (R-O9, R-O10) Is a Pi/VM host planned? | owner **2026-11-05 owner answer:** the Mac is currently in another country (explains UTC+2); owner does not need to change it; intended runtime host = 24/7 Windows PC → fix by deriving dates from the plant timezone (approved), see ADR-014 |
| Q-23 | Per-day coverage of `energy_generation` and `hourly_prices` for 2026-08-20…2026-10-05 (R-D19) | owner-run read-only query |
| Q-24 | What happened to the InsForge key on 2026-11-02 ~00:30 (rotated / revoked / expired)? Where is the current one kept? | owner **2026-11-05 owner answer:** the key was reset on the InsForge site on 11-02 and not updated in the static-PC script copy → matches the mid-run 401s ([18 C-8](18_OWNER_ANSWERS_AND_DECISIONS.md)). The Mac copy was fixed ~14:42; the Windows-PC copy must be checked (Q-26) |
| Q-25 | Which Phase 1/2 items of [18 §4](18_OWNER_ANSWERS_AND_DECISIONS.md) are in scope given "as few changes as possible"? | owner decision **2026-11-05 owner answer:** approved for implementation: skip complete price scrapes; plant-timezone dates; log-and-skip implausible values. `3B`→`H3B` pending an explanation (given 2026-11-05) |
| Q-26 | Which machine(s) run `bridge.py` right now (Mac via launchd or Terminal; Windows PC via Task Scheduler/manual)? Same code version (SHA-256 of `scripts/bridge.py`)? Is the Windows copy writing (log shows `✓ … rows synced`)? | owner read-only checks on both machines |
| Q-27 | Switch the frontend default price source from `hupx` to `memo` (MEMO is the main source)? | owner decision |
| Q-28 | On dam-data.memo.mk for 25.10.2026: does the table show 24 or 25 hourly rows, and how is the repeated 02–03 hour labelled? (bridge stored 24 MEMO rows for that day) | owner looks at the page |
