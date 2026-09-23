// Shared indicator maths for the serverless functions.
//
// Files prefixed with "_" are not routed by Vercel, so this is a module rather
// than an endpoint.
//
// WHY THIS EXISTS: RSI was implemented three times — Wilder-smoothed in
// ta.js, and as a plain 14-day average in peers.js and quote.js. The same
// ticker therefore showed RSI 48.5 in the peer table and 52.7 in the
// indicator grid, and worse, quote.js drives Buy/Hold/Sell decisions off
// thresholds at 35 and 70, so a non-standard RSI made those fire at the wrong
// times. RSI means Wilder's RSI; anything else is a different indicator
// wearing its name.
//
// Keep in parity with backend/indicators/technical.py, which uses
// ewm(alpha=1/period) — mathematically the same recursion as below.

/** Wilder-smoothed RSI for every bar; null until the series warms up. */
export function rsiSeries(closes, period = 14) {
  const out = (closes || []).map(() => null);
  if (!closes || closes.length < period + 1) return out;

  // Seed with a simple average of the first `period` changes...
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1];
    if (d >= 0) avgGain += d; else avgLoss -= d;
  }
  avgGain /= period;
  avgLoss /= period;
  out[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);

  // ...then smooth recursively. This is the step the other two copies were
  // missing, and it is what makes RSI respond to the whole series rather than
  // only the last 14 bars.
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(d, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-d, 0)) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}

/** The latest Wilder RSI, or null. */
export function rsiLast(closes, period = 14) {
  const s = rsiSeries(closes, period);
  for (let i = s.length - 1; i >= 0; i--) {
    if (s[i] != null) return s[i];
  }
  return null;
}

/** Round a price to cents, half away from zero.
 *
 *  Matches backend/exit_rules.money() and frontend/src/lib/exitRules.ts, all
 *  pinned to one shared fixture. JavaScript's Math.round rounds -3.695 to
 *  -3.69 (toward +infinity on a half) and Python's round() is banker's
 *  rounding, so without a shared rule the same stop came out a cent apart on
 *  different pages.
 */
export function money(x) {
  return Math.sign(x) * Math.round((Math.abs(x) + Number.EPSILON) * 100) / 100;
}

/** Exit levels for a position — the serverless twin of build_plan().
 *
 *  Same arithmetic as backend/exit_rules.build_plan and the frontend port, and
 *  pinned to the same fixture. ta.js used to inline this, which is why it
 *  could not be tested and why its rounding had quietly drifted.
 */
export function exitLevels(price, atr, horizonDays = 10) {
  let targetPct = 12.0;
  let stopPct = -7.0;
  if (atr && atr > 0 && price > 0) {
    const horizonMove = (atr / price) * 100 * Math.sqrt(horizonDays);
    targetPct = Math.max(5, Math.min(30, horizonMove));
    stopPct = -Math.max(3, Math.min(15, horizonMove * 0.6));
  }
  return {
    target: money(price * (1 + targetPct / 100)),
    stop: money(price * (1 + stopPct / 100)),
    target_pct: money(targetPct),
    stop_pct: money(stopPct),
    targetPctRaw: targetPct,
    stopPctRaw: stopPct,
  };
}
