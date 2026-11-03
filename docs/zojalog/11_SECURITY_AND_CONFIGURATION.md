# 11 — Security and Configuration

**Evidence:** code/config read **[V]**. Nothing was exploited or tested against live systems. `.env*` files and `.insforge/project.json` were **deliberately not read** (names and sizes only). Items needing live access are tagged **[U]**.
**Handling rule:** never print or copy secret values into docs, code, chat or commits. This document names locations only.

## 1. Configuration inventory (names only)
| Where | Variables / keys | Notes |
|---|---|---|
| `app/core/config.py` (+ `.env`) | `APP_NAME, DEBUG_MODE, CACHE_TIMEOUT, SCRAPER_NAME, ENERGY_DEVICE_IP, ENERGY_DEVICE_TAILSCALE_IP, USE_TAILSCALE_FIRST` | Defaults hard-coded in source incl. two network addresses |
| `scripts/bridge.py` (+ `.env.bridge`, CWD-relative) | `INSFORGE_URL, INSFORGE_ANON_KEY, INSFORGE_API_KEY` (admin), `ENERGY_DEVICE_IP, ENERGY_DEVICE_TAILSCALE_IP, USE_TAILSCALE_FIRST, SOLARLOG_CANDIDATES` | Hard-coded InsForge URL default; Tailscale host default |
| `app/models/insforge_client.py` | `.insforge/project.json` → `oss_host`, `api_key` | CWD-relative, read at import; git-ignored |
| React (`frontend/.env`, Vite) | `VITE_INSFORGE_URL, VITE_INSFORGE_ANON_KEY` | Hard-coded fallbacks in `App.jsx` L13–14 |
| `.env.example` | `DEBUG_MODE, CACHE_TIMEOUT, SCRAPER_NAME, ENERGY_DEVICE_IP, ENERGY_DEVICE_TAILSCALE_IP, USE_TAILSCALE_FIRST` | only file meant to be committed |
| `.env.local` | InsForge keys for "app code" per `AGENTS.md` | not read |
Files on disk: `.env`(282 B), `.env.bridge`(500 B), `.env.local`(177 B), `.env.example`, `frontend/.env`(152 B). `.gitignore` ignores `.env*` (except `.env.example`), `.insforge`, `*.db`, `*.log`, agent skill dirs.

Values that **must match across components**: InsForge project/host (bridge, React, FastAPI, public_dashboard — the last differs), device address candidates, `hour`/`source` conventions ([02 §7](02_ARCHITECTURE_AND_DATA_FLOW.md)).

## 2. Authentication / authorization model
- Dashboards: **no user auth**. Reads use the InsForge **anon** key (embedded in client JS — public by design). `public_dashboard` embeds a hard-coded anon JWT.
- Bridge: **admin key** (`INSFORGE_API_KEY`), used with the raw-SQL endpoint (full DB power). FastAPI: `api_key` from `.insforge/project.json` (privilege level **[U]**, likely admin).
- FastAPI app: **no auth on any of 27 routes**; CORS `allow_origins=["*"]` with `allow_credentials=True`.

## 3. Findings (details & IDs in [13](13_KNOWN_LIMITATIONS_AND_RISKS.md))
| ID | Severity | Finding | Status |
|---|---|---|---|
| R-S1 | Critical if FastAPI is reachable | Unauthenticated GET endpoints write fabricated/hard-coded rows to production (`/api/debug/add-test-data`, `add-april-data`, `add-mar14-prices`); open CORS | [V] |
| R-S2 | Critical if reachable | SQL built by string interpolation in `MockQuery` (`database.py` L78–117, L194–213) with user-controlled `source` and `date` (path/query) → injection into an admin-privileged raw-SQL endpoint | [V code] not exploited |
| R-S3 | High | `init_schema.sql` write policies `FOR ALL USING (true) WITH CHECK (true)` have no role restriction; anon key is public. Whether anon can write depends on GRANTs | **[U]** verify on live DB |
| R-S4 | **Low-Med** (re-rated 2026-11-03) | `.env`, `.env.bak`, `.env.hardware`, `hupx_prices.db`, `energy.db`, `hupx_data.db` are tracked and on `origin/main`, and the GitHub repo is **public**. The *committed* env files hold 5 / 3 / 3 non-credential keys (bool, int, LAN/Tailscale host values); a pattern scan of all 12 GitHub commits found no JWT/Bearer/key/token/password material. Residual: network topology disclosed (`config.py`, `.env`, `debug_connections.py`), OS username in `hupx_scraper.log`. The **working-tree** `.env` (282 B) differs from the committed one (146 B) and was deliberately not read | [V] committed state; [U] working-tree/untracked files |
| R-S5 | Medium | Anon keys/URLs and network addresses hard-coded in source (`App.jsx`, `public_dashboard`, `bridge.py`, `config.py`, test/debug scripts) | [V] |
| R-S6 | Medium | Admin key used by an always-on Mac process; a 401 burst on 2026-11-02 indicates key rotation/invalidity | [V log] |
| R-S7 | Medium | No `.dockerignore`; `COPY . .` would bake secrets/envs into images | [V] |
| R-S8 | Low | `/api/debug/test-network-connectivity` and `test-energy-connection` disclose internal IPs/URLs to any caller | [V] |
| R-S9 | Low | `X-SL-CSRF-PROTECTION`/browser-like headers used to talk to the logger; the logger's web interface is plain HTTP (secured only by network boundary/Tailscale) | [V] |
| R-S10 | **Low** (verified 2026-11-03) | 58 local `refs/copilot/checkpoints/*` commits (3 Copilot sessions, 2026-10-31→11-03) snapshot the tree and all contain `.env*` file names. **Content scan (owner-authorised, values never printed): 90 unique blobs reachable from the refs — 69 text files scanned line by line, 21 binaries (`.DS_Store`, `.pyc`, 3 `.db`) scanned byte-wise — with patterns for JWTs, `anon_`/`ik_` keys, `Bearer` tokens, key/secret/token/password assignments, AWS/GitHub tokens, PEM keys and URLs with credentials: 0 credential hits.** The only `.env*` blobs are 3 distinct files holding bool/int/`host:port`/private-IP values (no secret-like key names; one is a 2-key variant not in HEAD). Across all 58 checkpoint trees there are only 60 distinct paths: the **old flat tree** (`app/`, root scripts/tests, `.idea/`, DBs, logs), the three legacy docs, `AGENTS.md` (names the InsForge project host, no key) and the three `.env*` files above — **no** `.env.bridge`, `.env.local`, `.insforge/project.json`, `frontend/`, `scripts/`, `tests/` or `docs/` (so no hard-coded anon keys, and the checkpoints are **not a backup of the refactor**). One false positive: a 176-character hyphen separator line in `README.md`. Residual: network-topology values (LAN/Tailscale host:port) — same exposure class as R-S4; the refs sit outside `refs/heads`, so `git push`/`--all` do not send them, `--mirror`/bundles would | [V] |

## 4. Recommended direction (not performed — requires owner approval)
1. Decide whether FastAPI stays; if it runs anywhere reachable, remove/guard debug writers and parametrize SQL (or retire the MockSession path).
2. On the live DB (admin): review `anon` GRANTs/policies; scope write policies `TO service_role`/admin only.
3. Review contents of tracked env files; rotate anything sensitive; decide on history clean-up (affects collaborators) and remove files from tracking.
4. Remove hard-coded fallbacks; rely on env at build time.
5. Add `.dockerignore`; fix `requirements.txt` before any container build.
6. Add alerting for bridge 401/outage.

## 5. Safe-handling rules for future sessions
- Do not read `.env*` / `.insforge/project.json`. If a key is needed, ask the owner.
- Do not run commands that echo environment values.
- Do not add secrets to docs/tests; when quoting code, redact keys.
- Treat any request that would call the debug writers or run write-capable scripts as requiring explicit approval (CLAUDE.md rule 3).
