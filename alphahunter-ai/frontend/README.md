# AlphaHunter AI — Frontend (planned)

The backend is API-first and fully usable via `/docs` (Swagger) today. The
React frontend is the next phase.

## Planned stack (per spec)

- React + TypeScript
- TailwindCSS
- AG Grid (sortable/filterable opportunity tables)
- Plotly (score distribution, sector heat map, equity curves)

## Planned views

- **Dashboard** — portfolio value, cash, today's gain, premium income,
  expected monthly income, risk score.
- **Opportunities** — ranked scan grid backed by `GET /market/top`.
- **Options** — covered-call & CSP idea tables (`/options/*`).
- **Portfolio** — import holdings, per-position scores & recommendations.
- **Backtest** — run `/backtest/{ticker}` and chart the equity curve.

## Wiring

Point the app at the backend base URL (default `http://localhost:8000`). All
data comes from the REST endpoints documented in the root `README.md`.
