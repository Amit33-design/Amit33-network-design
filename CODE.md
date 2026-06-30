# CODE.md — Read This First

> **Every session must read this file before doing anything else.** A
> `SessionStart` hook (`.claude/settings.json`) loads it automatically. If you
> change how the repo works, **update this file in the same commit** so it
> never goes stale.

Last updated: 2026-06-30

---

## What this repo is

Two cooperating stock-screening systems that share one data source (yfinance)
and one universe (NASDAQ/NYSE/AMEX common stocks with >$1B revenue):

| System | Path | Role |
|---|---|---|
| **Legacy daily screener** | `screener/` | The original oversold-with-upside screener + universe builder. Runs daily in CI, commits dated CSVs to `results/`. **Stable — don't break it.** |
| **AlphaHunter AI** | `alphahunter-ai/` | The productized platform: FastAPI backend, scoring engines, options/portfolio/backtest, REST API, React frontend. Built on the same data + strategy. |

Both are live on `main`. The legacy screener's outputs feed AlphaHunter's
universe (`screener/universe_1b_revenue.csv`).

---

## Git & workflow conventions (IMPORTANT)

- **All work goes to `main`** in this session's established flow. Commit with
  clear messages; push with `git push -u origin main`.
- If a push is rejected, `git pull --rebase origin main` then push again — the
  screener bot commits results automatically and will race you.
- Do **not** open a PR unless explicitly asked.
- Co-author trailer on commits:
  `Co-Authored-By: Claude <noreply@anthropic.com>`
- Never commit secrets. All config is via `.env` (see `.env.example` files).

---

## Legacy screener (`screener/`)

**Strategy — three profiles, a ticker matches if it passes ANY:**

| Profile | Day | Week | Month | Revenue | Rating | Upside |
|---|---|---|---|---|---|---|
| `LARGE_CAP_DIP` | ≤ -5% | ≤ -12% | — | >$1B | Buy | ≥5% |
| `SMALL_CAP_CRASH` | ≤ -5% | ≤ -20% | — | none | Buy | ≥5% |
| `MONTHLY_CRASH_BOUNCE` | — | — | -30% to -50% | >$1B | Buy | ≥50% |

**Key files**
- `screener/oversold_growth_screener.py` — profiles + `screen_ticker()` + `load_universe()`
- `screener/run_ci.py` — CI entrypoint, writes `results/screen_<date>.csv`
- `screener/build_universe.py` — sharded universe builder (scan/merge modes)
- `screener/universe_1b_revenue.csv` — the >$1B universe cache (shared)

**Gotchas**
- yfinance `totalRevenue` is in the company's **reporting currency** — the
  universe builder filters `financialCurrency == "USD"` to keep the $1B floor
  meaningful. Don't remove that check.
- Wikipedia and NASDAQ Trader return 403 without a browser `User-Agent`.
- The sandbox blocks outbound HTTP to finance hosts; live data only works in
  **GitHub Actions CI**, not in the local agent sandbox. Test logic offline.

**Workflows**
- `.github/workflows/daily-screener.yml` — 6 AM Pacific, commits to `results/`
- `.github/workflows/build-universe.yml` — daily sharded universe refresh

---

## AlphaHunter AI (`alphahunter-ai/`)

FastAPI backend + React frontend. **The legacy screener is untouched by it.**

**Extended screener** (`backend/scanners/alphahunter.py`): keeps Rev>$1B +
down ≥5% day + down ≥20% month, adds RSI<35, volume>150% avg, above EMA200,
positive FCF, institutional ownership>50%, no-bankruptcy-risk check. Every
criterion records pass/fail + detail (explainable).

**Composite AI score** = 35% technical + 25% fundamental + 20% options +
10% momentum + 10% sentiment → 0-100. Weights in `.env`/`config.py`, must sum
to 1.0 (enforced by a test).

**Module map** — see `alphahunter-ai/docs/ARCHITECTURE.md`. Quick version:
`config.py`, `utils/` (market_data, universe, cache), `indicators/technical.py`,
`scanners/`, `scoring/`, `options/`, `portfolio/`, `backtesting/`, `reports/`,
`alerts/`, `scheduler/`, `ai/`, `api/`, `database/`.

**Run the backend**
```bash
cd alphahunter-ai
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000   # http://localhost:8000/docs
python -m backend.cli scan --limit 200 --loose  # CLI scan
pytest -q                                         # 13 tests, fully offline
```

**Run the frontend** (React + TS + Tailwind + AG Grid + Plotly — built & type-checks)
```bash
cd alphahunter-ai/frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api → :8000)
npm run build        # tsc -b + vite build (verify before committing FE changes)
```
Views: Dashboard, Opportunities (AG Grid), Options, Portfolio, Backtest —
each wired to the REST API via `src/lib/api.ts`. See `frontend/README.md`.

**REST API** (15 endpoints): `/market/top`, `/market/oversold`,
`/market/breakouts`, `/scanner/results`, `/scanner/run`, `/portfolio/import`,
`/options/coveredcalls`, `/options/csp`, `/backtest/{ticker}`,
`/report/morning`, `/ai/ask`. Full list in `alphahunter-ai/README.md`.

**Daily scan workflow**: `.github/workflows/alphahunter-scan.yml` runs
`python -m backend.run_daily` (gated to ~6 AM Pacific, like the legacy one) and
commits dated `alphahunter-ai/results/alphahunter_<date>.{json,csv}`.
`workflow_dispatch` accepts `limit` and `loose` inputs for manual runs.

**Tests must stay offline** — they use synthetic fixtures in
`tests/conftest.py`. Never add a test that hits the network.

---

## Conventions for engines & scoring

- Every recommendation must carry its sub-scores, the criteria it passed/failed,
  and a plain-English explanation. Don't add an opaque signal.
- Engines take plain dataclasses (`StockSnapshot`) so they're testable without
  network. Keep it that way.
- New thresholds/weights → add to `config.py` + `.env.example`, don't hardcode.

---

## When you finish a task

1. Run `pytest -q` in `alphahunter-ai/` if you touched the backend.
2. Update this `CODE.md` if you changed structure, commands, or conventions.
3. Commit (rebase if pushed rejected) and push to `main`.
