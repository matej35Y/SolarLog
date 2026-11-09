#!/usr/bin/env python3
"""
ZojaLog — targeted READ-ONLY InsForge check (free-plan safe).

What it does : 12 tiny HTTP GET requests (hard cap 16) against InsForge's *read* endpoint
               /api/database/records/<table>, each with LIMIT <= 30 rows. Nothing else.
What it never: no writes, no POST/PUT/PATCH/DELETE, no raw SQL, no admin key, no full-table scans,
               no retries. Credentials are read in-process from frontend/.env (public anon key)
               and are never printed.
TLS          : verified by default (uses the 'certifi' CA bundle if installed). If your Python has no root
               certificates (SSL: CERTIFICATE_VERIFY_FAILED), re-run with --insecure — safe enough here because
               only the PUBLIC anon key is sent and only a few data rows come back; never use it with an admin key.
Usage        : cd ~/Desktop/ZojaLog && python3 zojalog_readonly_check.py --plan   # show requests, send nothing
               cd ~/Desktop/ZojaLog && python3 zojalog_readonly_check.py          # run for real
Output       : data rows only (dates, hour labels, kWh, prices). Safe to paste back.
"""
import argparse, json, os, re, ssl, sys, time, urllib.error, urllib.parse, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--plan", action="store_true", help="print the requests that WOULD be sent, send nothing")
ap.add_argument("--insecure", action="store_true", help="skip TLS certificate verification (diagnostic use only)")
ap.add_argument("--root", default=os.getcwd(), help="repo root (default: current directory)")
args = ap.parse_args()

def env(path):
    d = {}
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip().strip("\"'")
    except FileNotFoundError:
        pass
    return d

fe = env(os.path.join(args.root, "frontend", ".env"))
BASE, KEY = fe.get("VITE_INSFORGE_URL"), fe.get("VITE_INSFORGE_ANON_KEY")
if not (BASE and KEY):
    try:  # fall back to the constants the shipped React app already contains
        t = open(os.path.join(args.root, "frontend", "src", "App.jsx"), encoding="utf-8").read()
        BASE = BASE or re.search(r"https?://[A-Za-z0-9.\-]+insforge\.app", t).group(0)
        KEY = KEY or re.search(r"anon_[A-Za-z0-9]+", t).group(0)
    except Exception:
        sys.exit("Could not find the anon key / URL (looked in frontend/.env and frontend/src/App.jsx). Run from the repo root.")
BASE = BASE.rstrip("/")
BUDGET, used = 16, 0
if args.insecure:
    CTX = ssl._create_unverified_context()
else:
    try:
        import certifi
        CTX = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        CTX = ssl.create_default_context()

def redact(s):
    for secret in (KEY,):
        if secret:
            s = s.replace(secret, "[REDACTED]")
    return s

def build(table, params):
    qs = "&".join(f"{k}={urllib.parse.quote(str(v), safe='.,()*:-')}" for k, v in params.items())
    return f"/api/database/records/{table}?{qs}"

def get(label, table, params, count=False):
    """The ONLY network primitive: one GET to the read endpoint."""
    global used
    path = build(table, params)
    assert path.startswith("/api/database/records/")
    assert int(params.get("limit", 0)) in range(1, 31), "every request must carry a small LIMIT"
    if args.plan:
        print(f"  GET {path}" + ("   [Prefer: count=exact]" if count else "")); return None
    if used >= BUDGET:
        sys.exit("request budget exhausted — stopping")
    used += 1
    headers = {"Authorization": f"Bearer {KEY}", "Accept": "application/json"}
    if count:
        headers["Prefer"] = "count=exact"
    req = urllib.request.Request(BASE + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            data = json.loads(r.read().decode() or "[]")
            res = (r.status, data, r.headers.get("Content-Range"))
    except urllib.error.HTTPError as e:
        res = (e.code, redact(e.read().decode()[:200]), None)
    except Exception as e:
        msg = redact(f"{type(e).__name__}: {e}")[:200]
        if "CERTIFICATE_VERIFY_FAILED" in msg:
            msg += "  -> re-run with --insecure (or run Python's 'Install Certificates.command' / pip install certifi)"
        res = ("ERR", msg, None)
    time.sleep(0.6)
    st, data, cr = res
    if isinstance(data, list):
        print(f"[{st}] {label}: {len(data)} row(s)" + (f" | content-range={cr}" if cr else ""))
        for row in data[:30]:
            print("     ", json.dumps(row, separators=(",", ":")))
    else:
        print(f"[{st}] {label}: {data}")
    return res

def labels(res):
    return sorted(int(r["hour"][1:]) for r in res[1]) if res and isinstance(res[1], list) else []

print(("PLAN (nothing is sent):" if args.plan else "RUN:") + f" read-only GETs, budget {BUDGET}, anon key (not printed)")
if args.insecure and not args.plan:
    print("WARNING: TLS certificate verification is DISABLED for this run (--insecure).")
r0 = get("energy: earliest row", "energy_generation", {"select": "date,hour,energy_kwh", "order": "date.asc", "limit": 1})
if not args.plan and (not r0 or r0[0] != 200):
    sys.exit("First request failed — stopping without further requests.")
get("energy: latest row", "energy_generation", {"select": "date,hour", "order": "date.desc", "limit": 1})
get("prices: earliest row", "hourly_prices", {"select": "date,hour,source", "order": "date.asc", "limit": 1})
get("H0 energy rows: earliest (+exact total)", "energy_generation", {"hour": "eq.H0", "select": "date,hour", "order": "date.asc", "limit": 1}, count=True)
get("H0 energy rows: latest", "energy_generation", {"hour": "eq.H0", "select": "date,hour", "order": "date.desc", "limit": 1})
e = get("energy 2025-03-30 (DST spring-forward)", "energy_generation", {"date": "eq.2025-03-30", "select": "hour", "order": "hour.asc", "limit": 30})
p = get("HUPX prices 2025-03-30", "hourly_prices", {"date": "eq.2025-03-30", "source": "eq.hupx", "select": "hour", "order": "hour.asc", "limit": 30})
get("energy 2026-03-15 (spike day)", "energy_generation", {"date": "eq.2026-03-15", "select": "hour,energy_kwh", "order": "hour.asc", "limit": 30})
get("energy 2025-04-23 H19 (spike)", "energy_generation", {"date": "eq.2025-04-23", "hour": "eq.H19", "select": "date,hour,energy_kwh", "limit": 2})
get("top-3 hourly energy values overall", "energy_generation", {"select": "date,hour,energy_kwh", "order": "energy_kwh.desc", "limit": 3})
h = get("HUPX rows stored for 2026-10-25", "hourly_prices", {"date": "eq.2026-10-25", "source": "eq.hupx", "select": "hour", "order": "hour.asc", "limit": 30})
get("price sentinel (< -1000)", "hourly_prices", {"price": "lt.-1000", "select": "date,hour,source,price", "limit": 3})
if not args.plan:
    le, lp = labels(e), labels(p)
    if le and lp:
        print(f"\nDST check 2025-03-30: energy labels {le[0]}..{le[-1]} missing {sorted(set(range(le[0], le[-1]+1))-set(le))}; "
              f"HUPX labels {lp[0]}..{lp[-1]} missing {sorted(set(range(lp[0], lp[-1]+1))-set(lp))}")
    print(f"HUPX 2026-10-25 rows: {len(h[1]) if h and isinstance(h[1], list) else 'n/a'}")
    print(f"-- requests used: {used}/{BUDGET} (all GET)")
