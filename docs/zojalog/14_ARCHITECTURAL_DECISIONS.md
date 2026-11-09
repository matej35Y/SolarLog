# 14 — Architectural Decisions

**How to read this log.** These decisions were **reconstructed during onboarding** from code, git history, schema files and logs — the owner did not write ADRs. *Evidence* is verified; *intent/rationale* is **[I]** (inferred) unless the owner confirms. When a meaningful architectural decision is made, append a new ADR (next number) and note it in [15](15_CHANGELOG.md). Never edit history silently: supersede instead.

| ADR | Title | Status |
|---|---|---|
| 001 | InsForge Postgres replaces local SQLite | Accepted (de facto) |
| 002 | Schema keyed by `(date, hour label, source)` | Accepted |
| 003 | Ingestion by a standalone bridge, not by FastAPI | Accepted (de facto); FastAPI ingestion legacy |
| 004 | Browser reads the DB directly and computes analytics client-side | Accepted (React); legacy server-side path remains |
| 005 | Tailscale for remote hardware access | Accepted |
| 006 | `MockSession` shim kept for legacy FastAPI code | Accepted as debt |
| 007 | Revenue = hourly spot price × energy (estimate) | Accepted |
| 008 | One shared stylesheet for Jinja and React (copied) | Accepted as debt |
| 009 | Scraper abstraction (FastAPI) vs standalone scrapers (bridge) | Accepted as debt |
| 010 | Two price sources, HUPX default | Accepted |
| 011 | Repo `docs/zojalog/` is the source of truth for project knowledge; claude.ai Project mirrors it | Accepted (owner instruction 2026-11-03) |
| 012 | Old SQLite history is out of scope; no migration; focus on future ingestion rules | Accepted (owner decision 2026-11-03) |

---
### ADR-001 — InsForge Postgres replaces local SQLite
- **Context:** The project began (2025-03) as FastAPI + SQLite on the owner's computer (README still says so). The branch `feature/refactor-architecture` (2026-04) and later files (`scripts/migrate_to_insforge.py`, `scripts/init_schema.sql`, `AGENTS.md`, `models/insforge_client.py`) move storage to InsForge, a hosted Postgres BaaS.
- **Decision:** Production data lives in InsForge `hourly_prices` and `energy_generation`; `hupx_prices.db` is a frozen snapshot (working-tree file 2026-04-01→08-28; the HEAD-committed file is a different snapshot, 2025-01-22→2026-04-15 — see [04 §5](04_DATABASE_AND_DATA_INTEGRITY.md)).
- **Consequences:** Hosted access for a Vercel-style frontend; RLS and keys become the security boundary; README is outdated; SQLite-era scripts (`migrate_add_source.py`) are dead; live-schema drift risk (R-D2, Q-01).
- **Evidence:** [V] files above. Rationale [I].

### ADR-002 — Schema keyed by `(date, hour label, source)`
- **Context:** Needs per-hour joins between production and price, multiple price benchmarks.
- **Decision:** `hour` is a label `H1…H24`; `hourly_prices` PK `(date,hour,source)`; `energy_generation` PK `(date,hour)`.
- **Consequences:** Simple joins and idempotent upserts; no sub-hour resolution; DST 23/25-hour days unrepresentable; every consumer depends on the `Hn` format ([02 §6](02_ARCHITECTURE_AND_DATA_FLOW.md)).
- **Evidence:** [V] `init_schema.sql`, scrapers, UIs.

### ADR-003 — Ingestion by a standalone bridge, not by FastAPI
- **Context:** The SolarLog logger sits on a private network reachable only from the owner's Mac/tailnet; the FastAPI app ingested via startup loops and ad-hoc endpoints.
- **Decision:** `scripts/bridge.py` runs as a launchd service every 15 minutes, computes energy, scrapes prices, and upserts to the cloud DB. The React app never needs the Mac to be online except for fresh data.
- **Consequences:** Reliable upserts (`ON CONFLICT`), gap backfill, discovery/cache logic; single point of failure (the Mac); FastAPI ingestion loops, debug writers and `EnergyDataService` are now legacy and diverge in behaviour (R-D7). **Do not "fix" FastAPI's loops before deciding whether that app should ingest at all (Q-12).**
- **Evidence:** [V] `bridge.py`, log. Rationale [I].

### ADR-004 — Browser reads the DB directly; analytics computed client-side
- **Context:** A hosted DB with a public anon key and RLS read policy removes the need for an API server in the read path.
- **Decision:** `App.jsx` uses `@insforge/sdk` with the anon key; revenue/averages are computed in `useMemo`; a second dashboard (`public_dashboard`) does the same with REST.
- **Consequences:** No server to run for reads; business logic duplicated in 3 places (R-F4); anon key public (R-S3/R-S5); whole-month data downloaded; Vite `/api` proxy and several npm deps are leftovers.
- **Evidence:** [V] `App.jsx`, `vite.config.js`, `package.json`.

### ADR-005 — Tailscale for remote hardware access
- **Context:** Remote access to the logger without port forwarding.
- **Decision:** Reach the logger by Tailscale host/IP (+ LAN fallback); bridge auto-starts Tailscale if stopped.
- **Consequences:** Secure transport; dependency on Tailscale daemon/hostnames; candidate list in `bridge.py` / `.env`.
- **Evidence:** [V] README, `bridge.py::ensure_tailscale`, `config.py`.

### ADR-006 — `MockSession` shim kept for legacy FastAPI code
- **Context:** When moving from SQLAlchemy/SQLite to InsForge's raw-SQL endpoint, the app code (`session.query(...).filter(...)`) was preserved by faking the API.
- **Decision:** Implement `MockQuery/MockSession` that emit string SQL.
- **Consequences:** Minimal diff at migration time; but injection risk (R-S2), non-persisting updates (R-D1), global shared state (R-B3), `id` column mismatch (R-D2). Should be replaced or retired together with ADR-003's follow-up.
- **Evidence:** [V] `database.py`. Rationale [I].

### ADR-007 — Revenue = hourly spot price × energy
- **Decision:** Estimated revenue per hour = `kWh/1000 × EUR/MWh`; aggregates are sums. No tariff, fees, taxes, imbalance or curtailment.
- **Consequences:** Good proxy for exposure to spot prices; not an accounting figure. Missing price ⇒ 0 (R-D5).
- **Evidence:** [V] all calculators ([05](05_SOLAR_DOMAIN_AND_CALCULATIONS.md)).

### ADR-008 — One shared stylesheet for Jinja and React (copied)
- **Decision:** `styles.css` is copied into `app/static/css/` and `frontend/src/`; `index.css` imports it for React.
- **Consequences:** Visual consistency across UIs; manual sync required (currently identical). Legacy JS charts retain an older palette (R-F10).
- **Evidence:** [V] `diff`.

### ADR-009 — Scraper abstraction vs standalone scrapers
- **Decision:** FastAPI has `BasePriceScraper` + `ScraperFactory` (+ DB side effects); the bridge has simpler standalone scraper classes returning rows.
- **Consequences:** Behavioural differences (MEMO column fallback R-D4, DST handling R-D3); changes must be applied in both if both matter. Factory is useful if the legacy app is retained.
- **Evidence:** [V] [07](07_SCRAPERS_AND_PRICE_SOURCES.md).

### ADR-010 — Two price sources, HUPX default
- **Decision:** HUPX (Hungary) and MEMO (North Macedonia) coexist, selectable in the UI; default `hupx` everywhere (`SCRAPER_NAME`, React state, legacy select).
- **Consequences:** Users can compare benchmarks; PK includes `source`; "All" mode in FastAPI is ill-defined (R-D6).
- **Evidence:** [V].

### ADR-011 — Repo docs are the source of truth; the claude.ai Project mirrors them
- **Context:** Several AI sessions (Claude Code, Copilot) documented the project independently; the three Copilot-authored docs on branch `matej35y-solarlog-doc-planning` describe only the old tree and contradict the working tree (see [15](15_CHANGELOG.md)).
- **Decision (owner brief, 2026-11-03):** `CLAUDE.md` + `docs/zojalog/` in the repository are authoritative. Every statement carries an evidence tag **[V]/[I]/[U]**; code wins over docs; the evidence order is source/runtime → schemas/config/tests → docs → owner statements → assumptions. The claude.ai Project holds mirrors; a change is not "in the Project" until it is actually re-uploaded or written there.
- **Consequences:** doc edits must be accompanied by a changelog entry and (for risks) a register entry; contradictory copies must be removed, not accumulated; `16_ONBOARDING_VERIFICATION_LEDGER.md` is the evidence log for claims.
- **Evidence:** [V] owner brief; Project instructions.

### ADR-012 — Old SQLite history is out of scope; focus on future ingestion rules
- **Context:** A live read-only check (owner-run, 2026-11-03) showed InsForge starts at 2026-04-01. The HEAD-committed `hupx_prices.db` holds 2025-01→2026-04 with `H0…H23` energy labels, two spike rows and junk prices (R-D13…R-D15).
- **Decision (owner):** ignore the old SQLite history — no migration, no relabelling, no cleanup; keep project changes minimal; no code yet. Work concentrates on rules for data ingested from now on ([17 §N](17_ONBOARDING_COMPLETION_REPORT.md)).
- **Consequences:** production is unaffected by the old anomalies; the committed DB stays in git untouched (do not delete); R-D13/R-D14/R-D15 stay in the register as ingestion-guard ideas; reports must not mix pre-2026-04 SQLite figures with production figures.
- **Evidence:** [V] [16 §11](16_ONBOARDING_VERIFICATION_LEDGER.md); decision from the owner's message.

### ADR-013 — Owner answers of 2026-11-05: what is adopted, what is not
- **Context:** the owner supplied written answers to the open questions (authored with an AI partner; triaged in [18](18_OWNER_ANSWERS_AND_DECISIONS.md)). Checked against code, logs and the read-only snapshot, several claims conflict with evidence.
- **Adopted (business rules, no conflict):** revenue stays gross spot valuation (ADR-007); both sources stay active; negative prices stored and shown as real values; a missing price is **no row, never 0**; EUR stored; the **volume-weighted capture price** (Σ revenue ÷ Σ MWh) is the canonical "Average price"; SolarLog cumulative yield is the energy source of truth; the repeated hour of a 25-hour day is stored as `H3B`; a failed scrape never overwrites stored values; legacy FastAPI/debug endpoints and `public_dashboard` are to be retired and PR #1 closed (owner actions — none executed).
- **Not adopted (conflict or scope):** the ~350 kW capacity ceiling (C-1); `source='memo_fallback'`; `ANOMALY_OVER_CAPACITY` flag and `updated_at` DDL; clamping night energy to 0; the `--dry-run` maintenance step; shared `zojalog_core`; UI/alerting/currency/discount-factor features (Phase 2 in 18 §4).
- **Consequences:** nothing is implemented until the owner approves a phase; every rule needing a number waits for the nameplate (Q-18); when the capture price, "—" for missing prices or `H3B` reach the UI they must be changed in every duplicated location (CLAUDE.md rule 5).
- **Evidence:** [V] [18 §1–2](18_OWNER_ANSWERS_AND_DECISIONS.md); decisions come from the owner's answers (not individually re-confirmed).

### ADR-014 — The production bridge belongs on the 24/7 Windows PC; changes must be reversible
- **Context:** the owner states the project is meant to run on the always-on Windows PC (reached via Tailscale), with the Mac's own Tailscale use not affecting it. Logs show a bridge currently running on the Mac (R-O12).
- **Decision (owner, 2026-11-05):** runtime host = Windows PC; the Mac must not be required; if a change breaks the previous behaviour it must be restored to how it worked. Approved for implementation: skip complete price scrapes, derive dates from the plant timezone, log-and-skip implausible values.
- **Consequences:** new code must use only the standard library (no new dependency such as `tzdata`), no Mac-only paths, and must behave identically regardless of the host's timezone; changes are built in a scratch copy and shown as a diff first; the previous `bridge.py` is kept for rollback; exactly one bridge instance should write to InsForge once the Windows copy is verified.
- **Evidence:** [V] logs (R-O12); decision from the owner's message of 2026-11-05 17:50.
