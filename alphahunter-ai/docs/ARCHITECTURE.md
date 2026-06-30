# AlphaHunter AI — Architecture

## Data flow

```
universe.py ──► MarketData (yfinance + TTL cache) ──► StockSnapshot
                                                          │
                                  ┌───────────────────────┤
                                  ▼                        ▼
                       AlphaHunterScanner          indicators/technical.py
                       (criteria pass/fail)        (RSI, EMA, MACD, ATR, …)
                                  │                        │
                                  └──────────┬─────────────┘
                                             ▼
                                    scoring/engines.py
                       technical · fundamental · options · momentum · sentiment
                                             ▼
                                   scoring/composite.py
                          weighted 0–100 score + trade plan + explanation
                                             ▼
                                   StockRecommendation (dict)
                                             ▼
                      api/routes.py · reports/morning.py · cli.py
```

## Module map

| Path | Responsibility |
|---|---|
| `config.py` | Env-driven settings singleton (`settings`) |
| `utils/market_data.py` | Cached yfinance wrapper → `StockSnapshot` |
| `utils/universe.py` | NASDAQ/NYSE listing + `>$1B` cache loader |
| `utils/cache.py` | In-process TTL cache |
| `indicators/technical.py` | Pure-pandas indicator library |
| `scanners/alphahunter.py` | Extended "Existing Screener" with pass/fail criteria |
| `scanners/runner.py` | Universe sweep → scored, ranked results |
| `scoring/engines.py` | Five transparent sub-score engines |
| `scoring/composite.py` | Weighted blend + recommendation assembly |
| `options/analyzer.py` | Covered-call / CSP yields from option chains |
| `portfolio/analyzer.py` | Per-position scoring + recommendations |
| `backtesting/engine.py` | Signal-quality backtest + metrics |
| `reports/morning.py` | 7 AM report buckets + market regime |
| `alerts/engine.py` | Slack / Discord / log dispatch |
| `scheduler/jobs.py` | APScheduler cron jobs |
| `ai/explainer.py` | Rule-based (or OpenAI) explanations + NL router |
| `api/routes.py` | FastAPI REST endpoints |
| `database/` | Optional SQLAlchemy persistence |

## Composite score

```
score = 0.35·technical + 0.25·fundamental + 0.20·options
      + 0.10·momentum  + 0.10·sentiment
```

Each sub-engine starts at a neutral 50 and adds/subtracts bounded points for
named factors, clamped to [0, 100]. Weights are env-configurable and validated
to sum to 1.0 (`test_weights_sum_to_one`).

### Action thresholds

| Score | Action |
|---|---|
| ≥ 75 | Buy |
| 60–74 | Accumulate |
| 45–59 | Hold |
| 30–44 | Reduce |
| < 30 | Sell |

## Design principles

- **Explainable:** every number carries its inputs and reasons.
- **Offline-testable:** engines take plain dataclasses; the test suite never
  touches the network.
- **Graceful degradation:** no DB, no Redis, no options chain, no OpenAI key →
  the platform still produces ranked, explained results.
- **Single source of truth:** shares the legacy screener's universe + data.

## Roadmap (next phases)

1. React + AG Grid + Plotly frontend (`frontend/`).
2. ML ranker (XGBoost/LightGBM) blended with the rule-based score.
3. Real sentiment (news + SEC filings) replacing the analyst-posture proxy.
4. Persisted scan history + score-distribution dashboards.
5. A GitHub Actions workflow running `python -m backend.cli scan` daily.
