# 04 — Database and Data Integrity

**Evidence:** schema from `scripts/init_schema.sql` **[V as file]**, but the *live* InsForge schema and grants were **not inspected** (no admin credentials used) **[U]**; live data coverage (2026-04-01→2026-11-03, no `H0` rows, no spikes) was verified on 2026-11-03 via owner-run read-only `GET`s **[V]** — see [16 §11](16_ONBOARDING_VERIFICATION_LEDGER.md). Legacy SQLite inspected on a read-only copy **[V]**.

> ⚠ The README says "SQLite". That is **outdated**. Production storage is **InsForge Postgres**. SQLite is only the legacy snapshot `hupx_prices.db`.

## 1. Production schema (`scripts/init_schema.sql`)
```sql
hourly_prices(   date DATE NOT NULL, hour VARCHAR(4) NOT NULL, price NUMERIC(10,4) NOT NULL,
                 source VARCHAR(16) NOT NULL DEFAULT 'hupx',  PRIMARY KEY (date, hour, source) )
energy_generation( date DATE NOT NULL, hour VARCHAR(4) NOT NULL, energy_kwh NUMERIC(10,4) NOT NULL,
                 PRIMARY KEY (date, hour) )
INDEX idx_hourly_prices_date_source ON hourly_prices(date, source)
INDEX idx_energy_generation_date   ON energy_generation(date)
RLS ENABLED on both tables
POLICY public_read_*   FOR SELECT USING (true)
POLICY service_write_* FOR ALL    USING (true) WITH CHECK (true)   -- no role restriction
```
- **No surrogate `id`.** The composite PKs are the integrity mechanism (one price per date/hour/source; one energy value per date/hour).
- Energy has **no source/channel/device column**; `price` has no currency/unit column (EUR/MWh by convention).
- No `created_at/updated_at`, no audit trail, no CHECK constraints (hour format, non-negative energy, price ranges).
- The file's `service_write_*` policies are not role-scoped; whether `anon` can actually write depends on table GRANTs **[U]** → verify (R-S3).

## 2. Who reads/writes what
| Actor | Mechanism | Operations |
|---|---|---|
| `scripts/bridge.py` | `POST {INSFORGE_URL}/api/database/advance/rawsql` (Bearer `INSFORGE_API_KEY`, falls back to anon key) | `SELECT max(date)`, bulk `INSERT … ON CONFLICT (…) DO UPDATE SET price|energy_kwh = EXCLUDED.…` (strings quote-escaped) |
| React app | `@insforge/sdk` `database.from(t).select/eq/gte/lte/order/limit` (anon key) | `SELECT` only |
| `public_dashboard` | REST `/api/database/records/{table}?col=eq.v&order=…` (hard-coded anon JWT; **different host**) | `SELECT` only |
| FastAPI | `execute_sql()` with key from `.insforge/project.json`, via `MockSession` | `SELECT *`, `SELECT DISTINCT`, `COUNT(*)`, plain `INSERT` (no `ON CONFLICT`) |
| Scripts (`fill_missing_data.py`, `restart_scraper.py`) | same as FastAPI | write prices |

## 3. The MockSession layer (`app/models/database.py`) **[V]**
A ~230-line (228 lines) imitation of SQLAlchemy used by FastAPI/scrapers/legacy scripts. It does **not** use SQLAlchemy except to raise `IntegrityError`.
- `HourlyPrice`, `EnergyGeneration`: plain classes (not ORM). They generate a `uuid4` `id` and include it in `to_dict()` → **INSERT includes an `id` column** that `init_schema.sql` does not define → FastAPI-path inserts likely fail against that schema **[I]** (R-D2). The older migration script (`migrate_to_insforge.py`) also inserts `id`, i.e. an earlier schema had it.
- `MockQuery.filter/filter_by/_build_where` build SQL by **string interpolation** (`f"{col} = '{val}'"`), no escaping → SQL injection for any user-controlled value (R-S2). Endpoints that pass user input: `source` (3 endpoints), `date` path param in `/api/prices/by-date`, `/api/energy/by-date`.
- `MockSession.add()` queues; **`commit()` only INSERTs queued objects.** Attribute mutations on fetched objects (`existing.energy_kwh = …`, `existing.price = …`) are **never written** → every "update existing record" branch on the FastAPI path is a silent no-op (R-D1): `solarlog_client.py` L260, `hupx_scraper.py` L139, debug endpoints.
- `session` is a **process-global singleton** with shared `_pending_adds`; `BasePriceScraper.save_to_db` calls `session.rollback()` first, discarding any other request's pending rows (R-B3).
- `query(Model.date).distinct().all()` returns raw JSON values (strings), not `date` objects, so `/api/available-dates` (which calls `.strftime` on them) likely fails **[I]** — see [03 §4 row 15](03_BACKEND_AND_API.md) and R-B4.
- `IntegrityError` is inferred by substring match on `'duplicate key'`/`'unique constraint'` in the error text.
- `insforge_client.execute_sql` supports `params` but nothing uses them; timeout 10 s; on error logs the SQL and re-raises.

## 4. Data integrity — what protects, what doesn't
| Mechanism | Where | Notes |
|---|---|---|
| Composite primary keys | Postgres | Prevent duplicates; bridge relies on them for upsert |
| Bridge upsert (last write wins) | `bridge.py::InsForgeClient.upsert` | Re-writes today+yesterday every 15 min; ≤14 days when gap detected → **overwrites stored history with device's current view, including 0.0 for hours absent in the response** (R-D8) |
| Skip-empty guard | `bridge.py::run_cycle` (`if rows:`) | An empty device response never deletes/overwrites |
| Gap backfill | `bridge.py::run_cycle` | Only compares **max(date)**; interior holes older than yesterday are never refilled (R-D9) |
| 0-price repair | `BasePriceScraper.save_to_db` | Intended to replace 0 prices; non-persisting on FastAPI path. **Only an exact `0.0` is ever replaced — revised prices from the source are ignored (R-D17)** |
| Missing price ⇒ 0 | every reader | No NULL/flag; downstream revenue understated (R-D5) |
| DST / 25-hour day | none | `H25` doesn't exist; HUPX `3B` crashes parsing (R-D3) |
| Backups | none documented **[U]** | git history contains 3 old `.db` files (see R-S4); InsForge-side backups unknown |

## 5. Legacy SQLite — two different `hupx_prices.db` files **[V, read-only copies]**
**(a) Working-tree file** (tracked path, modified vs HEAD, 622,592 bytes):
```
hourly_prices(id INTEGER PK, date DATE, hour VARCHAR, price FLOAT, source VARCHAR, UNIQUE(date,hour,source))
energy_generation(id INTEGER PK, date DATE, hour VARCHAR, energy_kwh FLOAT, UNIQUE(date,hour))
```
- 7,155 price rows: `hupx` 3,600 + `memo` 3,555; dates **2026-04-01 → 2026-08-28** (150 days).
- 2,490 energy rows; dates **2026-04-01 → 2026-08-27** (149 days).
- Hour labels (this file): exactly `H1…H24`. Whether this snapshot was imported into InsForge (`scripts/migrate_to_insforge.py` → `backup_for_insforge.sql` → `npx @insforge/cli db import`) is **[U]**; the script targets a schema with `id` that differs from `init_schema.sql`.
- `scripts/migrate_add_source.py` is dead: it imports a non-existent `engine` from `app.models.database`.
- Other tracked DBs at HEAD (deleted in the working tree): `energy.db` (0 B), `hupx_data.db` (16 KB, 10 rows of HUPX column metadata from an Oct-2025 Selenium prototype), `hupx_prices` (0 B) (risk R-S4).
- Rows per day: 24 until 2026-04-15, then **15–17 (daylight hours only)** — the legacy writer stores only hours present in the device response; the bridge always writes 24.

**(b) HEAD-committed file** (`git show HEAD:hupx_prices.db`, 819,200 bytes; identical to GitHub `main`) **[V, 2026-11-03 second pass]**:
- `hourly_prices(id, date, hour, price, source DEFAULT 'hupx')` — **no UNIQUE constraint** (the model declares one, but `create_all` never alters an existing table and `migrate_add_source.py` only prints a warning; R-D16). `energy_generation` has `_date_hour_uc`.
- 10,847 price rows (HUPX 8,255 / 345 dates 2025-01-22→2026-04-14; MEMO 2,592 / 108 dates 2025-02-15→2026-04-15) and 8,625 energy rows (362 dates 2025-02-01→2026-04-14).
- Energy `hour` labels are **`H0…H23` for 314 dates (2025-02-01→2026-02-24)** and `H1…H24` afterwards; 4 dates hold 25 rows; prices are always `H1…H24` (R-D13). Also: 1 junk price row (`-9999.0`, `H0`), 66 zero-price rows, 2 impossible hourly energy spikes (R-D14, R-D15).
- **Relationship:** the two files agree on the 13 fully overlapping days (2026-04-01→04-13; 04-14 is partial in (b)). Neither alone is complete: (a) lacks everything before 2026-04-01, (b) everything after 2026-04-15. **Production (InsForge) starts at 2026-04-01 — verified live 2026-11-03**; (b)'s pre-April history, `H0` labels and anomalies are **not** in production and are deliberately ignored (owner decision, no migration; R-O7). Do not delete (b) — it exists only in git.
- Reproduction queries: [16 Appendix A](16_ONBOARDING_VERIFICATION_LEDGER.md).

## 6. Important queries
- Latest ingested date: `SELECT max(date) as max_date FROM <table>` (bridge).
- Day read (React): `hourly_prices` `eq(date)` `[eq(source)]` + `energy_generation` `eq(date)`.
- Month read (React): `gte(date, YYYY-MM-01)` / `lte(date, YYYY-MM-last)` `limit(5000)` (max possible ≈ 744 rows/table, so the cap is safe).
- Initial date (React): `energy_generation` ordered by `date desc limit 1`.
- Upsert (bridge): single multi-row `INSERT … ON CONFLICT (date, hour[, source]) DO UPDATE SET …`.

## 7. Before changing the database
1. Confirm the **live** schema first (InsForge CLI/SQL as admin): columns, PKs, grants/policies for `anon`. Do not trust `init_schema.sql` as a description of production.
2. Any new column must be tolerated by: bridge `upsert` (builds column list from record keys), React `select('*')`, `public_dashboard`, MockSession inserts.
3. Never run destructive SQL, schema migrations or imports without explicit approval and a backup/export plan.
4. Changing `hour` format, PK or `source` values is a breaking change for every consumer ([02 §6](02_ARCHITECTURE_AND_DATA_FLOW.md)).
