# AlphaHunter AI — Technical Documentation

Complete technical reference for the repository. Written for humans and coding
agents. For the fast "read-before-acting" memory file see [`/CODE.md`](../CODE.md);
for agent working rules see [`/AGENTS.md`](../AGENTS.md); for how contributions
are queued see [`alphahunter-ai/IMPROVEMENTS.md`](../alphahunter-ai/IMPROVEMENTS.md).

Last updated: 2026-07-07.

---

## 1. What this product is

Two cooperating systems in one repo, sharing one data source (Yahoo Finance via
`yfinance`) and one universe (US common stocks > $1B revenue):

| System | Path | Role |
|---|---|---|
| **Legacy screener** | `screener/` | The original oversold-with-upside daily screener + the sharded universe builder. Runs in CI, commits dated CSVs to `results/`. Stable — treat as read-mostly. |
| **AlphaHunter AI** | `alphahunter-ai/` + `api/` | The productized platform: FastAPI backend, scoring engines, REST API, React frontend (deployed on Vercel), Vercel serverless functions, and CI cron jobs. |

The AlphaHunter frontend is a **static SPA on Vercel**. It has three data
sources at runtime, in priority order:
1. A full FastAPI backend (only if `VITE_API_TARGET` is set — usually not).
2. **Vercel serverless functions** in `/api` (live per-ticker data from Yahoo).
3. **Committed JSON snapshots** (`snapshot.json`, `dashboard.json`) refreshed by
   CI crons — the default source, so the site works with zero always-on backend.

---

## 2. Repository layout

```
/
├── CODE.md                      # session-start memory (auto-loaded by a hook)
├── AGENTS.md                    # agent working guide / conventions
├── vercel.json                  # Vercel build + SPA rewrites (excludes /api)
├── docs/TECHNICAL.md            # this file
│
├── api/                         # Vercel serverless functions (Node, plain JS)
│   ├── ta.js                    #   GET /api/ta?ticker=&range=  — full TA + thesis
│   ├── thesis.js                #   GET /api/thesis?ticker=     — compact thesis
│   ├── quote.js                 #   POST /api/quote {tickers}   — live prices + rec
│   └── run-scan.js              #   POST /api/run-scan          — dispatch the scan workflow
│
├── screener/                    # LEGACY system
│   ├── oversold_growth_screener.py  # profiles + screen_ticker() + load_universe()
│   ├── run_ci.py                    # CI entrypoint -> results/screen_<date>.csv
│   ├── build_universe.py            # sharded scan/merge universe builder
│   └── universe_1b_revenue.csv      # the >$1B universe cache (SHARED with AlphaHunter)
│
├── alphahunter-ai/
│   ├── backend/                 # FastAPI + scoring (Python 3.12)
│   ├── frontend/                # React + TS + Vite + Tailwind + AG Grid + Plotly
│   ├── tests/                   # pytest, fully offline (synthetic fixtures)
│   ├── docs/ARCHITECTURE.md     # module map + score math (backend-focused)
│   ├── IMPROVEMENTS.md          # roadmap / changelog for the auto-improvement loop
│   ├── requirements.txt
│   ├── docker-compose.yml, docker/Dockerfile
│   └── .env.example             # every tunable, no secrets
│
└── .github/workflows/
    ├── daily-screener.yml       # legacy: 6 AM PT -> results/
    ├── build-universe.yml       # legacy: sharded universe refresh
    ├── alphahunter-scan.yml     # ~6 AM PT -> snapshot.json + results/
    └── dashboard.yml            # 9 AM ET  -> dashboard.json
```

---

## 3. Backend architecture (`alphahunter-ai/backend/`)

### 3.1 Data flow (the scan)

```
universe.py ─► MarketData (yfinance + TTLCache) ─► StockSnapshot
                                                       │
                    ┌──────────────────────────────────┤
                    ▼                                   ▼
          AlphaHunterScanner                  indicators/technical.py
        (criteria pass/fail per ticker)       (RSI, EMA, MACD, ATR, 52w, …)
                    │  ScanHit                          │ indicator bundle
                    └───────────────┬───────────────────┘
                                    ▼
                         scoring/composite.score_snapshot()
        engines (5) + relative_strength + risk + csp_signal + backtest + sizing
                                    ▼
                        StockRecommendation (dict)  ── §4 data contract
                                    ▼
           run_daily.py ──► results/*.csv + snapshot.json     (scan)
           run_dashboard.py ──► dashboard.json                (watchlist)
           api/routes.py ──► REST JSON                        (if backend hosted)
```

### 3.2 Module map

| Module | Responsibility |
|---|---|
| `config.py` | Env-driven `settings` singleton (pydantic-settings). All thresholds/weights live here. `settings.score_weights` sums to 1.0 (enforced by test). |
| `utils/market_data.py` | `MarketData` — cached yfinance wrapper. `snapshot(t)` → `StockSnapshot(ticker, history, info)`; `history(t, period)` for backtests; `options_chain(t)`. `StockSnapshot` exposes None-safe props (`last_close`, `revenue`, `financial_currency`, `free_cash_flow`, `institutional_ownership`, …). **Engines take `StockSnapshot`, never the network — that's what keeps them unit-testable.** |
| `utils/universe.py` | Loads the scan list: the `screener/universe_1b_revenue.csv` cache first, else NASDAQ Trader listing (needs browser User-Agent). |
| `utils/cache.py` | `TTLCache` — in-process, thread-safe, `cache_ttl_seconds` default 900s. No Redis dependency. |
| `indicators/technical.py` | Pure-pandas indicators: `rsi`, `ema`, `sma`, `macd`, `atr`, `avg_volume`, `volume_ratio`, `pct_return`, `above_ema`, `distance_from_52w_high/low`, `golden_cross`. `indicator_bundle(hist)` computes them all at once → the `ind` dict every scorer reads. |
| `scanners/base.py` | `Criterion(name, passed, detail)`, `ScanHit(ticker, metrics, criteria)`, `Scanner` protocol. |
| `scanners/alphahunter.py` | The extended "Existing Screener" (§3.3). Records every criterion pass/fail for explainability. `require_all=True` = strict AND-screen; `False` = surface near-misses (core crash filter only). |
| `scanners/runner.py` | `run_scan()` — sweeps the universe, scores hits, returns ranked recommendations. |
| `scoring/engines.py` | The five sub-score engines + `quality_grade()` (A–F). Each returns a `SubScore(name, score 0-100, factors[])`. |
| `scoring/composite.py` | `score_snapshot()` — blends the 5 sub-scores, folds in relative strength, backtest calibration, risk flags, CSP signal, position sizing, thesis. Also `score_ticker_general()` (dashboard, no oversold gate). **This is the heart of the product.** |
| `scoring/relative_strength.py` | 3-month return vs SPY and the SPDR sector ETF; nudges the momentum sub-score. |
| `scoring/risk.py` | `compute_risk_flags()` — earnings proximity, short interest, 52w-low test, above-target, leverage, FCF, small-cap/beta, plus supportive flags. |
| `scoring/csp_signal.py` | Cash-secured-put-on-dip signal (§5). |
| `backtesting/engine.py` | `backtest_oversold(hist)` — replays the oversold setup, returns win rate, avg/median return, Sharpe, Sortino, profit factor, max drawdown. Used both standalone and to calibrate confidence. |
| `options/analyzer.py` | Covered-call / CSP annualized yields from a yfinance option chain. |
| `portfolio/analyzer.py` | Per-position scoring + recommendation from imported holdings. |
| `reports/morning.py` | Report buckets + coarse SPY market-regime read. |
| `alerts/engine.py` | Slack/Discord/log dispatch (webhooks optional; degrades to logging). |
| `scheduler/jobs.py` | APScheduler cron (only started when `alphahunter_env=production`). |
| `ai/explainer.py` | Rule-based explanation; optional OpenAI polish + NL query router. |
| `api/routes.py`, `api/schemas.py`, `main.py` | FastAPI app + 15 REST endpoints (§6). |
| `database/` | Optional SQLAlchemy persistence; app runs fully in-memory without `DATABASE_URL`. |
| `watchlist.py` | The curated 20-ticker multi-domain dashboard list (`DOMAINS`). |
| `run_daily.py` | Scan CI entrypoint → `results/alphahunter_<date>.{json,csv}` + `frontend/public/snapshot.json`. |
| `run_dashboard.py` | Dashboard CI entrypoint → `frontend/public/dashboard.json`. |
| `cli.py` | `python -m backend.cli scan|report|backtest`. |

### 3.3 The AlphaHunter screener (criteria)

Core crash filter (must all hold):
- **revenue_over_1b** — `financialCurrency == "USD"` AND `totalRevenue ≥ REVENUE_FLOOR`
- **down_5pct_day** — 1-day return ≤ `DAY_DROP_PCT` (-5%)
- **down_20pct_month** — ~20-day return ≤ `MONTH_DROP_PCT` (-20%)

Confirmation signals (all required when `require_all=True`):
- **rsi_below_35**, **volume_spike** (≥1.5× avg), **above_ema200**,
  **positive_fcf**, **institutional_over_50**, **no_bankruptcy_risk**
  (current ratio ≥1, D/E not extreme, EBITDA ≥ 0).

### 3.4 The composite AI score

```
score = 0.35·technical + 0.25·fundamental + 0.20·options + 0.10·momentum + 0.10·sentiment
```

Each engine starts at a neutral **50** and adds/subtracts bounded points for
named factors, clamped to [0, 100]. Weights are env-configurable and **must sum
to 1.0** (`test_weights_sum_to_one`). Action bands:

| Score | Action |
|---|---|
| ≥ 75 | Buy |
| 60–74 | Accumulate |
| 45–59 | Hold |
| 30–44 | Reduce |
| < 30 | Sell |

`quality_grade`: A ≥80 · B ≥68 · C ≥55 · D ≥42 · F <42 (from the fundamental sub-score).
`expected_gain_%` = analyst upside × confidence multiplier × quality multiplier
(a realistic estimate, not the raw target — this is what the Top Gainers board ranks by).

---

## 4. Data contracts

### 4.1 `StockRecommendation` (scan output; one object per hit)

Produced by `score_snapshot()`; consumed by the frontend (`lib/types.ts`),
`run_daily` CSV, and the REST API. Key fields:

```jsonc
{
  "ticker", "company", "score", "action", "confidence",   // core verdict
  "quality_grade", "analyst_upside_%", "expected_gain_%",  // quality + gain
  "hist_win_rate", "hist_avg_return_%", "hist_trades",     // backtest calibration
  "rel_strength": {"vs_spy", "vs_sector", "sector", "sector_etf"},
  "risk_flags": [{"level": "warn|info|good", "text"}],
  "csp_signal": {"active", "strength", "suggested_strike", "idea", "reason"},
  "position": {"shares", "value", "risk_$", "basis"},      // ATR-based sizing
  "rr_pass",                                                // R:R vs floor
  "subscores": {"technical","fundamental","options","momentum","sentiment"},
  "weights", "entry", "stop_loss", "target1", "target2", "risk_reward",
  "covered_call", "cash_secured_put",
  "criteria_passed": [...], "criteria_failed": [...],
  "metrics": { price, "day_%", "week_%", "month_%", rsi, "revenue_$B",
               above_ema200, institutional_%, ... },
  "reasoning": "plain-English explanation incl. backtest + sector thesis"
}
```

### 4.2 `snapshot.json` (deployed scan data)

`{ date, snapshot: true, live: bool, count, results: [StockRecommendation] }`.
Written by `run_daily.py`; the frontend falls back to it when `/api` is
unreachable (`lib/api.ts` `scanWithFallback`). A committed **seed** version
keeps the site populated before the first live cron.

### 4.3 `dashboard.json` (deployed watchlist data)

`{ generated_at, as_of, count, domains: { <domain>: [DashboardStock] } }` where
`DashboardStock = { ticker, company, domain, price, "day_%", score, action,
quality_grade, rsi, above_ema200, cycle, "analyst_upside_%", spark: [30 closes] }`.
Written by `run_dashboard.py`.

### 4.4 Serverless `/api/ta` response (single-ticker TA)

`{ ticker, name, price, day_change_pct, score, recommendation, verdict_reason,
thesis, cycle, levels, signals, csp_signal, dip_bounce, bottom, factors,
indicators{...}, chart{ dates, open, high, low, close, volume, ema20/50/200,
bb_upper/mid/lower, rsi, macd/macd_signal/macd_hist } }`.

---

## 5. Signals reference (what each one means)

| Signal | Where | Meaning |
|---|---|---|
| **Composite score / action** | scan + dashboard | Weighted 5-engine 0-100 → Buy/Accumulate/Hold/Reduce/Sell. |
| **quality_grade** | scan + dashboard | A–F from the fundamental sub-score. |
| **expected_gain_%** | scan, Top Gainers | Realistic upside = analyst upside × confidence × quality. |
| **Backtest calibration** | scan | The ticker's own oversold setup replayed → win rate/avg return; nudges `confidence` ±1 level. |
| **rel_strength** | scan + reasoning | 3-mo return vs SPY & sector ETF → group-driven vs stock-specific. |
| **risk_flags** | scan | Earnings ≤N days, short interest, 52w-low, above-target, leverage, −FCF, small-cap/beta, golden-cross, strong-buy. |
| **csp_signal** | scan + `/api/ta` | CSP-on-dip: down today + chart upside + dips historically bounced ⇒ sell puts into weakness. `strong`/`moderate`, suggested strike. |
| **position + rr_pass** | scan | ATR-stop sizing to risk `MAX_RISK_PCT` of `ACCOUNT_SIZE`; flags R:R below `MIN_RISK_REWARD`. |
| **bottom** (`/api/ta`) | Analysis | 6-tell checklist (oversold RSI, RSI divergence, 52w-low/support, capitulation candle, EMA reclaim) → low/possible/high with ✓/✗ reasons. |
| **cycle** (`/api/ta`) | Analysis | Bull/bear market cycle from 50/200 regime segmentation. |
| **signals** (`/api/ta`) | Analysis | Recent golden/death cross, MACD cross, RSI 30/70, Bollinger breakout events. |
| **thesis** (`/api/ta`, `/api/thesis`) | Analysis, Dashboard | Plain-English story: market-driven vs stock-specific, trend/cycle, dip history, stock character. |

---

## 6. REST API (FastAPI, only when backend hosted)

`GET /market/top` · `/market/oversold` · `/market/breakouts` ·
`GET /scanner/results?strict=` · `POST /scanner/run` ·
`GET /options/coveredcalls` · `/options/csp` ·
`GET /portfolio` · `POST /portfolio/import` · `GET /portfolio/recommendations` ·
`GET /backtest/{ticker}` · `GET /report/morning` · `POST /ai/ask` ·
plus `/` and `/health`. Interactive docs at `/docs`.

## 7. Serverless functions (`/api/*.js`, always live on Vercel)

Plain Node JS, no build. Run `node --check api/*.js` before committing.
- **`ta.js`** — deep single-ticker TA (charts, indicators, cycle, S/R, signals, CSP, bottom, thesis). Powers the Analysis tab.
- **`thesis.js`** — compact per-ticker thesis (`/api/thesis?ticker=X`), 5-min edge cache. Powers Dashboard tap-to-thesis.
- **`quote.js`** — `POST` batch live prices + on-the-go technical Buy/Hold/Sell + reason. Powers Portfolio for ANY ticker.
- **`run-scan.js`** — dispatches `alphahunter-scan.yml` via GitHub API. Needs Vercel env `GITHUB_DISPATCH_TOKEN` (fine-grained PAT, Actions r/w); without it the UI links to the Actions page.

The SPA rewrite in `vercel.json` excludes `api/`, `assets/`, and `snapshot.json`.

---

## 8. Frontend (`alphahunter-ai/frontend/`)

React 18 + TypeScript + Vite + TailwindCSS + AG Grid + Plotly. Pages (`src/pages/`):
`Dashboard` (collapsible domain sections + Top Gainers + tap-to-thesis),
`Gainers` (expected-gain leaderboard), `Opportunities` (AG Grid desktop / card
list mobile), `Analysis` (single-ticker charting workstation), `Options`,
`Portfolio` (localStorage save, live quotes), `Backtest`. All data flows through
`src/lib/api.ts` (backend → serverless → snapshot fallback, `isSnapshot()`
tracks which). Types in `src/lib/types.ts` mirror §4.1. `npm run build`
type-checks (`tsc -b`) then bundles — always run before committing FE changes.
Plotly's strict TS types often need `as any` on complex `data`/`layout` props.

---

## 9. CI / CD

| Workflow | Schedule (gated) | Writes | Commits |
|---|---|---|---|
| `daily-screener.yml` | 6 AM PT | `results/screen_<date>.csv` | yes |
| `build-universe.yml` | daily, sharded | `universe_1b_revenue.csv` | yes |
| `alphahunter-scan.yml` | ~6 AM PT | `results/alphahunter_<date>.*` + `snapshot.json` | yes (conflict-proof push) |
| `dashboard.yml` | 9 AM ET | `dashboard.json` | yes (conflict-proof push) |

Both AlphaHunter workflows use a **conflict-proof push** (`git rebase -X theirs`
retry loop) because they commit generated files that can race concurrent pushes.
Every push to `main` auto-deploys the frontend on Vercel.

**Deployment (Vercel):** project `amit33-network-design`, team `netdesign-team`,
Git-linked to `main`. Root `vercel.json` sets framework=Other, root dir `./`,
builds `alphahunter-ai/frontend`, output `dist`. Live at
https://amit33-network-design.vercel.app.

---

## 10. Environment / config

All tunables are in `alphahunter-ai/.env.example` and `config.py`. Categories:
screener thresholds, risk/catalyst, CSP-on-dip, position sizing, score weights,
caching, optional DB/Redis, optional OpenAI, optional alert webhooks. **No
secrets in code.** Vercel-side: `GITHUB_DISPATCH_TOKEN` (run-scan button),
optionally `VITE_API_TARGET` (point the SPA at a live backend).

---

## 11. Known constraints & gotchas

- **Sandbox egress:** the dev/agent sandbox blocks outbound HTTP to finance
  hosts (Yahoo, NASDAQ Trader, Wikipedia) and `api.vercel.com`. Live data only
  works in **GitHub Actions CI** and on Vercel. Test logic offline.
- **yfinance `totalRevenue` is in the reporting currency**, not USD — the
  `financialCurrency == "USD"` filter is load-bearing; don't remove it.
- **Yahoo/Wikipedia/NASDAQ return 403** without a browser `User-Agent`.
- **Yahoo v8 chart endpoint** (`/v8/finance/chart/{sym}`) is the open,
  no-auth data source the serverless functions use; `quoteSummary`/`v7 quote`
  now need a crumb — avoid them.
- **Day change != range change:** compute day % from the last two closes, not
  `meta.chartPreviousClose` (that's the close before the range start).
- **Tests must stay offline** — synthetic fixtures in `tests/conftest.py`.
