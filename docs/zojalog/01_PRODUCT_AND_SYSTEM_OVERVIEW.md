# 01 — Product and System Overview

**Evidence:** product intent from `README.md` (Macedonian + English) and UI copy **[V]**; runtime behaviour from `bridge.log` (2026-10-02 → 2026-11-03) **[V]**; plant hardware model from README only **[I]** (not verifiable from code).

## 1. What ZojaLog is and why it exists
ZojaLog tracks how much energy one solar plant produces and what that energy is worth at wholesale day-ahead prices. The owner-operator (Matej Macevski, Skopje) wants, for any hour/day/month: **production (kWh)**, **market price (EUR/MWh)** and **estimated revenue (EUR)**, and wants to compare two price benchmarks (HUPX vs MEMO).

It is not a billing system: revenue is an **estimate** (production × spot price per hour). Actual contract/tariff pricing is not modelled **[V]**.

## 2. Names (all refer to the same product)
| Name | Where |
|---|---|
| ZojaLog | project/owner naming, onboarding docs |
| SolarLog | GitHub repo `matej35Y/SolarLog`, legacy Jinja UI brand, InsForge-related scripts |
| Solar Earnings Tracker | `README.md` title; InsForge project name `solar-earnings` (`AGENTS.md`) |
| SolarLogZOJA ☀️ | React app nav brand and `<title>` (`frontend/src/App.jsx` L558, `frontend/index.html`) |
| HUPX Price API | `Settings.APP_NAME` (`app/core/config.py`) — FastAPI title |
| SolarLog (the device) | the **hardware data logger** (README: Base-2000) — not the app |

## 3. Who uses it
Single owner-operator; the dashboard is read-only. There is no login, no multi-tenant model, no user table **[V]** (the dashboard is public to anyone who knows the URL and holds the anon key bundled in the JS — see doc 11).

## 4. What the user sees
- **Daily view:** 24 rows `H1…H24` with kWh, share-of-peak bar, price, revenue; KPIs: total energy, total revenue, average price, peak hourly energy; combo/bar/line chart.
- **Monthly view:** one row per day with MWh, average price during production hours, revenue; KPIs: monthly energy, revenue, average spot price, days with generation; clicking a day jumps to its daily view.
- **Source switch:** HUPX (Hungary) / MEMO (Macedonia).
Full detail: [09](09_APPLICATION_FEATURES_AND_WORKFLOWS.md), [08](08_FRONTEND_AND_DESIGN_SYSTEM.md).

## 5. Terminology
| Term | Meaning in this codebase |
|---|---|
| Hour label `Hn` | Delivery hour n (1–24). **H1 = 00:00–01:00**, H24 = 23:00–24:00 local time. Stored as `VARCHAR(4)` |
| Energy (kWh) | Energy produced in that hour. Derived from cumulative yield counters |
| Power (W/kW) | Instantaneous rate. Only used by the bridge as a fallback when a counter resets |
| Cumulative yield | SolarLog per-inverter counter in **Wh** that only increases (until reset) |
| Interval / sample | One SolarLog record `[timestamp, [[power, yield] per inverter]]`, ~5-minute spacing **[I]** (not asserted in code) |
| Price (EUR/MWh) | Day-ahead market clearing price for that hour from HUPX or MEMO |
| Source | `hupx` or `memo` (column on `hourly_prices`; energy has none) |
| Revenue / value | `kWh/1000 × EUR/MWh` per hour, summed |
| Working hour / active hour | Hour with `energy_kwh > 0` |
| Bridge | `scripts/bridge.py`, the production ingester |
| days_back | SolarLog request index: 0 = today, 1 = yesterday… |

## 6. Raw vs calculated vs estimated
| Data | Nature | Produced by |
|---|---|---|
| SolarLog `776` intervals (power, yield) | **raw hardware reading** | device |
| `energy_generation.energy_kwh` | **calculated** (counter deltas bucketed per hour) | bridge (prod) / `EnergyDataService` (legacy) |
| `hourly_prices.price` | **raw market data** (scraped) | HUPX API / MEMO HTML |
| Revenue, averages, shares | **calculated at read time**, never stored | React `App.jsx`, FastAPI analysis endpoints, `public_dashboard` |
| Missing price → 0 | **implicit assumption** (not a market value) | all readers |
| Hours with no energy row | treated as 0 kWh | all readers |

## 7. Historical vs periodically updated
- **Periodically updated:** *today* and *yesterday* energy rows are re-upserted every 15 min (`ON CONFLICT DO UPDATE`); today's prices re-upserted every cycle; tomorrow's prices added after 13:00 local (`bridge.py` L451, L498).
- **Effectively historical:** older days are only touched when a "gap" is detected (backfill ≤14 days) — see doc 06. Browser reload/auto-refresh (5 min) just re-reads.

## 8. How missing data shows up for the user
No dedicated "no data" state in the React app: a day with no rows renders 24 rows of zeros and `€0.00` KPIs; a price outage renders revenue `€0.00` while energy is non-zero. The "Live" pill is static text, not a freshness indicator **[V]** (`App.jsx` L584; `sl-nav__pill`). Legacy UI shows an error/“No data for this date” banner. See risks R-D5, R-O2.

## 9. Current operating snapshot (2026-11-03) **[V from bridge.log]**
- Bridge running; 919 cycles logged across 33 days; last cycle 17:22 local, all four syncs OK (energy today+yesterday: 24 buckets each; prices HUPX+MEMO for today and tomorrow).
- Notable historical incidents: hardware-discovery failures on 11 days in October; network failures 2026-10-11→13 and 10-28; HUPX parse failure for 2026-10-25 (DST); 717 `401 Unauthorized` events on 2026-11-02 (credential problem, since resolved). Details: [13](13_KNOWN_LIMITATIONS_AND_RISKS.md).
