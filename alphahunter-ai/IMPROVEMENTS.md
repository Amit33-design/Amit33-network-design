# AlphaHunter — Improvement Roadmap (auto-improvement loop)

The product goal: **surface high-quality stocks with the best risk-adjusted
upside.** This file is the backlog the auto-improvement loop works through. Each
iteration ships one focused, tested change, commits to `main` (auto-deploys),
and checks the item off here.

Conventions: keep `pytest` green and offline; surface every new signal with its
inputs (explainability); add thresholds to `config.py`/`.env`, never hardcode.

## Done
- [x] **Chart explainers + move thesis.** Every Analysis chart (price/candles,
  volume, MACD, RSI) has a tap-to-open "ℹ️ what is this?" explainer — how to
  read the graph plus a live "right now" line from the data. New 📝 Thesis card
  narrates the move: market-driven vs stock-specific (ticker vs S&P day/month
  spread — the "memory names all fall together" context), trend/cycle read,
  historical dip behavior, and the net verdict. Scanner reasoning gains a
  sector thesis sentence (group-driven vs stock-specific weakness vs leader).
- [x] **Potential-bottom detector + multi-domain Dashboard + 9 AM ET cron.**
  Analysis tab: `api/ta.js` `bottomSignal()` scores classic bottoming tells
  (oversold RSI, bullish RSI divergence, 52w-low/support test, capitulation
  volume + hammer candle, 20-EMA reclaim) → high/possible/low with factors,
  shown as a "Potential bottom" card. Dashboard rebuilt as a curated 20-stock
  board across domains (AI, Semis, FAANG, Energy, EV, Fintech, Software) via
  `backend/watchlist.py` + `score_ticker_general` + `backend/run_dashboard.py`
  writing `frontend/public/dashboard.json`, refreshed daily by the new
  `.github/workflows/dashboard.yml` cron (9 AM ET), grouped by domain with
  score/action/quality/RSI/day%.
- [x] **CSP-on-dip buy signal.** New `scoring/csp_signal.py` + `api/ta.js`
  equivalent: flags a cash-secured-put entry when the stock is down ≥2% today
  AND the chart shows upside (above EMA200 / bullish cycle / ≥10% analyst
  upside) AND historical dips of this kind bounced (setup backtest in the
  scanner; per-ticker down-day forward-return stats in the Analysis tab).
  Strength strong/moderate, suggested strike (support-aware or spot − 1.5·ATR),
  explainable reason either way. Surfaced as a grid column, a mobile-card
  badge, an Analysis-tab banner with dip-bounce history, and CSV columns.
  Config knobs: CSP_DIP_DAY_PCT / CSP_MIN_HIST_WIN / CSP_MIN_UPSIDE.
- [x] **Mobile-browser compatibility pass.** Opportunities renders a card list
  on phones (the wide AG Grid is desktop-only now); grid height is responsive
  (70vh). Fixed non-responsive grids (Portfolio summary, Backtest metrics),
  headers/toggles wrap, container padding shrinks on small screens, root has
  overflow-x-hidden to kill stray horizontal scroll, and the Analysis verdict
  header wraps cleanly. Viewport meta already mobile-correct.
- [x] **Mobile Run Scan fix + advanced Technical Analysis (paid-app style).**
  Run Scan renders a native anchor link (mobile popup-blockers reject
  window.open from async callbacks) and the header is responsive (Run Scan
  pinned visible, nav scrolls). `api/ta.js` now returns OHLC candles, Bollinger
  Bands, MACD series, bull/bear **market-cycle detection** (50/200 regime
  segmentation with current phase + days), swing-based **support/resistance**,
  and a **recent-signals** feed (golden/death cross, MACD cross, RSI 30/70,
  Bollinger breakouts). The Analysis tab renders candlesticks + BB + EMAs +
  S/R lines + green/red cycle shading + ▲▼ signal markers, plus volume, MACD,
  and RSI subplots, a cycle badge, and S/R + signals panels.
- [x] **Single-ticker real-time Technical Analysis tab.** New `/analysis` page +
  `api/ta.js` serverless function: price chart with EMA20/50/200 overlays, RSI
  subplot, full indicator panel (RSI, MACD, ATR, multi-horizon returns, 52w
  position), and a Buy/Hold/Sell verdict with explainable bull/bear factors.
  Fixed an invalid-object-key syntax bug in `api/quote.js` found en route.
- [x] **Iter 1 — Quality grade + expected-gain ranking.** Richer multi-factor
  fundamental/quality score (ROE, ROA, margins, PEG, growth, leverage,
  liquidity) → A–F `quality_grade`; `expected_gain_pct` (analyst upside
  tempered by confidence & quality); surfaced in API, CSV, and the grid.

- [x] **Iter 2 — Backtest-calibrated confidence.** Each hit now backtests its
  own oversold setup (via `MarketData.history` + `backtesting/engine.py`) →
  `hist_win_rate`, `hist_avg_return_%`, `hist_trades`; confidence is bumped up
  (win≥60% & +avg) or down (win<40% or −avg) when ≥3 historical trades exist,
  the stat is woven into the reasoning, and shown as a "Hist. Win%" grid column.

- [x] **Iter 3 — Catalyst & risk awareness.** New `scoring/risk.py` attaches a
  `risk_flags` list to every recommendation: imminent earnings (≤N days),
  crowded short interest, 52-week-low falling-knife test, above-target,
  high leverage, negative FCF, small-cap/high-beta context, plus supportive
  flags (strong-buy consensus, golden-cross). Added `dist_52w_low` indicator,
  config knobs, a "Risk / Catalyst" grid column, and CSV output.

- [x] **Iter 4 — Sector relative strength.** New
  `scoring/relative_strength.py`: 3-month return spread vs SPY and vs the
  stock's SPDR sector ETF (11-sector map, benchmarks TTL-cached so a scan adds
  ≤12 fetches). Leaders (+5pp) get a bounded momentum boost, laggards (−15pp) a
  haircut — folded in before the weighted blend, recorded as factors.
  `rel_strength` in the payload/CSV, "RS vs SPY" + "Sector" grid columns, and
  an RS line on mobile cards. Degrades to None offline.

## Next (prioritized)
- [x] **Iter 5 — Position sizing & risk/reward gates.** Each recommendation
  now includes a `position` (shares/value/risk-$) sized so the ATR-stop risks
  `MAX_RISK_PCT` of `ACCOUNT_SIZE`, plus `rr_pass` vs the `MIN_RISK_REWARD`
  floor — failures get a red R:R warn flag. Grid "Size" column + red R:R,
  mobile-card size line, CSV columns, config knobs, sizing-math test.
- [ ] **Iter 6 — "Top Gainers" leaderboard view.** New frontend page ranking
  by `expected_gain_pct` with quality grade, plus a sparkline per name.
- [ ] **Iter 7 — Alerts.** Wire `alerts/engine.py` into the daily scan to push
  the top high-quality setups (Slack/Discord/email) when configured.
- [ ] **Iter 8 — ML ranker.** Train a gradient-boosted model on historical
  setups → forward returns; blend with the rule-based score.
- [ ] **Iter 9 — Multi-timeframe confirmation.** Weekly + daily trend agreement
  to cut false bounces.
- [ ] **Iter 10 — Backtest the full screen.** Portfolio-level backtest of the
  ranked list (top-N each day) with equity curve on the Backtest page.

## Guardrails
- Each iteration: tests pass, atomic commit, this file updated.
- No network in tests. No secrets in code. Explainable outputs only.
- The user can stop the loop anytime.
