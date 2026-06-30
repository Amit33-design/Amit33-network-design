# AlphaHunter AI — Frontend

React + TypeScript + Tailwind + AG Grid + Plotly. Talks to the FastAPI backend
through a `/api` proxy (see `vite.config.ts`).

## Run

```bash
# 1) start the backend (separate terminal, from alphahunter-ai/)
uvicorn backend.main:app --reload --port 8000

# 2) start the frontend
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Point at a non-local backend with `VITE_API_TARGET`:

```bash
VITE_API_TARGET=https://my-backend.example.com npm run dev
```

## Views

| Route | Backend endpoint(s) | What it shows |
|---|---|---|
| `/dashboard` | `/market/top`, `/report/morning` | Summary cards, score-distribution chart, market regime, top 10 |
| `/opportunities` | `/market/{top,oversold,breakouts}` | AG Grid of ranked picks with full metrics + reasoning |
| `/options` | `/options/{coveredcalls,csp}` | Covered-call & cash-secured-put income ideas |
| `/portfolio` | `/portfolio/import` | Paste holdings → per-position scores + recommendations |
| `/backtest` | `/backtest/{ticker}` | Oversold-setup backtest metrics |

## Build

```bash
npm run build        # type-checks (tsc -b) then bundles to dist/
npm run preview      # serve the production build
```
