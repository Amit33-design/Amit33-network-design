# AlphaHunter — Improvement Roadmap (auto-improvement loop)

The product goal: **surface high-quality stocks with the best risk-adjusted
upside.** This file is the backlog the auto-improvement loop works through. Each
iteration ships one focused, tested change, commits to `main` (auto-deploys),
and checks the item off here.

Conventions: keep `pytest` green and offline; surface every new signal with its
inputs (explainability); add thresholds to `config.py`/`.env`, never hardcode.

## Done
- [x] **Iter 1 — Quality grade + expected-gain ranking.** Richer multi-factor
  fundamental/quality score (ROE, ROA, margins, PEG, growth, leverage,
  liquidity) → A–F `quality_grade`; `expected_gain_pct` (analyst upside
  tempered by confidence & quality); surfaced in API, CSV, and the grid.

## Next (prioritized)
- [ ] **Iter 2 — Backtest-calibrated confidence.** For each hit, compute the
  historical bounce rate + avg forward return of its setup (reuse
  `backtesting/engine.py`) and show "historically bounced X% of the time,
  avg +Y%". Calibrate `confidence` to that, not just criteria count.
- [ ] **Iter 3 — Catalyst & risk awareness.** Flag earnings within N days
  (avoid pre-earnings landmines), recent analyst upgrades/downgrades, and
  distance-to-52w-low support. Add a `risk_flags` list per recommendation.
- [ ] **Iter 4 — Sector relative strength.** Rank each name vs its sector ETF
  and vs SPY; reward leaders in strong sectors. Add `rel_strength` score.
- [ ] **Iter 5 — Position sizing & risk/reward gates.** Suggest size from ATR
  and a max-risk %, and filter out setups with R:R below a floor.
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
