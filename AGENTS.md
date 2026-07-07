# AGENTS.md — Working Guide for Agents & Contributors

This is the operating manual for anyone (human or AI) changing this codebase.
Read [`/CODE.md`](CODE.md) first (it's auto-loaded at session start), this file
second, and [`docs/TECHNICAL.md`](docs/TECHNICAL.md) when you need depth.

> **Golden rule:** when you change how the repo works — structure, commands,
> conventions, data contracts — update `CODE.md`, this file, and/or
> `docs/TECHNICAL.md` **in the same commit** so the docs never rot.

---

## 1. Orientation (30 seconds)

- Two systems, one repo: **`screener/`** (legacy, stable) and
  **`alphahunter-ai/` + `api/`** (the product). They share the
  `screener/universe_1b_revenue.csv` universe.
- The frontend is a **static SPA on Vercel**. Live data comes from **Vercel
  serverless functions** (`/api/*.js`) and **committed JSON snapshots**
  (`snapshot.json`, `dashboard.json`) refreshed by CI crons. There is usually
  **no always-on backend**.
- The Python FastAPI backend runs the heavy scan in **GitHub Actions** and
  writes those snapshots.

## 2. Git & workflow conventions

- **All work goes to `main`.** Commit with a clear message; push
  `git push -u origin main`.
- If push is rejected: `git pull --rebase origin main` then push again (CI bots
  commit generated files and will race you).
- **Do NOT open a PR** unless explicitly asked.
- Commit trailer: `Co-Authored-By: Claude <noreply@anthropic.com>`.
- **Never commit secrets.** All config via `.env` / Vercel env vars.
- Every push to `main` auto-deploys the frontend on Vercel.

## 3. The definition of done (run these before every commit)

```bash
# backend touched?
cd alphahunter-ai && python -m pytest -q            # must stay green, offline

# serverless function touched?
node --check api/*.js                               # plain JS, no build

# frontend touched?
cd alphahunter-ai/frontend && npm run build         # tsc -b + vite build
```

Then update the relevant doc(s), commit atomically, rebase-and-push.

## 4. How to add a new signal (the common task)

Signals must be **explainable** (carry their inputs + a plain-English reason)
and **offline-testable** (operate on `StockSnapshot`/dicts, never the network).

1. **Config first.** Add any threshold to `backend/config.py` **and**
   `.env.example`. Never hardcode a magic number.
2. **Compute it.** Add a function in the right place:
   - a scoring nudge → `scoring/engines.py` or a new `scoring/<name>.py`
   - a flag/context → follow `scoring/risk.py` / `scoring/csp_signal.py`
   - a chart/technical → `indicators/technical.py` (backend) AND/OR `api/ta.js` (live)
3. **Wire it into `scoring/composite.py`** `score_snapshot()` — add it to the
   returned recommendation dict and, if it moves the number, before the weighted
   blend. Append a sentence to `reasoning` when relevant.
4. **Surface it:**
   - `run_daily.py` → add to `CSV_COLUMNS` + `_flatten()`.
   - `frontend/src/lib/types.ts` → extend `Recommendation`.
   - `frontend/src/components/RecGrid.tsx` → grid column + mobile-card line.
   - Seed it into `frontend/public/snapshot.json` so it shows before the next cron.
5. **Test it** in `tests/test_scanner_and_scoring.py` (shape + a firing/not-firing case).
6. **Doc it** in `docs/TECHNICAL.md` §5 and check the item off in
   `alphahunter-ai/IMPROVEMENTS.md`.

**Parity note:** several signals exist in BOTH Python (`backend/scoring/*`, for
the scan) and JS (`api/ta.js`/`quote.js`, for live single-ticker). If you change
the logic in one, change the other to match.

## 5. How to add a serverless endpoint

- Add `api/<name>.js` (Node, `export default handler`, uses global `fetch`).
- Data source: Yahoo **v8 chart** endpoint `/v8/finance/chart/{sym}` with a
  browser `User-Agent` (no auth). Avoid `quoteSummary`/`v7 quote` (need a crumb).
- If it must be reachable as a real path, confirm the `vercel.json` rewrite
  negative-lookahead already excludes `api/` (it does).
- `node --check api/<name>.js`.

## 6. How to add a frontend page

- `src/pages/<Name>.tsx`; register the route + nav tab in `src/App.tsx`.
- Fetch through `src/lib/api.ts`. Keep mobile in mind (cards on phones, grids on
  desktop; headers wrap; root is `overflow-x-hidden`).
- Plotly's TS types are strict — cast complex `data`/`layout` to `as any` when needed.

## 7. The auto-improvement loop

An autonomous loop (via `ScheduleWakeup`) works through
`alphahunter-ai/IMPROVEMENTS.md` top-to-bottom, one tested/atomic change per
wake-up. If you're that loop: pull `main`, check the CI workflows (fix failures
first), implement the next unchecked item end-to-end, run the §3 checks, check
it off, commit, push, reschedule. The user can say "stop the loop" to halt it.

## 8. Non-negotiable gotchas (see TECHNICAL.md §11 for the full list)

- **Sandbox blocks finance hosts + Vercel API** — live data only works in CI /
  on Vercel. Never conclude code is broken from a sandbox 403; test logic offline.
- **`financialCurrency == "USD"` filter is load-bearing** (yfinance revenue is
  in the reporting currency). Don't remove it.
- **403 without a browser User-Agent** on Yahoo/Wikipedia/NASDAQ.
- **Day % = last two closes**, not `meta.chartPreviousClose`.
- **Score weights must sum to 1.0** (a test enforces it).
- **Tests never hit the network.**

## 9. Where things live (quick index)

| I want to change… | File |
|---|---|
| A threshold/weight | `backend/config.py` + `.env.example` |
| The screener criteria | `backend/scanners/alphahunter.py` |
| The composite score / a recommendation field | `backend/scoring/composite.py` |
| A sub-score | `backend/scoring/engines.py` |
| Risk flags / CSP / relative strength | `backend/scoring/{risk,csp_signal,relative_strength}.py` |
| Live single-ticker TA / thesis / bottom / cycle | `api/ta.js` |
| Live portfolio prices/recs | `api/quote.js` |
| Dashboard watchlist | `backend/watchlist.py` + `backend/run_dashboard.py` |
| Scan output columns | `backend/run_daily.py` |
| A frontend page/tab | `frontend/src/pages/*` + `frontend/src/App.tsx` |
| A CI schedule | `.github/workflows/*.yml` |
