# 18 — Owner answers (2026-11-05), triaged against evidence

**Source:** `ZOJALOG_SYSTEM_ANSWERS_AND_SPECIFICATION.md`, uploaded by the owner on 2026-11-05 (written with an AI partner; its numbering "ans §1…§43" differs from the 51 questions Claude asked). The file embeds hostnames/IPs and is **not reproduced here**. Its uploaded copy currently sits **untracked** next to this doc (`docs/zojalog/ZOJALOG_SYSTEM_ANSWERS_AND_SPECIFICATION.md`, not covered by `.gitignore`): **do not `git add` it** — move it out of the repo or ignore it before any `git add docs/` (public GitHub remote).
**Scope of this doc:** records what was checked, what is locked, what contradicts evidence and what is still open. **No code, DB or git state was changed.** No InsForge access was used; checks ran against the working tree, `bridge.log` and the read-only working-copy `hupx_prices.db` (opened `mode=ro&immutable=1`).
**Status legend:** **LOCK** owner business decision, no conflict · **LOCK-U** owner fact, plausible but not verifiable here [U] · **CONFLICT** contradicted by [V] evidence · **OPEN** blocked / unanswered · **DEFER** collides with the owner's standing rule "as few changes as possible, no DB structural change unless an absolute must" → needs a scope decision (§4).

## 1. Contradictions with verified evidence
| # | Answer says | Evidence [V] | Consequence |
|---|---|---|---|
| C-1 | Peak 280–360 kWh/h; P_AC ≈ 350 kW "estimated"; reject hours > 1.02 × P_AC (ans §1, §37, checklist) | Snapshot Apr–Aug 2026 (same top rows as production, see 16 §11): max **546.4 kWh** (2026-04-08 H13); monthly max 546 / 516 / 509 / 486 / 459 (falls with summer temperature = a physical curve, not spikes). **515 of 2,336 producing hours (22 %) on 128 days exceed 357 kWh**; 18 hours on 11 days exceed 500 kWh | A 350 kW ceiling would flag ~22 % of legitimate hours. Real capacity is ≥ ~550 kW AC-equivalent; ceiling must come from the nameplate → Q-18 |
| C-2 | Timestamp = **end** of interval; samples 07:05…08:00 fall in H8 (ans §9) | `bridge.py::calculate_hourly_energy` uses `H{sample_time.hour + 1}`: the delta ending at 08:00 goes to **H9** | One of the two is off by one 5-min sample at every hour boundary (≤ 1/12 of an hour's energy moves to the next hour; **daily totals unaffected**). Sampling interval and key-776 semantics stay [U] → ground-truth comparison needed |
| C-3 | "Logs demonstrate the reset-recovery branch works" (ans §10) | Formula matches code (mean of previous and current power × elapsed) — **but** the function logs nothing; the only "reset" in `bridge.log` is a network `ConnectionResetError` | Formula LOCK; "works" is [U] |
| C-4 | Future hours do not exist / are not inserted (ans §12, §39) | Bridge returns all 24 labels (`range(1, 25)`, 0.0 when missing) and upserts 24 rows for today every cycle | Future hours are stored as 0.0 today; "do not insert" is a behaviour change (DEFER) |
| C-5 | Prices polled hourly, ingested dates skipped, MEMO < 10 requests/day (ans §20) | `run_cycle` scrapes HUPX + MEMO for today (+ tomorrow after 13:00 **Mac** time + gap days) **every 15-min cycle**, no skip check; `bridge.log`: **1,832 HUPX + 1,832 MEMO requests in 35 days** (≈ 52/day each on average; up to ~140/day while the Mac is awake all day) + one upsert per source per cycle | Not "< 10". Free-plan request budget and needless rewrites (R-D18) |
| C-6 | Maintenance: `python3 scripts/bridge.py --dry-run` (ans §30) | `bridge.py` has **no** argument parsing (`argparse`/`sys.argv`/`dry` → no match) | That command would start a normal, **writing** bridge. Do not use (R-O11) |
| C-7 | Live schema listing; anon = `SELECT` only (ans §22–23) | The listing is identical to repo `scripts/init_schema.sql`, not live catalog output (`zojalog_schema_check.sql` results still not received). That file also has `CREATE POLICY … FOR ALL USING (true) WITH CHECK (true)` **without** `TO <role>` (applies to anon too). `migrate_to_insforge.py` emits `INSERT … (id, …)` | "anon read-only" holds only if table GRANTs withhold writes — unverified (R-S3, Q-02, Q-20). Live tables may have had an `id` column |
| C-8 | 401 burst on 2026-11-02 = bridge started with an invalid key (ans §23) | Cycles at 00:02 and 00:17 succeed; first 401 at **00:32:56 inside an already-running process**; 717 lines until 14:42:09; restarts 14:41:55 and 14:44:53; clean since (cycle of 2026-11-05 17:20 syncs all tables) | The key stopped being accepted mid-run (rotated / revoked / expired [I]); a restart with a valid key fixed it. Owner to confirm cause (Q-24). "Writes work now" is [V] |
| C-9 | Internal inconsistencies in the answers: (a) missing price stays `NULL` (§5, §40) but `price … NOT NULL`; (b) fallback writes `source='memo_fallback'` (§5); (c) `ANOMALY_OVER_CAPACITY` flag (§37); (d) ingestion treats "the user's selected market" as benchmark (§3); (e) clamp night energy > 0.05 kWh to 0 (§37) | (a) NULL impossible without DDL → "no row". (b) adds a third `source` value the filters don't know and would show MEMO prices as HUPX revenue. (c) no column exists; "withheld from totals" needs code in the 4 duplicated places or DDL. (d) the toggle is client-side; the bridge cannot know it. (e) **H5 carries real production on 28 days (max 0.29 kWh)**; H1–H4, H22–H24 had 0 rows > 0.05 kWh | (a) adopt as "no row, never 0". (b)–(e) **not adopted** until the owner decides |
| C-10 | Adds ≥ 10 new capabilities (shared `zojalog_core`, MKD toggle, discount factor, alerting, retry/backoff, freezing, irradiance gap redistribution, plausibility flags, `updated_at` DDL, UI badge / dynamic hours / capture price) | Owner directive 2026-11-03: minimal changes; no structural DB change unless absolute must | Scope decision needed (§4) |

## 2. New findings produced while checking
- **N-1 Mac clock ≠ logger clock (R-O9) [V].** `SolarLogFetcher.fetch_day` labels rows with `datetime.now() - days_back` (the **Mac** clock) while `days_back` indexes the **logger's** days. Until 2026-11-03 both rolled over together (cycles at 00:0x already show `days_back=0` = 0.00 kWh). On 2026-11-05, cycles at 00:04…00:49 still show the previous day (715.65 kWh) as `days_back=0` and the day before (773.88 kWh) as `days_back=1`; the rollover only appears at **01:05**. So the Mac is now UTC+2 (the owner's client also reports UTC+2) while the logger is on CET (UTC+1). During that hour the previous day's data is written under D+1 and D−1's total under D; it self-heals at the first cycle after the logger's midnight, but stays wrong if the Mac sleeps inside that window [I]. The "13:00" tomorrow-price rule then fires at 12:00 CET (harmless early attempts) [I].
- **Logger clock = CET/CEST [V]:** (a) the rollover above; (b) clock-hour centroid of production Apr–Aug 2026 = 12.1–12.3 h (solar noon in Skopje ≈ 12:34 CEST; a UTC+3 or UTC+1 logger would give ≈ 13:34 / 11:34).
- **N-2 Uptime [V]:** 974 `Cycle start` lines in 34.2 days = **29 %** of the 3,283 possible 15-min slots → the Mac is awake only part of the time; completeness relies on backfill, freshness is irregular (R-O10).
- **N-3 Coverage hole candidate 2026-08-28 → ~2026-09-17 [U] (R-D19).** SQLite ends 08-27/28; bridge log starts 10-02 and backfills ≤ 14 days; the live check recorded only first/last row. Needs a per-day coverage query (Q-23).
- **N-4 DST on the energy side [I].** The bridge sorts samples by the time-of-day string, so a repeated 02:xx hour interleaves; it is night (deltas ≈ 0) so impact is negligible. The real defect is on the price side (`int('3B')`, R-D3).
- **N-5 `H3B` is compatible with minimal change [I].** Storing the repeated HUPX hour as `H3B` keeps H4…H24 aligned with energy buckets (`H{hour+1}`); UIs loop H1…H24, so an extra `H3B` price row is ignored and energy in that hour ≈ 0 ⇒ revenue unchanged. Only one fall-back day (2026-10-25) has been observed; the `'3B'` token for other days is [U].
- **N-6** The benchmark day `2026-03-29` (ans §43) **is not in production** (data starts 2026-04-01). The spring-forward case needs fixtures or 2027-03-28.

## 3. Status of each answer
| ans § | Topic | Owner answer | Status |
|---|---|---|---|
| 1 | Capacity | none given; ~350 kW "estimated" | **CONFLICT** C-1 → Q-18 |
| 2 | Nature of revenue | dashboard = gross spot valuation; optional discount factor | **LOCK** gross spot valuation (ADR-007); factor **DEFER**; whether real settlement differs is unanswered |
| 3 | Benchmark HUPX vs MEMO | keep both; legal default left unchecked | **OPEN** Q-19 |
| 4 | Negative prices | store real values; UI badge | **LOCK** (already stored as-is); badge **DEFER** |
| 5 | Missing price | never 0; UI "—"; fallback `memo_fallback` | **LOCK** "no row, never 0"; UI **DEFER**; fallback **CONFLICT** C-9 |
| 6 | Currency | EUR stored; MKD toggle optional | **LOCK** EUR; toggle **DEFER** |
| 7 | Average price | volume-weighted capture price is canonical | **LOCK**; UI change in 3 places when scheduled |
| 8 | Energy truth | SolarLog yield (billing meter is the legal basis) | **LOCK-U**; loss figures generic [U] |
| 9 | Timestamps | end-of-interval; CET/CEST | clock **[V]**; convention **CONFLICT** C-2 |
| 10 | Resets | trapezoid of previous/current power | **LOCK** formula [V]; "works" [U] C-3 |
| 11 | Yield counter | lifetime cumulative Wh | **LOCK-U** (consistent with the delta logic) |
| 12 | History / partial day | 30–90 days; cycle windows | cycle windows [V]; 30–90 d [U]; future hours C-4 |
| 13 | Other keys | bridge uses key 776 only | **LOCK** [V]; legacy key meanings [U] |
| 14 | Outages | network; logger buffers, bridge back-fills | **LOCK-U** (discovery failures verified, 16 §4.3) |
| 15 | Network path | gateway forwarding | **LOCK-U** (hosts/IPs deliberately not copied) |
| 16 | HUPX granularity | hourly DAM | **LOCK** [V]: 24 records/day still returned for 2026-11-06 (resolves Q-07) |
| 17 | DST | `H3B` for 25 h; `H3` absent for 23 h; UI dynamic keys | storage label **LOCK**; dynamic UI **DEFER** (N-5) |
| 18 | Publication times | HUPX ~12:45, MEMO 13:00–13:30 CET; 13:00 rule OK | **LOCK-U**; Mac timezone caveat N-1 |
| 19 | Revisions | final/immutable | **LOCK-U** |
| 20 | MEMO load | < 10 requests/day | **CONFLICT** C-5 |
| 21 | Backfill 2026-10-25 HUPX | wants a single-day backfill with `H3B` | intent **LOCK**; **needs explicit write approval at implementation time**, after tolerant parsing exists |
| 22–23 | Schema / permissions | listing; anon read-only | **OPEN / CONFLICT** C-7, C-8 |
| 24 | Quotas | generic ">500k rows, 500 MB" | [U]; row growth ≈ 26,280/yr is fine, request/egress quotas not stated |
| 25 | Lineage | SQLite → migrate script → bridge from 10-02 | partly [V]: the script only **writes a SQL file** (does not connect); hole N-3 |
| 26 | Test rows | zero synthetic rows; disable debug endpoints | only top-3 and sentinel were checked, no full audit [U]; disabling = **LOCK** intent (code later) |
| 27 | `updated_at` DDL | recommended | **DEFER** (DDL) |
| 28 | launchd | pauses while the Mac sleeps | **LOCK-U**; plist still missing (Q-21); uptime N-2 |
| 29 | Inventory | SPA on Vercel; `public_dashboard` to retire; FastAPI unmaintained | **LOCK** decisions; Vercel URL not given |
| 30 | Maintenance procedure | stop → `--dry-run` → start | **CONFLICT** C-6 |
| 31 | Alerting | 5 failed connects; no tomorrow-price by 16:00 | **DEFER** (new feature, channel undecided) |
| 32 | Git hygiene | `.gitignore` list | **LOCK** (= CLAUDE.md rule 2); coverage of `*.log`/`.device_cache` not yet re-verified |
| 33–34 | Branches / PR #1 | prune Copilot worktrees; work on `feature/ingestion-v2`; close PR #1 | **LOCK-U**; nothing executed — needs explicit go |
| 35 | Consolidation / naming | shared `zojalog_core`; ZojaLog / SolarLogZOJA | naming **LOCK**; library **DEFER** (C-10) |
| 36 | Sample gaps | fetch 5-min history; else distribute by irradiance curve | part 1 is already what the bridge does (it reads the logger's buffer); part 2 **DEFER** (modelled data; would need an "estimated" marker, CLAUDE.md rule 1) |
| 37 | Plausibility | night zero; ceiling; price −500…4000 | night **partly CONFLICT** (C-9e); ceiling **CONFLICT** C-1; price bounds **LOCK-U** |
| 38 | Freezing | older than T−2 immutable | **LOCK-U** in principle; today only days {0,1} are touched unless a gap > 1 triggers a ≤ 14-day re-fetch; a "force" option would be a new CLI |
| 39 | Partial days | future hours not inserted | C-4 **DEFER** |
| 40 | Retry | 3 retries 5/20/60 s; failure never overwrites | intent **LOCK**; a failed scrape already writes nothing [V]; a single bad HUPX row drops the day (R-D3) |
| 41–43 | Validation | ground truth: logger "Yield Today", utility statements; ±1.5 % (> 3 % = error); 5 days | **LOCK-U**; tolerances generic [U]; exports not yet supplied; 2026-03-29 impossible (N-6) |

## 4. Proposed phasing — **not approved, no code until the owner picks**
- **Phase 0 — information only:** nameplate AC/DC capacity (Q-18); legal benchmark (Q-19); output of `zojalog_schema_check.sql` (Q-20); launchd plist (Q-21); Mac timezone / always-on plan (Q-22); per-day coverage 2026-08-20…10-05 (Q-23); cause of the 11-02 key failure (Q-24); ground-truth export for ~3 days.
- **Phase 1 — minimal ingestion safeguards in `scripts/bridge.py`, each independently approvable:** (1) tolerant HUPX parse: `3B` → `H3B`, one bad row must not drop the day (R-D3); (2) derive dates and the 13:00 rule from the plant's timezone instead of the Mac clock (R-O9); (3) skip-if-complete for prices and do not rewrite frozen days (R-D18); (4) write guards that **log-and-skip** (label whitelist, price bounds, owner-supplied energy ceiling) — no flags, no DDL.
- **Phase 2 — deferred, separate approval:** UI changes (capture price, "—" for missing price, negative badge, dynamic hours), DDL (`updated_at`, flags), alerting, `zojalog_core`, MKD toggle, discount factor, gap redistribution.
- **Phase 3 — ops:** fixtures/tests, a staging InsForge project, plist in repo, host (Pi/VM).
- **Writes/authorizations still required:** the single-day 2026-10-25 HUPX backfill, any DDL, any git commit/push/branch/prune, any deletion.

## 5. Reproduction (read-only)
`grep -c "Cycle start" bridge.log` (974) · `grep -ac "↳ MEMO" bridge.log` (1,832) · `grep -an "starting up" bridge.log` (restarts) · awk over `Cycle start` / `days_back=` / `hourly buckets` lines for 2026-11-05 00:00–01:30 (N-1) · `grep -n "argparse\|sys.argv\|dry" scripts/bridge.py` (none) · SQLite `select count(*) from energy_generation where energy_kwh>357` on a read-only/immutable open of the working-copy snapshot (C-1).

## 6. Owner follow-up (2026-11-05 17:50)
- **Capacity (Q-18):** SolarLog inverter page screenshot: 13 inverters, generator (DC) power 11 × 50 kWp + 15 + 20 = **585 kWp**; AC ratings not shown. Observed max 546.4 kWh/h = 93 % of 585 ⇒ consistent with C-1's finding. Candidate plausibility ceiling ≈ **600 kWh/h** (585 × ~1.02), as a named constant. The page has SAVE/RECALC buttons: never press them.
- **Benchmark (Q-19):** MEMO is mainly used, HUPX only for comparison. Frontend default is `hupx` (Q-27). The `3B` defect therefore affects the comparison source only; revenue in the MEMO view is unaffected.
- **Key (Q-24):** reset on the InsForge site on 11-02, not updated in the static-PC script copy — explains the mid-run 401s (C-8); Windows copy status unknown (Q-26).
- **Timezone (Q-22):** Mac currently abroad; the owner does not want to change it; the fix is code-side (plant-timezone dates).
- **Run location (ADR-014, R-O12):** intended host is the 24/7 Windows PC; what runs where is unverified (Q-26).
- **Approved for implementation (not yet started):** (1) skip complete price scrapes (in-memory set of `(date, source)` stored with ≥ 23 rows; retry until published); (2) dates and the 13:00 rule from the plant timezone, stdlib only (EU DST rule); (3) log-and-skip implausible values (energy row > 600 kWh/h, price outside −500…4000 €/MWh, label outside `H1…H24`/`H3B`) — skip only the offending row, keep the stored value, warn once per run. **Pending:** `3B`→`H3B` (explained to the owner first).
- **Method:** built in a scratch copy, tested with synthetic inputs, shown as a diff; the live `bridge.py` is untouched until the owner approves; previous file kept for rollback.
