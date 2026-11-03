# 08 — Frontend and Design System

**Evidence:** all CSS/JS/HTML read in full **[V]**; tokens extracted from `:root` **[V]**; the UI was **not rendered in a browser** during onboarding, so visual claims are derived from CSS/markup, not screenshots **[I for appearance]**. One behaviour (day navigation) was executed in Node under three time zones **[V-run]**.

## 1. Three UIs exist
| UI | Files | Data access | Status |
|---|---|---|---|
| **React SPA (primary)** | `frontend/index.html`, `src/main.jsx`, `src/App.jsx`, `src/index.css`, `src/styles.css` | InsForge directly via `@insforge/sdk` (anon key) | Current; `dist/` last built 2026-10-02; Vercel SPA rewrite in `vercel.json` |
| **Legacy Jinja UI** | `app/templates/{index,daily,monthly}.html`, `app/static/js/{daily,monthly}.js`, `app/static/css/styles.css` | FastAPI `/api/analysis/*` | Legacy; served by uvicorn at `/ui*` |
| **`public_dashboard`** | `frontend/public_dashboard/index.html` (single file, inline CSS+JS) | InsForge REST `/api/database/records/<table>` with a hard-coded anon JWT, **different InsForge host** | Unclear status **[U]** |

## 2. React SPA
- `main.jsx` → `<StrictMode><App/></StrictMode>`; `App.jsx` (≈1,015 lines) holds **everything**: helpers (`fmt`, `fmtDate`, `fmtShortDate`, `formatMonthLabel`, `getMonthOptions`), `ErrorBoundary` (class), `Dashboard` (function), default export `App`. `src/pages`, `components`, `hooks`, `theme` are **empty directories**. `src/App.css` is an unused Vite-template leftover.
- **No router, no state library.** View switching = `activeTab ∈ {'daily','monthly'}`.
- **State:** `selectedDate`, `selectedMonth`, `selectedSource` (default `hupx`), `chartType ∈ {combo,bar,line}`, `loading`, `error`, `dailyData{prices,energy}`, `monthlyData{prices,energy}`.
- **Data flow:** on mount, query latest `energy_generation.date` → set date/month (L173–192). On any of tab/date/month/source change → `fetchDaily` or `fetchMonthly` (L195–270). `setInterval` refresh every 5 min (L273–282). Both fetches use `Promise.all` over prices+energy; errors set a generic message.
- **Derivations (`useMemo`)**: `dailyAnalysis` (24-row map, totals, avg price over `energy>0` hours, max hourly energy), `monthlyAnalysis` (price/energy maps keyed `date_Hn`, per-day sums, month totals), chart data for each. Formulas: [05](05_SOLAR_DOMAIN_AND_CALCULATIONS.md) §6–7.
- **Dependencies actually imported:** `react`, `react-dom`, `@insforge/sdk`, `chart.js` (`registerables`), `react-chartjs-2`, `lucide-react`. **Unused in package.json:** `@mui/material`, `@mui/x-date-pickers`, `@emotion/*`, `axios`, `dayjs`, `react-router-dom`. `vite.config.js` `/api` proxy (→ `localhost:8000`) is unused by `App.jsx`.
- **Credentials in source:** `VITE_INSFORGE_URL` / `VITE_INSFORGE_ANON_KEY` with **hard-coded fallbacks** in `App.jsx` L13–14 (R-S3/R-S5). Don't copy them elsewhere.
- **Known bug R-F1:** day navigation (L158–170) uses `new Date(d+'T00:00:00')` + `toISOString()`. Executed with `TZ=Europe/Skopje`: ◀ from 2026-11-03 → **2026-11-01** (skips a day), ▶ stays **2026-11-03** (stuck). Correct in UTC/New York. `public_dashboard.changeDate` anchors at noon and is correct. Initial default date also uses UTC (`App.jsx` L116–117) but is overwritten by the latest DB date. Re-run 2026-11-03 (Node 22, `TZ=Europe/Skopje|UTC|America/New_York`): same result; PR #1's `Date.UTC(...)` version and `public_dashboard.changeDate` (noon anchor) are correct in all three zones.
- **Second-pass observations [V, code]:** (1) **R-F14** — `dailyAnalysis` initialises `maxEnergy = 1` (L309), so the *Peak Power* KPI can never show less than `1.0 kWh/h` (a no-production day shows 1.0, and the "Share" bars divide by it). (2) `TrendingUp` and `BarChart2` are imported but unused (ESLint passes because `varsIgnorePattern: '^[A-Z_]'`). (3) The source filter `if (source) pQuery.eq('source', source)` ignores the return value; this works because `@insforge/sdk` 1.2.4 wraps `@supabase/postgrest-js` 1.21.4, whose `eq()` mutates `this.url` and returns `this`. (4) Every fetch (incl. the 5-min auto-refresh) sets `loading=true`, replacing the chart with the spinner each time; on error the previous data stays visible under the red alert. (5) Rows labelled outside `H1…H24` are ignored (R-D13).

## 3. Views, components and interactions (React)
| Area | Elements | Interaction |
|---|---|---|
| Top nav `sl-nav` | brand (sun icon + "SolarLogZOJA ☀️"), links Daily / Monthly, static "Live" pill | click switches `activeTab` |
| Header `sl-dash-header` | eyebrow "Energy Intelligence", H1, subtitle, badges: source (green) + date/month (mono, gray) | display only |
| Tab bar `sl-tab-bar` | "Daily Breakdown" / "Monthly Overview" (duplicate of nav links) | switches tab |
| Controls `sl-controls` | Daily: ◀ date input ▶; Monthly: ◀ month select (optgroups by year 2024→max(current,2026)) ▶; Source select (HUPX (Hungary)/MEMO (Macedonia)); Refresh button (spins while loading) | change → refetch |
| KPI grid `sl-kpi-grid` (4 cards) | Daily: Total Energy (indigo), Total Revenue (teal), Avg. Price (amber), Peak Power kWh/h (blue). Monthly: Monthly Energy MWh, Monthly Revenue (+~€/day), Avg. Spot Price ("Weighted spot avg" label — actually unweighted), Active Generation days | display |
| Chart card `sl-chart-card` (height 360 px) | Daily: combo/bar/line toggle (`chart-toggle`), energy bars + price line, dual axes. Monthly: daily revenue bars + generation (MWh) line | toggle, tooltips (index mode) |
| Table card `sl-table-card` | Daily: 24 rows Hour / Production / Share (mini bar) / Market price / Revenue. Monthly: one row per day (pointer cursor) | **monthly row click → daily view of that date** |

## 4. Legacy Jinja UI (for completeness)
- `/ui` overview: hero with "Today's Energy / Revenue / Avg. Price" strip (fetches `/api/analysis/by-date/<today>?source=hupx`, uses `arithmetic_avg_price_per_mwh`), feature cards, footer date.
- `/ui/daily` and `/ui/monthly`: `<input type=date|month>`, source select (**All**/HUPX/MEMO), Load button, KPIs, area/bar/line chart (Chart.js 4.4 from jsDelivr CDN), table; monthly row click → `/ui/daily?date=…`. PR #1 (origin/main, 2026-11-02) added date/month navigation controls to these files (not present in the local working tree).
- Chart colours here still use an older dark-theme palette (`#18E299` greens, `rgba(255,255,255,.055)` grid, `#0f0f1a` tooltip) on the light shared CSS (R-F10).

## 5. Design system (as implemented)
**Authoritative source:** `:root` in `frontend/src/styles.css`, **byte-identical** to `app/static/css/styles.css` (verified by `diff`). Keep both in sync. `public_dashboard` re-declares a near-identical subset inline.

> ⚠ `DESIGN.md` ("Design System Inspired by Mintlify": brand `#18E299`, near-black `#0d0d0d`, Geist Mono, 5% borders) is **not what ships**. Treat it as an unused reference.

### Tokens
| Group | Values |
|---|---|
| Brand | `--brand #0aaf72`, `--brand-dim #089960`, `--brand-muted rgba(10,175,114,.09)`, `--brand-glow .16`, `--brand-border .22` |
| Surfaces | `--bg #f4f6f9`, `--bg-card #fff`, `--bg-raised #edf0f5`, `--bg-sunken #e8ecf2`, `--bg-input #f0f3f8` |
| Text | `--ink #0f1623`, `--text #3d4a5c`, `--text-muted #6b7a8d`, `--text-faint #9ba8b8` |
| Lines | `--line rgba(0,0,0,.08)`, `--line-med .12`, `--line-strong .18` |
| Accents | indigo `#6366f1`/`#4f46e5`, amber `#d97706`/`#b45309`, blue `#2563eb`/`#1d4ed8`, teal `#0d9488`/`#0f766e`, rose `#e11d48` |
| Shadows | `--shadow-xs … --shadow-md`, `--shadow-card`, `--shadow-glow` |
| Radius | `--r-sm 6`, `--r-md 10`, `--r-lg 14`, `--r-xl 18`, `--r-2xl 24`, `--r-pill 9999` |
| Spacing | `--sp-1 4 … --sp-24 96` (4/8/12/16/20/24/32/40/48/64/96) |
| Layout | `--nav-h 58px`, `--page-w 1280px` |
**Typography:** Inter (300–700) for UI; JetBrains Mono (400/500) for hours, numbers in tables, axis ticks, badges; loaded via Google Fonts `@import` (`styles.css` L5). Body line-height 1.5.
**Layout:** sticky translucent nav (`rgba(244,246,249,.88)` + `backdrop-filter: saturate(160%) blur(20px)`), content `max-width: var(--page-w)`, padding `var(--sp-8)`; KPI grid `repeat(4,1fr)`; cards `--r-xl`, white, hairline border + `--shadow-card`.

### Component classes (prefix `sl-`, ~90 distinct classes across `styles.css` + `index.css`)
`sl-nav(__inner|__brand|__logo|__sep|__links|__link|__pill|__right|__toggle)`, `sl-page`, `sl-hero*` (legacy overview only), `sl-features*`/`sl-feature-card*`, `sl-dash-header*`, `sl-controls*`, `sl-input`, `sl-select`, `sl-badge(--green|--gray|--indigo)`, `sl-alert(--error|--warning|--info)`, `sl-kpi-grid`, `sl-kpi(--indigo|--teal|--amber|--blue|--green|--rose)` + `__top|__label|__icon|__value|__unit|__sub`, `sl-chart-card*`, `sl-table-card*`, `sl-table`, `sl-row(--2|--3)`, `sl-spinner`, `sl-loading`, `sl-hidden`, `sl-divider`, `sl-footer*`. Others: `btn-primary|btn-ghost|btn-brand|btn-sm|btn-xs`, `chart-toggle(__btn)`, `td-mono|td-energy|td-value|td-bar|td-bar-wrap|td-bar__fill`, `animate-up`. `index.css` (imports `styles.css`) adds `sl-tab-bar`, `sl-tab-btn`, `sl-ctrl-picker`, `sl-ctrl-btn` (34×32) used only by the React app.

### Charts (Chart.js 4)
React colours: energy bars `rgba(10,175,114,.7)` / border `#0aaf72` radius 4; price line `#6366f1`, width 2.2, tension .35, points 3/6; grids `rgba(0,0,0,.05)`; x ticks JetBrains Mono 11 `#6b7a8d`; legend Inter 12/500 with point style; tooltip bg `#0f1623`, padding 12, radius 8; y-left (energy/revenue) and y1-right (price/MWh, grid hidden); interaction `mode:index`.

### States and motion
- **Loading:** React shows `.sl-spinner` (spin .65 s) in place of the chart; Refresh button text → "Refreshing…" with spinning icon. Legacy: `#loading`.
- **Error:** `.sl-alert--error` with "⚠️" + message; **ErrorBoundary** shows a centred card with "Reload Dashboard" (inline styles, brand pill button).
- **Empty:** React has **no empty state** — renders zeros. Legacy has `errorMessage` and a "no production" warning.
- **Hover/focus/active:** 12 `:hover`, 2 `:focus` rules, 5 `.active` rules; **no `:active`/`:disabled` rules**; 16 `transition` declarations.
- **Animation:** `fadeUp` (.4 s cubic-bezier(.22,1,.36,1)) via `.animate-up`, `pulse` (2.2 s) on the Live pill dot, `spin`.
- **Responsive:** breakpoints 1024 / 768 / 480 (`styles.css`) and 768 / 640 (`index.css`); legacy nav has a hamburger toggle (`sl-nav__toggle`).
- **Icons:** `lucide-react` (React); inline SVG (legacy).

## 6. Rules for new UI work
1. Reuse `sl-*` / `td-*` / `btn-*` classes and tokens; do not add colours/fonts/radii outside `:root`. If a token is needed, add it to **both** `styles.css` copies.
2. Match the existing page anatomy: header → controls → KPI grid → chart card → table card.
3. Date handling: avoid `toISOString()` on local-midnight dates (R-F1).
4. Any new number shown must state its definition (see the three "Avg. Price" meanings in [05 §7](05_SOLAR_DOMAIN_AND_CALCULATIONS.md)).
5. Add loading/error/empty states (the React app currently lacks empty and staleness states).
6. If you touch calculations in the UI, mirror them in `main.py` and `public_dashboard` or document the divergence.
7. Verify in a real browser at ≥1024, 768 and 480 widths — onboarding did not.
