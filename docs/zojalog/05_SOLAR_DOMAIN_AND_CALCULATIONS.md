# 05 — Solar Domain and Calculations

**Evidence:** every formula traced to source **[V]**. The two hourly-energy algorithms were additionally **executed on synthetic data** (2026-11-03) to confirm behaviour **[V-run]**. Real SolarLog payloads were not captured, so field meanings marked **[I]** come from how the code uses them.

## 1. Concepts that must not be confused
| Pair | Rule in this codebase |
|---|---|
| Power vs energy | Power (W) is instantaneous; energy (Wh/kWh) is accumulated. Stored values are **energy**. Power is read from the device but only used as an estimator when a counter resets |
| Cumulative vs interval | Hardware gives **cumulative yield (Wh)** per inverter channel. Interval energy = difference of consecutive readings |
| Raw vs processed | Raw: device intervals, scraped prices. Processed: `energy_kwh` per hour; revenue/averages at read time |
| Price vs revenue | Price is EUR/MWh (market). Revenue is derived: EUR |
| Available vs missing | A missing price row is treated as price 0; a missing energy row as 0 kWh. Neither is flagged |

## 2. SolarLog data format (as used by code)
Request: `POST http://<host>/getjp`, body `preval=none;<compact JSON>`, headers `Content-Type: application/x-www-form-urlencoded; charset=UTF-8`, `X-Requested-With: XMLHttpRequest`, `X-SL-CSRF-PROTECTION: 1`.
- Key **`776`** = history intervals; request `{"776":{"<days_back>":null}}` (0 = today, 1 = yesterday, …). Response: `{"776":{"<days_back>":[ [ "HH:MM:SS", [[power_W, yield_Wh], …one pair per inverter/channel] ], … ]}}` **[I: per-channel semantic]**.
- Key `777` (`{"1":null}`) is used only as a liveness probe by the bridge; the legacy service also requests `141,152,161,162,480,801` but ignores those results.
- Empty list ⇒ night/device off/no history; treated as "no rows".

## 3. Production algorithm — `scripts/bridge.py::calculate_hourly_energy` (L48–90)
1. Sort intervals by timestamp; parse `"%H:%M:%S"`.
2. First sample is only a baseline (no energy attributed).
3. For each later sample, for **each channel index** present in both samples:
   - if `yield_now >= yield_prev`: `energy_Wh = yield_now − yield_prev`.
   - else (**counter reset**): estimate `mean(max(0,power_prev), max(0,power_now)) × elapsed_s / 3600` (non-finite powers dropped; none ⇒ 0).
4. Add `energy_Wh/1000` to bucket **`H{sample_hour + 1}`** (`sample_hour` = the sample's own hour).
5. Return all 24 keys `H1…H24` (zeros filled), rounded to 4 decimals. Elapsed time wraps across midnight (+24 h) if negative.

## 4. Legacy algorithm — `EnergyDataService.get_hourly_data` (`solarlog_client.py` L102–184)
1. Sort intervals; `curr_total = sum(yield over all channels)`.
2. First record skipped (`prev_total=None`).
3. `wh = curr_total − prev_total`; **if negative → 0 for the whole interval** (all channels), logged as "device might have reset".
4. Bucket `H{hour_of_timestamp + 1}`; output only hours that received data, string keys `"1","2",…` (`save_data_to_db` prefixes `H`), rounded to 3 decimals.
5. Future dates return `({}, 0)` without calling the device; connection failure returns `(None, None)`.

## 5. Verified differences (synthetic runs, 2026-11-03)
| Case | Input | Bridge (production) | Legacy service |
|---|---|---|---|
| A. monotonic, 2 channels, samples 00:55→02:00 | +200 at 01:00, +250 at 01:05, +1550 at 01:55, +200 at 02:00 | `H2=2.0 kWh`, `H3=0.2 kWh` (24 keys) | `H2=2.0`, `H3=0.2` (only 2 keys) |
| B. one channel resets (5000→10 Wh, 600/720 W over 300 s) while other +40 Wh | – | **0.095 kWh** (55 Wh estimated + 40) | **0.0** (total negative → clamped; healthy channel's 40 Wh lost) |
| C. first-sample baseline | 500 → 600 Wh | `H1=0.1` | `H1=0.1` |
**Implication:** the same device day can yield different stored values depending on which path wrote it. Production = bridge. Never mix them for the same date without understanding R-D7.

**Boundary semantic (R-D10):** a sample stamped exactly `HH:00` (e.g. 01:00:00, covering 00:55→01:00 if timestamps are interval *ends*) is bucketed into `H{HH+1}` (`H2`), i.e. the hour *after* the energy was produced. Both algorithms behave this way; the code comment claims timestamps are interval ends, but the mapping then shifts one sample per hour. Whether SolarLog stamps start or end of interval is **[U]**. Do not "fix" without confirming against device behaviour and agreeing how to treat history.

## 6. Prices and revenue
- Price unit EUR/MWh; hour labels from sources: HUPX `ProductH` → `H{n}`; MEMO period `"00 - 01"` → `H1` … `"23 - 00"` → `H24`. See [07](07_SCRAPERS_AND_PRICE_SOURCES.md).
- **Hourly revenue (EUR) = `energy_kwh / 1000 × price_eur_per_mwh`** — identical in `main.py` L563–566 & L771–774, `App.jsx` L312 & L371, `public_dashboard` `buildHourly`.
- Daily revenue = Σ hourly revenue. Monthly revenue = Σ daily revenue (no re-averaging).
- Example (illustrative): 50 kWh in an hour priced 120 EUR/MWh → 0.050 MWh × 120 = **6.00 EUR**.

## 7. Aggregation rules — **not identical across implementations**
| Metric | FastAPI (`main.py`) | React (`App.jsx`) | `public_dashboard` |
|---|---|---|---|
| Daily "Avg. price" shown | legacy UI shows `arithmetic_avg_price_per_mwh` = mean of price over hours with `energy>0 OR price>0` (includes night hours with price) | mean price over hours with `energy>0` (missing price counted as 0) | mean over hours with `price>0` (ignores production) |
| Also available | `working_hours_avg_price_per_mwh` (energy>0 hours) and `average_price_per_mwh` = revenue ÷ MWh (weighted) — **not displayed by legacy UI** | – | peak price |
| Daily "Peak" | – | max hourly kWh ("Peak Power", unit kWh/h) | max hourly kWh + max price |
| Hours listed | only hours with `energy>0 or price>0` | always 24 rows | always 24 rows |
| Monthly avg price | unweighted mean of price over all working hours (`avg_working_hour_price`) | same; **KPI sub-label says "Weighted spot avg" but it is unweighted** | `Σ priceSum / Σ activeHours` (unweighted) |
| Days included | only days with energy rows **and** price rows; future days skipped | days that have any energy row | every calendar day of the month listed |
| Days with generation | `days_with_data` = included days | `daysWithData` = days with kWh>0 | `activeDays` = days with kWh>0 |
Any new KPI must pick one definition explicitly and say so in its label.

## 8. Missing / partial data behaviour
| Situation | Result |
|---|---|
| No price row for an hour with energy | price = 0 ⇒ revenue 0 for that hour; the 0 is included in "average price" (React/public) — silent understatement |
| No energy row | 0 kWh |
| Source "All" in FastAPI | HUPX and MEMO rows merged into one `{hour: price}` dict; last row wins, order not defined (R-D6) |
| DST 25-hour day | HUPX parse failure ⇒ no HUPX rows that day (R-D3); `H25` unsupported |
| Partial today | bridge writes all 24 buckets each cycle; future hours are 0.0 |
| Future date | FastAPI skips hardware; bridge only scrapes tomorrow's prices after 13:00 |
| Hour label outside `H1…H24` (historical `H0`, R-D13) | React `dailyAnalysis`/`monthlyAnalysis` and `public_dashboard` look up only `H1…H24` ⇒ such rows are **silently ignored** (the date still counts as a day with data in React monthly); FastAPI's union of hours includes them |
| Rows written by the legacy `EnergyDataService` | only hours present in the device response (15–17/day in the snapshot since 2026-04-16); the bridge always writes 24 buckets |

## 9. Rules for changing calculations
1. Locate **all** copies: `main.py` (2 handlers), `App.jsx` (daily+monthly `useMemo`), `public_dashboard` (`calcSummary`, `aggregateMonthly`), plus both energy calculators.
2. Do not silently recompute history: stored `energy_kwh` is the output of the algorithm *at write time*; changing an algorithm does not alter old rows unless the bridge re-upserts them (it does for today/yesterday and ≤14-day gaps).
3. Validate with synthetic cases like §5 and compare against known days before/after.
4. Update this doc and [13](13_KNOWN_LIMITATIONS_AND_RISKS.md) in the same change.

## 10. Historical label eras and gap lumping (second pass, 2026-11-03) **[V data / I cause]**
- **Label eras (R-D13).** The first code (`energy_service.py`, commits 8cedd5a/669a59e/950f61c) labelled `H{int(HH)}` (`H0…H23`); `6454cc1` introduced `hour_key = hour_int + 1` (`H1…H24`). The HEAD-committed SQLite has the old convention up to 2026-02-24. Prices were always `H1…H24`. Proof independent of timestamp semantics: on the DST spring-forward day 2025-03-30 the nonexistent hour is missing as `H2` in energy but `H3` in prices. Details and numbers: [16 §5.1](16_ONBOARDING_VERIFICATION_LEDGER.md). **Production (InsForge) contains no `H0` rows, no spikes and no data before 2026-04-01 (live check 2026-11-03, [16 §11](16_ONBOARDING_VERIFICATION_LEDGER.md)).**
- **Gap lumping (R-D14).** In both calculators the delta between two consecutive samples is added to the bucket of the *later* sample, however far apart the samples are. A data gap therefore books the whole gap's energy into one hour (`2026-03-15 H12 = 2,103.9 kWh` vs a normal peak of ~450–546 kWh/h). No outlier guard exists in either calculator [V for legacy; bridge has the same structure, I].
- **Negative and zero prices (R-D15).** Revenue = `kWh/1000 × price` is applied literally: negative-price hours yield negative revenue (242 producing hours in the committed snapshot); a 0 price (real or failed scrape) yields 0. Whether this matches the owner's economics (curtailment, feed-in) is a product decision [U] (Q-15).
