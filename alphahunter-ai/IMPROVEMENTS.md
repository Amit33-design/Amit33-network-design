# AlphaHunter — Improvement Roadmap (auto-improvement loop)

The product goal: **surface high-quality stocks with the best risk-adjusted
upside.** This file is the backlog the auto-improvement loop works through. Each
iteration ships one focused, tested change, commits to `main` (auto-deploys),
and checks the item off here.

Conventions: keep `pytest` green and offline; surface every new signal with its
inputs (explainability); add thresholds to `config.py`/`.env`, never hardcode.

## Done
- [x] **Retuned the score weights from realized returns (+28% predictive lift).**
  New `backend/analyze_signals.py` reconstructs forward returns offline from the
  committed scan history (1,489 samples) and correlates every signal against
  them. Result: **sentiment was the STRONGEST predictor (r=+0.216) at only 10%
  weight**, while **options (20% weight) was near-useless (r=+0.057)** and
  **momentum was NEGATIVE (r=-0.044)**. Weights moved 35/25/20/10/10 →
  **35 technical / 25 fundamental / 25 sentiment / 10 options / 5 momentum**,
  lifting composite-vs-forward-return correlation from **+0.101 to +0.130 on a
  HELD-OUT later half** (not just in-sample). Deliberately moderate — ~2 months
  in one regime. Re-runnable any time to re-justify the weights.
- [x] **Fixed the empty alpha: benchmark now reuses the scan's warm cache.**
  Root cause found — `relative_strength` fetches SPY at `period="6mo"` for
  every scored name during the scan, so that TTL key is warm, but
  `build_performance` asked for `"1y"`: a *different* cache key, forcing a
  fresh fetch at the end of a run that had already made hundreds of requests,
  exactly when Yahoo rate-limits. Alpha silently came back empty. It now tries
  the warm `"6mo"` key first, then `"1y"`, then a snapshot fallback, and is
  hardened against a non-datetime index. Locked in by a regression test that
  asserts `"6mo"` is requested first and no `"1y"` fetch follows.
- [x] **Recalibrated the alert gates from realized results.** The first
  segmented track record (405 aged picks) showed the digest was filtering on
  attributes that don't predict returns: grade **B was the WORST cohort
  (-7.1%)** yet was allowed, and **confidence was inverted** (Low +0.7% beat
  High -1.1% and Medium -3.6%) yet gated. Meanwhile **score was strongly
  predictive** (80+: 100% win / +19.9%; 60+: 30% / -3.5%). `select_alert_worthy`
  now gates on **score ≥ ALERT_MIN_SCORE (70) AND grade A**, drops the
  confidence gate, keeps the R:R gate, and ranks by score. Also hardened the
  SPY benchmark (snapshot fallback + explicit log) after it silently failed to
  load, leaving alpha empty on the first segmented report.
- [x] **Benchmark-relative track record (alpha vs SPY).** Raw returns were
  misleading — the blended win rate fell to 38% / -1.6% as history aged, but
  that number is meaningless without knowing what the market did. Every pick is
  now also measured against SPY over its *own* holding window: per-pick
  `benchmark_%` + `alpha_%`, summary `avg_alpha_%` / `beat_benchmark_rate`, and
  an alpha column on every cohort in the segment tables (which now rank by
  alpha, not raw return). The Dashboard headline leads with "% beat SPY" and a
  "vs SPY" tile. +2 tests (40 total).
- [x] **Track-record segmentation — closing the feedback loop.** `performance.py`
  now breaks realized results down by **quality grade, setup tier, confidence
  and score band** (win rate + avg return per cohort, best first). Cohorts with
  fewer than 3 picks are dropped so a 100%-on-one-pick fluke can't teach the
  wrong lesson. Surfaced on the Dashboard's Track Record section as a
  "What's actually working" grid — so scoring changes can be argued from
  realized returns instead of intuition. +1 test (38 total).
- [x] **Tradability floors (found via the track record).** The new track record
  exposed a real defect: a $0.05 warrant (PGYWW) scored 61 and lost 43%, and
  16 of 40 board names were under $5 (incl. $0.12/$0.19 warrants). Both
  scanners now hard-exclude, before scoring, any name under `MIN_PRICE` ($5),
  under `MIN_DOLLAR_VOLUME` ($5M/day avg), or with a warrant/unit/right
  ticker — `GOOGL` and `BRK-B` are explicitly protected from the symbol
  heuristic. Explainable via `tradability_reason()`; +2 tests.
- [x] **Click a ticker → its Analysis chart.** Tickers are now deep links
  (`/analysis?ticker=X`) from the Dashboard cards (plus a "📈 chart" affordance,
  with the rest of the card still tapping to the inline live thesis), the
  Opportunities grid, and the mobile opportunity cards. Analysis reads the
  `?ticker=` param, auto-runs on mount and on param change, and keeps the URL
  in sync when you analyze manually — so chart views are shareable and the
  back button works.
- [x] **2y default analysis range + watchlist validation (fixed dead SQ).**
  Analysis defaults to a 2-year chart so the view matches the long-term
  verdict logic. run_dashboard now reports tickers with no data (a `missing`
  list in dashboard.json + a prune warning in logs) — which immediately caught
  Block's SQ→XYZ ticker rename; watchlist fixed to XYZ.
- [x] **Trading-app chart zoom.** Price chart gains 1M/3M/6M/1Y/All quick-range
  buttons, a mini range-slider overview, scroll/pinch zoom with drag-to-pan
  (no more distorted zoom boxes), y-axis auto-refit to the visible window,
  double-click reset, and a cleaned modebar. Volume/MACD/RSI subplots get
  scroll-zoom + double-click reset. On-chart hint documents the controls.
- [x] **Opportunities filters + broader watchlist.** Filter bar on
  Opportunities (Setup: crash dip/pullback · Quality: A/B · Confidence:
  High/Medium) with live shown-count and a "loosen filters" empty-state;
  filtering is client-side over the scan. Watchlist grows 30 → 40 with three
  new domains: Healthcare/Pharma (LLY UNH JNJ PFE), Defense/Aerospace
  (LMT RTX NOC), Retail/Consumer (WMT COST TGT).
- [x] **Two-layer verdict: long-term trend decides, short-term only times.**
  Rebuilt the Analysis + Portfolio verdict logic (api/ta.js, api/quote.js):
  Layer 1 (trend score) uses only slow structure — 200-day, 50/200 regime,
  weekly trend, market cycle, 6-12mo returns — and DECIDES the Buy/Hold/Sell
  class; Layer 2 (timing score) uses RSI/MACD/weekly move and only tunes the
  entry. Downtrends can never say Buy (a green week = counter-trend rally);
  uptrend dips can never say Sell (oversold in an uptrend = entry). UI shows
  "Long-term trend ▲ UP 74" + "Entry timing Good 65" chips and splits "Why
  this signal" into trend vs timing columns; verdict_reason leads with trend.
- [x] **Fetch resilience + setup-tier visibility.** `MarketData` now retries
  transient fetch failures (Yahoo 429s) with bounded exponential backoff via
  `with_retries()` — exceptions retry, clean empties (delisted) do NOT, so the
  scan doesn't slow down; knobs FETCH_RETRIES / FETCH_BACKOFF_SECONDS. The
  Opportunities grid + mobile cards + daily CSV now show each name's setup
  tier: "Crash dip" (strict screen, highest conviction) vs "Pullback" (broad
  opportunity screen) with explanatory tooltips.
- [x] **Track record (accountability).** New `backend/performance.py` prices
  each day's historical top-10 picks today (dated `results/*.json` history →
  per-pick return since pick, win rate, avg return, best/worst; picks aged
  <2 days excluded; pricing bounded + TTL-cached). run_daily writes
  `frontend/public/performance.json` (guaranteed to exist) and the workflow
  commits it. Dashboard gains a collapsible "📈 Track Record" section with
  summary tiles + recent-picks table. Pure `summarize_picks` tested offline.
- [x] **Fix empty Opportunities/Options + retire Backtest & Top Gainers tabs.**
  OpportunityScanner broad pullback screen + run_daily fallback (verified live:
  40 ranked names on 2026-07-16 after zero-hit strict scans); helpful
  empty-states; removed tabs redirect to Dashboard.
- [x] **Real-time thesis API + Dashboard redesign.** New `api/thesis.js` —
  compact per-stock thesis endpoint (`/api/thesis?ticker=X`: price, day move,
  verdict, score, narrative; edge-cached 5 min) like a real trading app.
  Dashboard: tap any stock card to fetch its live thesis inline; cards get
  30-day sparklines (real closes from run_dashboard; placeholder until next
  cron), score-colored left borders, a "Today's movers" strip (top gainers/
  losers), and per-domain average-score chips + leader callouts.
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
- [x] **Iter 6 — "Top Gainers" leaderboard view.** New /gainers page ranked by
  `expected_gain_%` (realistic upside, not raw targets): podium top-3 cards
  (grade, confidence, historical bounce rate, CSP badge), full leaderboard
  table (exp. gain, analyst upside, quality, score, hist win%, warn flags),
  and a "Quality A/B only" filter. Works offline from the snapshot.
- [x] **Iter 7 — Alerts.** `run_daily` now pushes a morning digest of the top
  high-conviction setups via `alerts.engine.send_scan_digest()`:
  `select_alert_worthy()` keeps A/B quality + High/Medium confidence + passing
  R:R, ranked by expected gain; `format_digest()` renders it. Delivers to
  Slack/Discord webhooks (SLACK_WEBHOOK_URL / DISCORD_WEBHOOK_URL repo secrets,
  wired into alphahunter-scan.yml) and degrades to logging when unset. +2 tests.
- [ ] **Iter 8 — ML ranker.** Train a gradient-boosted model on historical
  setups → forward returns; blend with the rule-based score.
- [x] **Iter 9 — Multi-timeframe confirmation.** New `technical.weekly_trend()`
  reads a higher-timeframe (10-week EMA) trend and folds agreement into the
  momentum sub-score: weekly-up confirms the daily bounce (+6), weekly-down
  flags counter-trend / false-bounce risk (−8). Surfaced as `mtf` in the
  payload, a reasoning sentence, a "Weekly uptrend/downtrend" badge on the
  Analysis tab, plus the same logic + thesis line in `api/ta.js`. +2 tests.
- [ ] **Iter 10 — Backtest the full screen.** Portfolio-level backtest of the
  ranked list (top-N each day) with equity curve on the Backtest page.

## Guardrails
- Each iteration: tests pass, atomic commit, this file updated.
- No network in tests. No secrets in code. Explainable outputs only.
- The user can stop the loop anytime.
