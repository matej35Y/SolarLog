# ZojaLog / SolarLog System Architecture, Business Rules & Technical Answers

**Project References:** `ZojaLog` / `SolarLogZOJA` / `bomba` / `Solar Earnings Tracker`  
**Document Status:** Comprehensive Technical Specification & Decision Baseline  
**Date:** November 2026  
**Audience:** System Architects, Operations, Hardware/Energy Engineers, AI Agents

---

## Executive Summary & System Topology

ZojaLog is a specialized solar PV plant telemetry and merchant revenue analytics platform. The plant is located in North Macedonia and cleared against Day-Ahead hourly electricity spot markets (HUPX and MEMO).

The production architecture consists of:
1. **Field Telemetry & Ingestion Bridge (`scripts/bridge.py`):** Runs as an automated service on the local host, querying the on-site SolarLog data logger over a secure Tailscale mesh connection every 15 minutes, parsing 5-minute cumulative yield counters, and scraping daily Day-Ahead market clearing prices from HUPX (Hungary) and MEMO (North Macedonia).
2. **Persistent Cloud Storage (InsForge Postgres):** Managed Postgres BaaS storing normalized hourly generation and market price curves with Row Level Security (RLS) policies.
3. **Analytical Frontend (`frontend/src/App.jsx`):** High-performance React 19 SPA deployed on Vercel, directly interfacing with InsForge via `@insforge/sdk` using anonymous read-only credentials, dynamically calculating volume-weighted capture prices and merchant yield.

---

# Section A: Business Rules for Revenue (Blockers)

### 1. Capacity and Plant Layout
* **Codebase State:**
  There are no hardcoded AC or DC capacity ratings in configuration files or database schemas. Empirical inspection of the historical production table (`energy_generation`) reveals peak summer midday generation reaches approximately **280 kWh to 360 kWh per hour**.
* **Why this is a Blocker:**
  Physical plausibility rules require an absolute upper bound. Without an AC capacity ceiling, communication glitches, inverter resets, or corrupted telemetry can record impossible numbers (e.g. 5,000 kWh in one hour), irreversibly distorting financial reports.
* **Engineering Specification:**
  - **Nominal DC Capacity ($P_{\text{DC}}$):** Installed PV module peak capacity (kWp).
  - **Nominal AC Active Grid Capacity ($P_{\text{AC}}$):** Combined rated active output of the inverter stations (kW). Because $1\text{ hour} \times P_{\text{AC}}\text{ kW} = P_{\text{AC}}\text{ kWh}$, any hourly value $E_h > 1.02 \times P_{\text{AC}}$ is physically impossible.
  - **Inverter Architecture:** Number of physical inverter channels mapped over RS485 to the SolarLog logger (e.g., 3x 100 kW or 4x 75 kW).

---

### 2. Nature of Revenue (Merchant Spot vs. PPA / Feed-in Tariff)
* **Codebase State:**
  Across all calculation engines (`bridge.py`, `App.jsx`, legacy `main.py`), revenue is computed strictly as:
  $$\text{Revenue}_h\,(\text{EUR}) = \frac{\text{Energy}_h\,(\text{kWh})}{1000} \times \text{Price}_h\,(\text{EUR/MWh})$$
* **Market Reality & Business Interpretation:**
  - If the plant sells power purely as an independent power producer (IPP) on the Day-Ahead spot market, this formula represents **100% Gross Market Realization**.
  - If the plant operates under a bilateral Power Purchase Agreement (PPA) with an off-taker (e.g. GEN-I, EVN Trading, or private balancing groups), revenue is subject to contractual discounts (e.g. $\text{HUPX} - \text{Discount}$, or a percentage such as $92\% \times \text{Spot}$), balancing penalties, or fixed feed-in floor prices.
* **Specification:**
  The dashboard serves as the **Gross Market Asset Valuation**. Contractual off-taker discounts and balancing management fees can be represented via an optional configuration factor (`REVENUE_DISCOUNT_FACTOR`, default `1.00`).

---

### 3. Settlement Benchmark: HUPX vs. MEMO
* **Codebase State:**
  Both feeds are stored concurrently in `hourly_prices` differentiated by the `source` column (`'hupx'` vs `'memo'`). The UI allows toggling between them, defaulting to `hupx`.
* **Context & Market Structure:**
  - The plant is located in **North Macedonia** (interconnected via MEPSO transmission grid).
  - **MEMO** (National Electricity Market Operator of North Macedonia) launched the national Day-Ahead Market in May 2023. Prior to MEMO's liquidity, Macedonian merchant renewables pegged contracts to **HUPX** (Hungarian Power Exchange), frequently with a regional cross-border transmission fee adjustment.
  - Today, domestic bilateral off-takers settle on MEMO clearing prices, while regional power purchase contracts remain pegged to HUPX.
* **Specification:**
  Both sources must remain active. The UI will maintain the primary toggle, and the ingestion engine will treat the user's primary selected market as the benchmark for financial totals.

---

### 4. Negative Price Handling & Curtailment
* **Codebase State:**
  Negative hourly prices (common during spring/summer weekend afternoons on HUPX due to Central European renewable surplus) are stored directly as negative floats (e.g. $-18.50\text{ €/MWh}$). Multiplied by positive energy, revenue becomes negative, reducing the daily cash balance.
* **Operational Reality:**
  - **Merchant Penalty:** If the plant is uncurtailed, the operator financially pays for power injected during negative hours.
  - **Automated Curtailment:** If an automated plant controller throttles inverters to 0 kW during negative price hours, energy will drop to 0, preventing negative cash flow.
  - **Contractual Floor:** If the off-taker contract guarantees a floor of 0.00 €/MWh.
* **Ingestion Rule:**
  The ingestion pipeline and database must record true mathematical spot prices and resulting revenues (positive or negative). Hours with negative revenue will be flagged in the UI with a distinct visual indicator (`negative-yield-badge`) to alert asset managers.

---

### 5. Missing Price Handling
* **Codebase State:**
  Historically, if an hourly price was not scraped, frontends and APIs defaulted via `priceMap[h] ?? 0.0`. This silently computed 0.00 € for those hours, severely understating plant revenue and distorting price averages.
* **Ingestion Rule:**
  - In InsForge Postgres, uncollected prices must remain `NULL` (or no row present)—never numeric `0.00`.
  - In the UI: If an hour contains energy $> 0$ but price is `NULL`, revenue displays as `"—"` (Pending/Unknown) with a warning tooltip.
  - Fallback logic: If primary source (`hupx`) is uncollected by 14:00, the ingestion bridge attempts fallback to `memo` (flagged with `source = 'memo_fallback'`).

---

### 6. Costs, Fees, and Settlement Currency
* **Codebase State:**
  Financial records are strictly denominated in Euros (`EUR`).
* **Market Context:**
  In North Macedonia, domestic utility invoices and local PPA settlement statements are denominated in EUR but payable in Macedonian Denars (MKD) at the official National Bank middle exchange rate (fixed peg: $1\text{ EUR} \approx 61.495\text{ MKD}$).
* **Specification:**
  The core database and calculations remain strictly in EUR. A client-side visual currency toggle (EUR / MKD at 61.50) can be added to the UI header without impacting data pipelines.

---

### 7. Canonical Definition of "Average Price"
* **Codebase Conflict Audit:**
  Three conflicting formulas currently exist across the repo:
  1. *Unweighted Arithmetic Average (All Hours)*: $\frac{1}{24} \sum_{h=1}^{24} P_h$ (Included night hours with zero solar production; economically meaningless for solar).
  2. *Unweighted Arithmetic Average (Producing Hours Only)*: $\frac{1}{N} \sum_{E_h > 0} P_h$ (Equally weights a 2 kWh dawn hour with a 350 kWh midday peak hour; mathematically biased).
  3. *Volume-Weighted Capture Price (Realized Market Value)*:
     $$P_{\text{capture}} = \frac{\sum_{h=1}^{24} \left(\text{Energy}_h \times \text{Price}_h\right)}{\sum_{h=1}^{24} \text{Energy}_h} = \frac{\text{Total Revenue (€)}}{\text{Total Energy (MWh)}}$$
* **Specification:**
  The **Volume-Weighted Capture Price** is adopted as the sole authoritative "Average Price" metric across all daily, monthly, and yearly summaries. Arithmetic averages will be retired or labeled "Base Market Average".

---

### 8. Source of Truth for Energy Generation
* **Codebase State:**
  The bridge polls SolarLog key `776` over local HTTP JSON, obtaining cumulative yield counters directly from inverter RS485 communication cards.
* **Engineering Reality:**
  Inverter internal current transducers (CTs) typically carry a Class 1.5% to 2.5% accuracy tolerance. Official billing meters (Class 0.2s / 0.5s utility meters at the grid delivery point) are the legal settlement basis and account for medium-voltage transformer iron/copper losses and cable drop (typically 1.0% to 2.0% loss).
* **Specification:**
  SolarLog cumulative yield is the official operational source of truth for hourly profiling. Ingestion rules assume SolarLog numbers represent inverter-terminal generation.

---

# Section B: SolarLog Hardware Telemetry (Blockers)

### 9. Timestamps & Interval Mapping
* **Codebase Verification (`scripts/bridge.py`):**
  - SolarLog returns 5-minute telemetry intervals in key `776`:
    `["07:15:00", [[power_inv1, yield_inv1], [power_inv2, yield_inv2], ...]]`
  - In `bridge.py`, interval `07:15:00` is parsed with:
    `hour = f"H{sample_time.hour + 1}"` (07:15:00 maps to `H8`).
  - **Convention:** Timestamps represent the **end of the sampling interval**. Any samples occurring from 07:05 through 08:00 accumulate into `H8` (the 07:00–08:00 delivery window).
  - **Clock Reference:** The SolarLog internal clock runs on local time (CET/CEST).

---

### 10. Channel Telemetry & Inverter Counter Resets
* **Codebase Verification:**
  - Key `776` returns an array of per-channel pairs: `[power_watts, cumulative_yield_wh]`.
  - The bridge tracks each inverter channel independently across sequential intervals:
    $$\Delta E = \text{Yield}_{\text{current}} - \text{Yield}_{\text{previous}}$$
  - **Reset Recovery Branch:**
    If $\Delta E < 0$ (e.g. inverter firmware reboot, RS485 comm dropout, or hardware swap), the bridge detects an anomaly and switches to trapezoidal numerical power integration:
    $$E_{\text{est}} = \frac{P_{\text{current}} + P_{\text{previous}}}{2} \times \frac{\Delta t}{3600}$$
  - Logs demonstrate this reset recovery branch functions correctly during transient dawn/dusk inverter reboots.

---

### 11. Yield Counter Behavior
* **Codebase Verification:**
  The counters in key `776` are **monotonically increasing lifetime cumulative Wh**. They do not reset at midnight. Daily midnight delta calculation is preserved by comparing the first morning sample against the previous night's terminal sample.

---

### 12. Hardware History Depth & Partial Days
* **Codebase State:**
  - SolarLog non-volatile internal flash buffers 5-minute interval data for 30 to 90 days.
  - In `bridge.py`, standard cycles poll `days_back=0` (today) and `days_back=1` (yesterday).
  - When backfilling missing historical gaps, the bridge increments `days_back` up to 14 days.
  - For current day operations, SolarLog returns intervals up to the most recent 5-minute mark. Future hours do not exist in the hardware response.

---

### 13. Auxiliary SolarLog Keys (141, 152, 161, 162, 480, 801)
* **Codebase Audit:**
  Legacy scripts (`solarlog_client.py`) requested keys 141 (AC instantaneous power), 152 (daily summary), 161/162 (fault/status codes), and 801 (device metadata).
* **Specification:**
  The production `scripts/bridge.py` requests **key 776 exclusively**. Key 776 provides all necessary energy and power telemetry required for settlement and analytics. Auxiliary keys can remain ignored unless inverter diagnostic alerting is explicitly scoped.

---

### 14. Hardware Disconnections & Network Outages
* **Root Cause Analysis:**
  Log audits (`bridge.err.log`) during historical outages (e.g. Oct 2–3, Oct 11–13, Oct 28) show network socket timeouts to Tailscale endpoint `desktop-l3cv8h8:8085`.
* **Hardware Resilience:**
  Because the physical SolarLog data logger continuously logs 5-minute data to internal flash memory regardless of network status, no telemetry is lost during internet outages. Once the Tailscale link is restored, the bridge queries `days_back` and completely restores the database.

---

### 15. Network Topography & Routing
* **Configuration (`.env.bridge`):**
  - Primary Tailscale Endpoint: `desktop-l3cv8h8:8085` / `100.116.216.29:8085`.
  - Direct Fallback IP: `192.168.1.100:80` (active when connected to local plant subnet).
  - Node `desktop-l3cv8h8` operates as an on-site gateway forwarding port 8085 to the SolarLog web server.

---

# Section C: Price Feeds & Day-Ahead Settlement

### 16. HUPX Granularity and Market Product
* **API Details:**
  The scraper queries `https://labs.hupx.hu/data/v1/dam_aggregated_trading_data`.
* **Product:** Day-Ahead Hourly Auction (DAM).
* **Granularity:** Standard 60-minute delivery products (`ProductH` 1 through 24). Values are denominated in EUR/MWh.

---

### 17. Daylight Saving Time (DST) Handling (23h and 25h Days)
* **The Problem:**
  - **Fall Back (Short Day, 25 Hours):** In October, European clocks shift 03:00 $\rightarrow$ 02:00. The day has 25 trading hours. HUPX designates the repeated hour as `3B` (or 25).
  - **Spring Forward (Long Day, 23 Hours):** In March, European clocks jump 02:00 $\rightarrow$ 03:00. Hour 3 does not exist.
  - The legacy database schema strictly stores `hour VARCHAR(4)` with expected keys `H1` through `H24`.
* **Authoritative Solution:**
  1. The column `hour VARCHAR(4)` natively accommodates labels `'H3B'` or `'H25'`.
  2. For the 25-hour day: Store the repeated hour explicitly as `'H3B'`.
  3. For the 23-hour day: Hour `'H3'` is absent or recorded as 0 kWh with `NULL` price.
  4. The frontend UI dynamically renders hours based on the actual keys returned in the dataset rather than iterating over a fixed 1..24 loop.

---

### 18. Publication Timing & The 13:00 Rule
* **Day-Ahead Market Clearing Schedule:**
  - **12:00 CET:** HUPX order book closure.
  - **12:45–12:55 CET:** HUPX clearing prices calculated and published.
  - **13:00–13:30 CET:** MEMO Day-Ahead auction results cleared and published.
* **Bridge Behavior:**
  The conditional check `if now.hour >= 13:` in `bridge.py` is accurate. Attempting to scrape tomorrow's prices before 13:00 CET results in 404 or empty tables. Scraping after 13:00 ensures tomorrow's day-ahead prices are ingested immediately.

---

### 19. Price Revisions and Finality
* **Market Rules:**
  European Day-Ahead spot auction clearing prices are legally final and immutable upon official publication. They are not revised post-settlement. 
* **Ingestion Logic:**
  `ON CONFLICT (date, hour, source) DO UPDATE SET price = EXCLUDED.price` is safe and idempotent.

---

### 20. MEMO Scraping Reliability
* **Scraper Details:**
  Scraped via HTTP POST form from `https://dam-data.memo.mk/index.php?action=auction-by-hour&lang=en`.
* **Execution Footprint:**
  Because the bridge polls prices only once an hour (and skips already-ingested dates), total daily requests to MEMO are $< 10$, representing zero risk of IP blocking or server overload.

---

### 21. Backfill of 2026-10-25 HUPX Data
* **Status:**
  On 2026-10-25, MEMO was successfully ingested, but HUPX failed due to the 25-hour DST format. A dedicated single-day backfill using the approved `'H3B'` schema format will complete the historical series.

---

# Section D: Database Architecture & InsForge Backend

### 22. Production Schema Verification
The production database schema hosted on InsForge Postgres (`z9dt4nnj.eu-central.insforge.app`) is defined as follows:

```sql
-- Table: hourly_prices
CREATE TABLE hourly_prices (
    date DATE NOT NULL,
    hour VARCHAR(4) NOT NULL,      -- 'H1'..'H24', plus 'H3B' for DST
    price NUMERIC(10, 4) NOT NULL, -- EUR/MWh
    source VARCHAR(16) NOT NULL DEFAULT 'hupx', -- 'hupx' | 'memo'
    PRIMARY KEY (date, hour, source)
);
CREATE INDEX idx_hourly_prices_date_source ON hourly_prices (date, source);

-- Table: energy_generation
CREATE TABLE energy_generation (
    date DATE NOT NULL,
    hour VARCHAR(4) NOT NULL,      -- 'H1'..'H24', plus 'H3B' for DST
    energy_kwh NUMERIC(10, 4) NOT NULL,
    PRIMARY KEY (date, hour)
);
CREATE INDEX idx_energy_generation_date ON energy_generation (date);
```

* **Key Schema Observations:**
  - Tables use composite natural primary keys. There are no surrogate auto-incrementing `id` columns.
  - Row Level Security (RLS) is enabled.

---

### 23. Security Permissions & The 401 Incident on 2026-11-02
* **Access Control Matrix:**
  - `anon` role (Public / Frontend): Granted `SELECT` permission only. Cannot insert, update, or delete.
  - `service_role` (Backend / Bridge): Full read/write permissions via admin API key.
* **The 401 Incident Analysis:**
  The 717 HTTP 401 errors observed on 2026-11-02 occurred when the bridge process was started with an invalid or expired `INSFORGE_API_KEY`. The current `.env.bridge` file has been verified with active write permissions.

---

### 24. Database Storage Limits & Free-Tier Quotas
* **Annual Storage Footprint:**
  - Energy Generation: 24 rows/day $\times$ 365 = 8,760 rows/year.
  - Hourly Prices (2 sources): 48 rows/day $\times$ 365 = 17,520 rows/year.
  - **Total annual ingestion:** $\approx 26,280\text{ rows/year}$.
  - Storage size: Approximately **4.5 MB to 6 MB per year**.
* **Capacity Planning:**
  Standard Postgres free-tier quotas handle $> 500,000$ rows and 500 MB of storage. The database will operate within free limits for over a decade.

---

### 25. Historical Data Lineage (April–October)
* **Data Flow History:**
  - Data from 2026-04-01 to 2026-08-28 originated in legacy SQLite (`hupx_prices.db`).
  - In late August, `scripts/migrate_to_insforge.py` migrated these records to InsForge Postgres.
  - Starting October 2, `scripts/bridge.py` took over automated live ingestion.
  - `hupx_prices.db` is purely archival and no longer active.

---

### 26. Data Audit & Test Endpoints
* **Integrity Audit:**
  Legacy FastAPI routes (`/api/debug/add-test-data`, `/add-april-data`) allowed inserting fabricated data. A comprehensive production database audit confirms zero synthetic test rows or sentinel values exist in the active 2026 series. These endpoints should be permanently disabled.

---

### 27. Schema Evolution (`created_at`, `updated_at`)
* **Recommendation:**
  Add non-breaking audit columns to both tables:
  ```sql
  ALTER TABLE hourly_prices ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
  ALTER TABLE energy_generation ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
  ```
  This provides immediate operational transparency regarding whether data was ingested in real time or backfilled later.

---

# Section E: Operations & Deployment Architecture

### 28. launchd Daemon & Host Machine Constraints
* **Service Configuration:**
  Managed via macOS launchd plist `com.solarlog.bridge` (`scripts/service.sh`).
* **Operational Characteristics:**
  - LaunchAgents run within user login sessions. If the host Mac is closed or put to sleep, launchd pauses execution.
  - When awakened, the bridge resumes, discovers the gap in InsForge, and backfills all missing hours directly from the SolarLog buffer.
  - **Recommendation:** If uninterrupted real-time reporting is required, the bridge can be deployed to an on-site low-power device (e.g. Raspberry Pi) or a cloud VM running Tailscale.

---

### 29. Inventory of Deployed Artifacts
1. **Production Bridge (`scripts/bridge.py`):** Active on local host. Handles hardware polling and DB sync.
2. **Production Web Application (`frontend/`):** React 19 SPA deployed on Vercel. Connects directly to InsForge.
3. **Public Dashboard (`frontend/public_dashboard/index.html`):** Legacy vanilla-JS dashboard pointing to obsolete host (`4hj8wryw`). Target for retirement.
4. **FastAPI Backend (`app/main.py`):** Unmaintained legacy prototype. Missing dependency declarations; superseded by the direct-to-InsForge architecture.

---

### 30. Bridge Maintenance & Rollback Procedure
* **Standard Operating Procedure:**
  ```bash
  # 1. Stop daemon
  ./scripts/service.sh stop

  # 2. Perform updates or syntax checks
  python3 scripts/bridge.py --dry-run

  # 3. Restart daemon
  ./scripts/service.sh start

  # 4. Tail real-time execution logs
  ./scripts/service.sh logs
  ```

---

### 31. Telemetry Monitoring & Alerting
* **Specification:**
  Implement a lightweight failure notification system inside `bridge.py`:
  - If Tailscale cannot establish a socket connection after 5 consecutive attempts $\rightarrow$ trigger alert.
  - If Day-Ahead prices for tomorrow remain uncollected by 16:00 CET $\rightarrow$ trigger alert.

---

# Section F: Version Control & Development Standards

### 32. Git Hygiene & Secret Security
* **Protocol:**
  Before pushing to any public remote (e.g. GitHub `matej35Y/SolarLog`), ensure `.gitignore` strictly covers:
  - `.env*`
  - `.insforge/project.json`
  - `.device_cache`
  - All local log files (`*.log`)

---

### 33. Disposable Branches and Copilot Worktrees
* **Cleanup:**
  Worktrees in `/Users/matejmacevski35/copilot-worktrees/*` generated by automated coding agents can be safely pruned (`git worktree prune`).
* **Active Branches:**
  Active production work proceeds on `main` or a dedicated refactor branch (`feature/ingestion-v2`).

---

### 34. Legacy Pull Requests (PR #1)
* **Status:**
  PR #1 (legacy Jinja UI date picker) is obsolete and should be closed without merging.

---

### 35. Logic Consolidation & Naming Conventions
* **Target Architecture:**
  Consolidate all business logic into a single shared Python library (`zojalog_core`) to eliminate code duplication across scrapers and bridges.
* **Official Branding:**
  - Repository / Project Name: `ZojaLog`
  - Dashboard Branding: `SolarLogZOJA` ☀️

---

# Section G: Ingestion Rules & Telemetry Processing

### 36. Handling Missing Telemetry Samples (Network Gaps)
* **The Scenario:** SolarLog goes offline for 3 hours during midday (e.g. 11:00 to 14:00) and reconnects at 14:05.
* **Flawed Naive Handling:** Simply taking the counter delta between 11:00 and 14:05 places 3 hours of accumulated generation entirely into Hour 15, creating an artificial spike.
* **Authoritative Ingestion Rule:**
  1. Because SolarLog records internal 5-minute intervals, the bridge must fetch historical 5-minute samples for the offline period upon reconnection.
  2. If the physical logger itself lost power and internal 5-minute data is truly missing, the bridge distributes the net counter delta across the daylight gap hours using a standard solar irradiation distribution curve (or equal daytime apportionment).

---

### 37. Plausibility Validation Thresholds
Every incoming hourly record must pass strict validation before insertion:
1. **Night Invariant:** Hours $H1$–$H5$ and $H22$–$H24$ must have $\text{Energy} = 0.00\text{ kWh}$. Any sensor noise or leak voltage $> 0.05\text{ kWh}$ is clamped to $0.00$.
2. **AC Generation Ceiling:** Hourly energy cannot exceed rated plant AC capacity:
   $$E_h \le 1.02 \times P_{\text{AC}}\text{ (kWh)}$$
   Records exceeding this threshold are flagged as `ANOMALY_OVER_CAPACITY` and withheld from automated financial totals.
3. **Price Bounds:** Any Day-Ahead price outside the standard European market clearing limits ($-500\text{ €/MWh} \le P \le 4000\text{ €/MWh}$) is rejected as scraper corruption.

---

### 38. Historical Data Freezing
* **Rule:**
  Records older than **$T - 2$ days** are frozen and immutable. The bridge will never update or re-scrape records older than 48 hours unless a manual administrative override (`--force-recalculate`) is provided. This guarantees accounting stability.

---

### 39. Partial Days & Future Hours Representation
* **Rule:**
  - **In Database:** Future hours that have not yet occurred are **not inserted**.
  - **In UI:** Future hours render as empty chart slots. Past hours with zero production (e.g. night hours) render as flat zero bars, clearly distinguishing zero generation from pending future time.

---

### 40. Scraper Retry & Resilience Policy
* **Rule:**
  - Failed scrapes execute 3 retries with exponential backoff (5s, 20s, 60s).
  - A failed scrape never overwrites existing database values.
  - If a price source is unavailable, the record remains `NULL` to prevent zero-value distortion.

---

# Section H: Validation & Benchmarking

### 41. Ground Truth Alignment
Telemetry accuracy will be benchmarked directly against:
1. SolarLog on-device daily cumulative display (`Yield Today`).
2. Monthly EVN/MEPSO utility meter settlement statements.

### 42. Engineering Tolerance
* A discrepancy of **$\le \pm 1.5\%$** between SolarLog telemetry and utility billing meters is expected due to medium-voltage transformer losses and Class 1.0 inverter CT limits.
* Any discrepancy $> 3.0\%$ indicates an omitted inverter channel, phase drop, or counter reset error.

### 43. Benchmark Verification Days
Validation suites will test against five characteristic operational profiles:
1. **Sunny Summer Day (e.g. 2026-07-15):** Smooth bell curve; verifies maximum capacity ceiling.
2. **Volatile Cloudy Day (e.g. 2026-10-18):** Rapid fluctuations; verifies delta aggregation.
3. **Network Interruption Day (e.g. 2026-10-12):** Validates backfill and gap distribution.
4. **Fall-Back 25h DST Day (e.g. 2026-10-25):** Validates repeated hour `H3B` handling.
5. **Spring-Forward 23h DST Day (e.g. 2026-03-29):** Validates skipped hour `H3` handling.

---

# Section I: Priority Action Checklist

To finalize the ingestion engine refactor, the following parameters are locked into the system configuration:

- [x] **Database Schema:** Natural keys `(date, hour, [source])` confirmed.
- [x] **Average Price Metric:** Volume-Weighted Capture Price established as primary.
- [x] **Negative Price Policy:** Preserved as real market value with UI alert tagging.
- [x] **DST Strategy:** `H3B` nomenclature adopted for 25-hour days.
- [ ] **Plant Nominal AC Capacity ($P_{\text{AC}}$ in kW):** *Awaiting owner specification (estimated ~350 kW).*
- [ ] **Primary Off-taker Benchmark:** *Confirm whether MEMO or HUPX is legal default for invoice validation.*

---
*Document automatically compiled for ZojaLog / SolarLog asset management and code generation.*
