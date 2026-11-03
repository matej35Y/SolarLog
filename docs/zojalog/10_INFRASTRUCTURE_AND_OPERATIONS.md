# 10 — Infrastructure and Operations

**Evidence:** repo files and logs **[V]**; live hosting (Vercel project, FastAPI host, InsForge dashboard, launchd plist) was **not accessible** **[U]**.

## 1. Infrastructure inventory
| Piece | What it is | Evidence | Status |
|---|---|---|---|
| Owner's Mac | Runs the bridge (launchd) and Tailscale; macOS (`/Applications/Tailscale.app`, `launchctl`) | `bridge.py`, `service.sh` | **[V]** active (log written 2026-11-03 17:22) |
| SolarLog logger | Plant data logger, reachable on LAN and over the tailnet via a host/port candidate list | `bridge.py`, `config.py` | **[V]** answering (24 buckets today) |
| Tailscale | Peer-to-peer VPN that lets the Mac (and legacy FastAPI) reach the logger remotely | README, `ensure_tailscale()` | **[V]** used |
| InsForge (project `solar-earnings`) | Hosted Postgres + REST + SDK; skills installed for agents | `AGENTS.md`, `bridge.py`, `App.jsx`, `.insforge/` | **[V]** in use (admin + anon keys) |
| Second InsForge host | hard-coded in `public_dashboard` | `public_dashboard/index.html` L421 | **[U]** alive? same data? |
| Vercel | SPA rewrite config only (`frontend/vercel.json`) — project/URL unknown | file | **[U]** deployed? |
| FastAPI host | `Dockerfile` (python:3.11-slim, port 8080, comment "fly.io / insforge compute") and `railway.json` (`$PORT`) | files | **[U]** probably not deployed; image cannot run (see §3) |
| GitHub | `origin = github.com/matej35Y/SolarLog`; visibility unknown | `.git/config` | **[V]** exists; **[U]** public/private |
| Local dev | `.venv` (Py 3.13.2) + second env `venv` (Py 3.13.2); Node for Vite | filesystem | **[V]** |
| Git topology | 6 local branches (**4 not on origin**), 58 `refs/copilot/checkpoints/*` commits (3 sessions, 2026-10-31→11-03), 5 prunable stale worktrees under `~/copilot-worktrees/`, `matej35y-solarlog-doc-planning` @ `7150ab8` (legacy docs) | `git for-each-ref`, `git worktree list` | **[V]** 2026-11-03 — R-O1, R-O8 |
| Bridge liveness | last cycle 2026-11-03 21:38, "Cycle done", tomorrow's prices synced (929 cycles since 2026-10-02) | `bridge.log` | **[V]** |

## 2. Runtime topology
Bridge (Mac) → InsForge ← React app (browser, anywhere). FastAPI is optional/local. There is **no server of the owner's own in the production path** besides the Mac process.

## 3. Deployment artefacts and their problems
- **Dockerfile:** `FROM python:3.11-slim`; installs `gcc libpq-dev`; `pip install -r requirements.txt`; `COPY . .`; `uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers`.
  - `requirements.txt` has only `requests==2.31.0`, `python-dotenv==1.0.0`, `beautifulsoup4==4.12.2` (**exactly `bridge.py`'s third-party imports [V, AST]**; the FastAPI app also imports fastapi, fastapi_utils, pydantic_settings, sqlalchemy, pandas and needs uvicorn/Jinja2) → `app.main` imports `fastapi`, `fastapi_utils`, `jinja2`, `pydantic_settings`, `sqlalchemy`, `pandas` ⇒ **ImportError at start** (R-B7). Local venv uses newer versions (fastapi 0.115.8, etc.) and Python 3.13 vs image 3.11.
  - **No `.dockerignore`** ⇒ `COPY . .` would bake `.env*`, `.insforge/project.json`, `.venv`, `venv`, `node_modules`, `*.db`, logs into the image when built from this folder (R-S7).
  - `.insforge/project.json` is git-ignored, so a CI build from git would lack it and `insforge_client` would crash on import.
- **railway.json:** `build: pip install -r requirements.txt`, `start: python3 -m uvicorn … --port $PORT` — same dependency gap.
- **Frontend:** `npm run build` → `frontend/dist` (last local build 2026-10-02); Vercel rewrites every path to `/index.html`. Required env: `VITE_INSFORGE_URL`, `VITE_INSFORGE_ANON_KEY` (code has hard-coded fallbacks). `dist/` and `node_modules` are git-ignored (`frontend/.gitignore`).

## 4. Running things (local)
```bash
# Frontend
cd frontend && npm install && npm run dev            # Vite dev server; /api proxy → localhost:8000 (unused by App.jsx)
npm run build && npm run preview

# Bridge (production ingester) — from repo root
python3 scripts/bridge.py
./scripts/service.sh status | start | stop | restart | logs    # launchd label com.solarlog.bridge

# Legacy FastAPI — from repo root, venv active, needs .insforge/project.json and .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
# UI: /ui, /ui/daily, /ui/monthly; docs: /docs
```
Do **not** run `scripts/fill_missing_data.py`, `restart_scraper.py`, `migrate_*.py` or the scraper tests casually — they write to the production DB.

## 5. Logs and monitoring
- Bridge: stdout/stderr → `bridge.log` / `bridge.err.log` (repo root, git-ignored, 1.7 MB / 2.7 KB). `service.sh` points at a different path (R-O3). No log rotation, alerting, heartbeat or dashboard freshness indicator.
- FastAPI: stderr INFO logs only.
- Quick health check of the bridge: last `Cycle done.` timestamp within ~15–20 min; `grep -c "401 Client Error" bridge.log` for credential problems; `grep "Hardware Discovery FAILED"` for device/network issues.

## 6. Maintenance runbooks
**Bridge stopped / no new data:** `./scripts/service.sh status` → check Mac awake/online, Tailscale running (`tailscale status`), `bridge.log` tail, then restart service. After recovery the next cycle re-fetches today+yesterday (and ≤14 days if the latest date lags).
**401 from InsForge:** admin key in `.env.bridge` rejected/rotated (happened 2026-11-02). Update the key (never paste it in chat/docs), restart service.
**Missing HUPX day (DST):** see R-D3; requires a code fix + explicit decision on backfilling (writes to production).
**Interior gap in history:** bridge won't self-heal gaps older than yesterday (R-D9); needs a deliberate, approved backfill.
**Git/backup:** the refactor is uncommitted; back up the working tree before risky actions (R-O1). InsForge-side backup policy **[U]**.

## 7. Before changing infrastructure
Confirm which pieces are actually deployed (Vercel project, any FastAPI host) — the repo cannot tell. Fix `requirements.txt` and add `.dockerignore` before any container deploy. Never change production infra, rotate keys, or alter RLS without explicit authorization and a rollback plan.
