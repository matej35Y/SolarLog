# 06 — Hardware Integration and Data Collection

**Evidence:** code **[V]**; runtime behaviour from `bridge.log` / `bridge.err.log` (919 cycles, 2026-10-02 → 2026-11-03) **[V]**. The launchd plist (`~/Library/LaunchAgents/com.solarlog.bridge.plist`) lives outside the repo and was not inspected **[U]**. No live hardware calls were made during onboarding.

## 1. Two collectors exist
| | **Bridge** (`scripts/bridge.py`) | **Legacy** (`app/services/solarlog_client.py` + FastAPI loops) |
|---|---|---|
| Role | **Production ingester** | Legacy/local; also used by `/api/analysis/by-date` |
| Runs | Single process on the owner's Mac, launchd | Inside uvicorn (when someone runs it) |
| Cadence | every 15 min (`CYCLE_MINUTES`) | every `CACHE_TIMEOUT` (3600 s), ×3 loops (R-B1) |
| Writes | bulk `ON CONFLICT DO UPDATE` via raw SQL (admin key) | `MockSession` inserts (no updates persist; `id` column issue) |
| Device discovery | candidate list + cache + Tailscale auto-start | `device_ip` + optional Tailscale fallback |

## 2. Hardware communication
- Protocol: HTTP `POST /getjp` to the logger's web server (non-standard ports in bridge candidates, e.g. 8080/8085 behind the Tailscale host; plain port 80 on the LAN). Payload/headers in [05 §2](05_SOLAR_DOMAIN_AND_CALCULATIONS.md).
- **Bridge discovery** (`SolarLogFetcher`): priority list = Tailscale host (+ alternate 8080/8085 port) → `ENERGY_DEVICE_IP` → `SOLARLOG_CANDIDATES` (comma list). Last good address cached in `./.device_cache` (CWD-relative). On any fetch error: `ensure_tailscale()` then `_discover_device()` probes each candidate with `{"777":{"1":null}}` (3 attempts each; HTTP 503 = "busy", waits 3 s).
- `fetch_day(days_back)`: up to 3 attempts, 25 s timeout, 503 ⇒ wait 4 s; returns `[]` on failure (never raises). Note: inside `_discover_device` the 3 attempts apply to non-200 status codes and 503; a connection exception moves straight to the next candidate.
- `ensure_tailscale()` shells out to `tailscale status`; if stopped, runs `tailscale up --accept-routes=true` (tries the macOS app binary then `tailscale`).
- **Legacy** (`EnergyDataService._try_connection_with_fallback`): tries Tailscale IP first if `USE_TAILSCALE_FIRST`, else LAN first; 2 attempts on the primary (2 s apart), 1 on the secondary; 30 s timeout. Network errors become `(None, None)`.
- Network facts: remote access relies on **Tailscale** (peer-to-peer VPN) — the hostname/IP values are in `.env`, `config.py` defaults and `bridge.py` defaults (not repeated here).

## 3. The bridge cycle in detail (`run_cycle`, L439–513)
**Energy**
1. `max(date)` of `energy_generation`. `days_to_fetch = {0,1}` always (today for intraday, yesterday to finalize).
2. If `gap = today − latest > 1`: add `0…min(gap,14)`. If table empty: add `0…6`.
3. Fetch oldest→newest; each non-empty day → one multi-row upsert of 24 rows (`H1…H24`, zeros included).
**Prices**
4. `max(date)` of `hourly_prices`; `dates = {today}`; if `gap > 0`: add `0…min(gap,14)` days back; empty table: 7 days.
5. After **13:00 local** add tomorrow (day-ahead results).
6. For each date: HUPX scrape → upsert; MEMO scrape → upsert.
7. Sleep 15 min; unexpected exceptions are logged and the loop continues.
Consequences: interior gaps older than yesterday are never refilled (R-D9); stored history for today/yesterday is overwritten every cycle (R-D8); a failed HUPX parse is not retried after the date rolls over (R-D3).

## 4. Operating the bridge
```bash
python3 scripts/bridge.py                 # foreground; reads ./.env.bridge (INSFORGE_URL, INSFORGE_ANON_KEY, INSFORGE_API_KEY, ENERGY_DEVICE_IP, ENERGY_DEVICE_TAILSCALE_IP, USE_TAILSCALE_FIRST, SOLARLOG_CANDIDATES)
./scripts/service.sh status|start|stop|restart|logs   # launchctl wrapper for com.solarlog.bridge
```
- Logs: `bridge.log`/`bridge.err.log` in the repo root (both ignored by git via `*.log`). `service.sh` reads `LOG_FILE=/Users/…/Desktop/bomba/bridge.log` — a **different folder name** than the active log (`…/ZojaLog/bridge.log`); `service.sh status/logs` may show a stale file **[I]** (R-O3).
- There is no health endpoint, alerting or heartbeat; check `bridge.log` for `Cycle done`.

## 5. Observed reliability (from the log) **[V]**
| Event | Count / dates |
|---|---|
| Cycles logged | 929 over 33 days (2026-10-02 → 11-03 21:38; 919 at first documentation) — counts below re-verified 2026-11-03 21:40; per-day table in [16 §4](16_ONBOARDING_VERIFICATION_LEDGER.md) |
| `Hardware Discovery FAILED` | 372 total; days with failures: 10-02 (90), 10-03 (117), 10-11 (42), 10-12 (55), 10-13 (39), 10-28 (23) + a few singles |
| HUPX/MEMO network failures | 10-11…10-13 and 10-28 (Mac offline/DNS) |
| `401 Unauthorized` on rawsql | **717 events, all on 2026-11-02** — admin key rejected that day (`.env.bridge` and `bridge.py` were modified later that day); cycles succeed on 11-03 **[I: key problem fixed]** |
| HUPX `invalid literal for int(): '3B'` | 18 failures for target **2026-10-25** (DST fall-back): 8 in cycles run on 10-24 (the after-13:00 "tomorrow" lookup) and 10 on 10-25, plus 1 network failure ⇒ **19 attempts, 0 successes** — the bridge never stored HUPX prices for that date |
| `Gap detected` (backfill) events | **0** in the whole log — the gap-backfill path has never fired in this period |
| Day with no successful energy sync | 2026-10-12 |
During outages nothing is written; after recovery today/yesterday are re-fetched, so short outages self-heal if the device still serves that `days_back`.

## 6. Failure modes → effects
| Failure | Effect |
|---|---|
| Hardware unreachable | cycle logs discovery failure, no energy upsert; dashboard shows stale data without warning |
| Tailscale stopped | `ensure_tailscale()` attempts restart; else as above |
| InsForge unreachable / 401 | `upsert` returns False (warning), data not stored; no retry queue — next cycle re-fetches only recent days |
| HUPX/MEMO unreachable | `[]` returned; prices for that date not updated |
| HUPX returns `ProductH` like `3A/3B` | whole HUPX list for the day is lost |
| MEMO layout change | `[]` (bridge) — safer than the FastAPI scraper's column fallback |
| SolarLog 503 | retried (3×, 3–4 s waits) |
| Mac asleep/off | no ingestion (single point of failure) |

## 7. Before changing collection code
1. Keep both calculators' behaviour documented in [05](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) consistent or explicitly diverge.
2. The bridge overwrites rows: any change that alters computed values will rewrite today/yesterday (and ≤14-day gaps) — get approval before shipping algorithm changes.
3. Never run the bridge pointed at an unfamiliar database; it uses an admin key.
4. If adding fields to the upsert, `upsert()` builds columns from the first record's keys — ensure the live table has them.
