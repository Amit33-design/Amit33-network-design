# AlphaHunter AI

AI-powered stock discovery & portfolio intelligence. It analyzes the US market
(NYSE / NASDAQ / AMEX), ranks opportunities with an explainable 0–100 score,
recommends options strategies, and explains every recommendation.

> This is a **research tool, not financial advice.** It surfaces candidates for
> you to investigate; it does not place trades.

This `alphahunter-ai/` backend is the productized evolution of the repo's
existing daily screener (`../screener/`). It reuses the same yfinance data and
the proven NASDAQ-Trader universe, and keeps the legacy screener untouched.

## What's implemented

| Spec area | Module | Status |
|---|---|---|
| Existing Screener (extended) | `backend/scanners/alphahunter.py` | ✅ working |
| Technical engine | `backend/indicators/technical.py` | ✅ working |
| Composite AI score (35/25/20/10/10) | `backend/scoring/` | ✅ working |
| Options engine (CC / CSP yields) | `backend/options/analyzer.py` | ✅ working |
| Portfolio analyzer | `backend/portfolio/analyzer.py` | ✅ working |
| Backtesting | `backend/backtesting/engine.py` | ✅ working |
| Morning report | `backend/reports/morning.py` | ✅ working |
| Alerts (Slack/Discord/log) | `backend/alerts/engine.py` | ✅ working |
| Scheduler (APScheduler) | `backend/scheduler/jobs.py` | ✅ working |
| REST API (FastAPI) | `backend/api/routes.py` | ✅ working |
| AI explanation / NL queries | `backend/ai/explainer.py` | ✅ rule-based; OpenAI optional |
| Database (Postgres) | `backend/database/` | ✅ optional, degrades gracefully |
| Frontend (React/AG Grid) | `frontend/` | ⬜ next phase |

## The screener strategy

Keeps the original **Revenue > $1B AND down ≥5% today AND down ≥20% over the
month**, extended per spec with:

- RSI < 35
- Volume > 150% of average
- Price above EMA200
- Positive free cash flow
- Institutional ownership > 50%
- No-bankruptcy-risk check (current ratio, leverage, EBITDA)

Then every hit is scored and ranked. Thresholds live in `.env` / `config.py`.

## Quickstart

```bash
cd alphahunter-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Run the API
uvicorn backend.main:app --reload --port 8000
# open http://localhost:8000/docs

# Or scan from the CLI (fast smoke test against a few hundred names)
python -m backend.cli scan --limit 200 --loose
python -m backend.cli backtest AAPL --hold 10
```

With Docker:

```bash
docker compose up --build
```

## Key REST endpoints

```
GET  /market/top                 ranked picks
GET  /market/oversold            RSI<35 subset
GET  /market/breakouts           above-EMA200 subset
GET  /scanner/results?strict=    full / near-miss scan
POST /scanner/run                custom ticker list + params
POST /portfolio/import           analyze your holdings
GET  /options/coveredcalls       covered-call ideas
GET  /options/csp                cash-secured-put ideas
GET  /backtest/{ticker}          single-name oversold backtest
GET  /report/morning             full morning report
POST /ai/ask                     natural-language query
```

## Tests

```bash
pytest -q          # runs fully offline (synthetic fixtures, no network)
```

## Configuration & transparency

- Every threshold and score weight is env-configurable (`.env`).
- No secrets are hardcoded.
- Every recommendation carries its sub-scores, the criteria it passed/failed,
  and a plain-English explanation of what drove the number.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the module map and the
scoring math.
