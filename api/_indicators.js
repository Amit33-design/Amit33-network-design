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
