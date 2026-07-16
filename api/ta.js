// Vercel serverless function: GET/POST /api/ta?ticker=AAPL[&range=1y]
// Real-time single-ticker technical analysis for the Analysis tab. Fetches the
// daily OHLCV series from Yahoo's open v8 chart endpoint (no auth) and returns
// the price history + EMA overlays + RSI series + a full indicator panel and a
// trend/momentum Buy-Hold-Sell verdict with explainable factors.

const CHART = (t, range) =>
  `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(t)}?range=${range}&interval=1d`;

const ema = (arr, span) => {
  if (arr.length < span) return arr.map(() => null);
  const k = 2 / (span + 1);
  const out = [];
  let prev = arr[0];
  arr.forEach((v, i) => {
    prev = i === 0 ? v : v * k + prev * (1 - k);
    out.push(i >= span - 1 ? prev : null);
  });
  return out;
};

const smaLast = (arr, n) =>
  arr.length < n ? null : arr.slice(-n).reduce((a, b) => a + b, 0) / n;

function rsiSeries(closes, period = 14) {
  const out = closes.map(() => null);
  if (closes.length < period + 1) return out;
  let ag = 0, al = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1];
    if (d >= 0) ag += d; else al -= d;
  }
  ag /= period; al /= period;
  out[period] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    ag = (ag * (period - 1) + Math.max(d, 0)) / period;
    al = (al * (period - 1) + Math.max(-d, 0)) / period;
    out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
  }
  return out;
}

function macdSeries(closes) {
  const e12 = ema(closes, 12), e26 = ema(closes, 26);
  const line = closes.map((_, i) => (e12[i] != null && e26[i] != null ? e12[i] - e26[i] : null));
  const valid = line.filter((x) => x != null);
  const sig = ema(valid, 9);
  const pad = line.length - valid.length;
  const signal = line.map((_, i) => (i >= pad ? sig[i - pad] : null));
  const histS = line.map((_, i) => (line[i] != null && signal[i] != null ? line[i] - signal[i] : null));
  return { line, signal, hist: histS };
}

function smaSeries(arr, n) {
  return arr.map((_, i) => (i >= n - 1 ? arr.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0) / n : null));
}

function bollinger(closes, n = 20, mult = 2) {
  const mid = smaSeries(closes, n);
  const upper = [], lower = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) { upper.push(null); lower.push(null); continue; }
    const win = closes.slice(i - n + 1, i + 1);
    const m = mid[i];
    const sd = Math.sqrt(win.reduce((a, b) => a + (b - m) ** 2, 0) / n);
    upper.push(m + mult * sd);
    lower.push(m - mult * sd);
  }
  return { mid, upper, lower };
}

// Bull/bear market cycle: regime = 50-day SMA above/below 200-day SMA. Segment
// the series into phases and report the current one + past phases for shading.
function cycles(dates, closes) {
  const s50 = smaSeries(closes, 50);
  const s200 = smaSeries(closes, 200);
  const regime = closes.map((_, i) =>
    s50[i] != null && s200[i] != null ? (s50[i] >= s200[i] ? "bull" : "bear") : null
  );
  const phases = [];
  let cur = null;
  regime.forEach((r, i) => {
    if (r == null) return;
    if (!cur || cur.type !== r) {
      if (cur) cur.end = dates[i - 1];
      cur = { type: r, start: dates[i], end: dates[dates.length - 1], startIdx: i };
      phases.push(cur);
    }
  });
  const last = phases[phases.length - 1] || null;
  const daysIn = last ? closes.length - last.startIdx : null;
  return {
    current: last ? last.type : "indeterminate",
    days_in_phase: daysIn,
    since: last ? last.start : null,
    phases: phases.map((p) => ({ type: p.type, start: p.start, end: p.end })),
  };
}

// Support/resistance from recent swing lows/highs (fractal-style) + pivots.
function levels(highs, lows, closes) {
  const N = Math.min(closes.length, 120);
  const h = highs.slice(-N), l = lows.slice(-N), c = closes[closes.length - 1];
  const swingHi = [], swingLo = [];
  for (let i = 2; i < N - 2; i++) {
    if (h[i] > h[i - 1] && h[i] > h[i - 2] && h[i] > h[i + 1] && h[i] > h[i + 2]) swingHi.push(h[i]);
    if (l[i] < l[i - 1] && l[i] < l[i - 2] && l[i] < l[i + 1] && l[i] < l[i + 2]) swingLo.push(l[i]);
  }
  const resistance = [...new Set(swingHi.filter((x) => x > c).map((x) => Math.round(x * 100) / 100))]
    .sort((a, b) => a - b).slice(0, 3);
  const support = [...new Set(swingLo.filter((x) => x < c).map((x) => Math.round(x * 100) / 100))]
    .sort((a, b) => b - a).slice(0, 3);
  return { support, resistance };
}

// Historical down-day bounce stats: for every session that dropped <= dipPct,
// how often was the close 10 sessions later higher, and by how much on average?
function dipBounceStats(closes, dipPct = -2.0, holdDays = 10) {
  const rets = [];
  for (let i = 1; i < closes.length - holdDays; i++) {
    const day = ((closes[i] - closes[i - 1]) / closes[i - 1]) * 100;
    if (day <= dipPct) {
      rets.push(((closes[i + holdDays] - closes[i]) / closes[i]) * 100);
    }
  }
  if (!rets.length) return { dips: 0, win_rate: null, avg_return: null };
  const wins = rets.filter((r) => r > 0).length;
  return {
    dips: rets.length,
    win_rate: Math.round((wins / rets.length) * 100) / 100,
    avg_return: Math.round((rets.reduce((a, b) => a + b, 0) / rets.length) * 10) / 10,
  };
}

// CSP-on-dip: stock is down today, the chart still points up (above 200-day /
// bullish cycle), and history says dips like this tend to bounce -> selling a
// cash-secured put into the weakness collects elevated premium at a discount
// strike. Returns an always-present, explainable signal object.
function cspSignal(dayChange, last, s200, cyc, sr, a, bounce) {
  const out = { active: false, strength: null, suggested_strike: null, reason: "" };
  if (dayChange == null || dayChange > -2.0) {
    out.reason = "no meaningful dip today";
    return out;
  }
  const chartUp = (s200 != null && last > s200) || cyc.current === "bull";
  if (!chartUp) {
    out.reason = `down ${dayChange.toFixed(1)}% but chart lacks upside (below 200-day, bearish cycle)`;
    return out;
  }
  if (bounce.dips >= 3 && (bounce.win_rate < 0.45 || bounce.avg_return < 0)) {
    out.reason = `down ${dayChange.toFixed(1)}% in an uptrend, but similar dips bounced only ${(bounce.win_rate * 100).toFixed(0)}% of ${bounce.dips} times`;
    return out;
  }
  const strong = bounce.dips >= 3 && bounce.win_rate >= 0.55 && bounce.avg_return > 0;
  out.active = true;
  out.strength = strong ? "strong" : "moderate";
  const atrStrike = a != null ? last - 1.5 * a : null;
  const supp = (sr.support || [])[0];
  out.suggested_strike = Math.round(((supp != null && atrStrike != null && supp > atrStrike ? supp : atrStrike) ?? last * 0.95) * 100) / 100;
  const bits = [`down ${dayChange.toFixed(1)}% today`, "uptrend intact"];
  if (strong) bits.push(`similar dips bounced ${(bounce.win_rate * 100).toFixed(0)}% of ${bounce.dips} times (avg ${bounce.avg_return >= 0 ? "+" : ""}${bounce.avg_return}% in 10d)`);
  else if (bounce.dips >= 3) bits.push(`dip history mixed (${(bounce.win_rate * 100).toFixed(0)}% of ${bounce.dips})`);
  else bits.push("limited dip history");
  out.reason = bits.join("; ");
  return out;
}

// "Potential bottom" detector: checks 6 classic bottoming tells and reports a
// full checklist (firing AND not-firing, each with a reason), so the UI can
// show exactly why the likelihood is what it is. Score = sum of firing tells:
// <35 low, 35-59 possible, >=60 high.
function bottomSignal(o, h, l, c, v, rsis, e20, sr) {
  const n = c.length;
  const last = c[n - 1];
  let score = 0;
  const checks = [];
  const add = (ok, pts, onText, offText) => {
    if (ok) score += pts;
    checks.push({ ok, pts: ok ? pts : 0, max: pts, s: ok ? onText : offText });
  };

  const rsi = rsis[n - 1];
  add(
    rsi != null && rsi < 40,
    rsi != null && rsi < 30 ? 25 : 12,
    rsi != null && rsi < 30 ? `deeply oversold (RSI ${rsi?.toFixed(0)})` : `oversold (RSI ${rsi?.toFixed(0)})`,
    rsi != null ? `RSI not oversold (${rsi.toFixed(0)}, needs <40)` : "RSI unavailable"
  );

  // Bullish RSI divergence over the last ~20 sessions.
  const w = Math.min(20, n - 1);
  const pMinIdx = c.lastIndexOf(Math.min(...c.slice(-w)));
  const prevMinIdx = c.slice(0, n - Math.floor(w / 2)).lastIndexOf(Math.min(...c.slice(-2 * w, -Math.floor(w / 2))));
  const diverging = pMinIdx > prevMinIdx && prevMinIdx >= 0 && c[pMinIdx] < c[prevMinIdx]
    && rsis[pMinIdx] != null && rsis[prevMinIdx] != null && rsis[pMinIdx] > rsis[prevMinIdx];
  add(diverging, 22,
    "bullish RSI divergence (price lower low, RSI higher low)",
    "no bullish RSI divergence");

  // Near the 52-week low.
  const lo52 = Math.min(...c.slice(-252));
  const abovLow = lo52 ? ((last - lo52) / lo52) * 100 : null;
  add(abovLow != null && abovLow < 8, 15,
    "at/near 52-week low",
    abovLow != null ? `${abovLow.toFixed(0)}% above 52-week low (needs <8%)` : "52w low unavailable");

  // Testing a support level.
  const supp = (sr.support || [])[0];
  add(supp != null && Math.abs(last - supp) / last < 0.04, 10,
    `testing support ~$${supp}`,
    supp != null ? `next support $${supp} not being tested` : "no support level below price");

  // Capitulation volume + reversal (long lower wick) candle in last 3 days.
  const avgV = v.slice(-20).reduce((a, b) => a + b, 0) / Math.min(20, v.length);
  let hammer = false;
  for (let i = Math.max(1, n - 3); i < n; i++) {
    const body = Math.abs(c[i] - o[i]);
    const lowerWick = Math.min(o[i], c[i]) - l[i];
    if (v[i] > 1.8 * avgV && lowerWick > 1.5 * body && c[i] >= o[i]) { hammer = true; break; }
  }
  add(hammer, 16,
    "capitulation volume + hammer reversal candle",
    "no capitulation/hammer candle in last 3 days");

  // Short-term reclaim: back above the 20-day EMA after being below it.
  const reclaimed = e20[n - 1] != null && e20[n - 2] != null && c[n - 2] < e20[n - 2] && last > e20[n - 1];
  add(reclaimed, 12,
    "reclaimed 20-day EMA",
    e20[n - 1] != null && last > e20[n - 1] ? "already above 20-day EMA (no fresh reclaim)" : "still below 20-day EMA");

  score = Math.min(100, score);
  const label = score >= 60 ? "high" : score >= 35 ? "possible" : "low";
  const firing = checks.filter((x) => x.ok).length;
  return {
    score,
    likelihood: label,
    firing,
    total: checks.length,
    checks,
    explainer:
      `Bottoming-evidence score: ${firing} of ${checks.length} classic reversal tells firing ` +
      `(${score}/100). <35 = low, 35-59 = possible, >=60 = high likelihood the stock is forming a bottom.`,
    // kept for backward compatibility with older frontends
    factors: checks.filter((x) => x.ok).map((x) => ({ t: "bull", s: x.s })),
  };
}

// Recent crossover / breakout signals for the last ~90 sessions.
function signals(dates, closes, s50, s200, macdS, rsis, bb) {
  const out = [];
  const start = Math.max(1, closes.length - 90);
  for (let i = start; i < closes.length; i++) {
    if (s50[i] != null && s200[i] != null && s50[i - 1] != null && s200[i - 1] != null) {
      if (s50[i - 1] <= s200[i - 1] && s50[i] > s200[i]) out.push({ date: dates[i], type: "bull", label: "Golden cross (50>200)" });
      if (s50[i - 1] >= s200[i - 1] && s50[i] < s200[i]) out.push({ date: dates[i], type: "bear", label: "Death cross (50<200)" });
    }
    if (macdS.line[i] != null && macdS.signal[i] != null && macdS.line[i - 1] != null && macdS.signal[i - 1] != null) {
      if (macdS.line[i - 1] <= macdS.signal[i - 1] && macdS.line[i] > macdS.signal[i]) out.push({ date: dates[i], type: "bull", label: "MACD bullish cross" });
      if (macdS.line[i - 1] >= macdS.signal[i - 1] && macdS.line[i] < macdS.signal[i]) out.push({ date: dates[i], type: "bear", label: "MACD bearish cross" });
    }
    if (rsis[i] != null && rsis[i - 1] != null) {
      if (rsis[i - 1] < 30 && rsis[i] >= 30) out.push({ date: dates[i], type: "bull", label: "RSI back above 30 (oversold exit)" });
      if (rsis[i - 1] > 70 && rsis[i] <= 70) out.push({ date: dates[i], type: "bear", label: "RSI back below 70" });
    }
    if (bb.upper[i] != null && closes[i] > bb.upper[i] && closes[i - 1] <= bb.upper[i - 1]) out.push({ date: dates[i], type: "bull", label: "Bollinger upper breakout" });
    if (bb.lower[i] != null && closes[i] < bb.lower[i] && closes[i - 1] >= bb.lower[i - 1]) out.push({ date: dates[i], type: "bear", label: "Bollinger lower breakdown" });
  }
  return out.reverse().slice(0, 10);
}

function atr(highs, lows, closes, period = 14) {
  if (closes.length < period + 1) return null;
  let sum = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const tr = Math.max(
      highs[i] - lows[i],
      Math.abs(highs[i] - closes[i - 1]),
      Math.abs(lows[i] - closes[i - 1])
    );
    sum += tr;
  }
  return sum / period;
}

// Weekly (higher-timeframe) trend from daily closes: last close of each
// 5-day block vs a 10-week EMA. Confirms or contradicts the daily setup.
function weeklyTrend(c) {
  if (c.length < 60) return { trend: "flat", weekly_return_pct: null };
  const weekly = [];
  for (let i = c.length - 1; i >= 0; i -= 5) weekly.unshift(c[i]);
  if (weekly.length < 12) return { trend: "flat", weekly_return_pct: null };
  const k = 2 / 11;
  let e = weekly[0];
  const series = [e];
  for (let i = 1; i < weekly.length; i++) { e = weekly[i] * k + e * (1 - k); series.push(e); }
  const above = weekly[weekly.length - 1] > series[series.length - 1];
  const rising = series[series.length - 1] > series[series.length - 3];
  const trend = above && rising ? "up" : !above && !rising ? "down" : "flat";
  const wret = weekly.length > 11
    ? Math.round(((weekly[weekly.length - 1] - weekly[weekly.length - 11]) / weekly[weekly.length - 11]) * 1000) / 10
    : null;
  return { trend, weekly_return_pct: wret };
}

function analyze(dates, o, h, l, c, v) {
  const last = c[c.length - 1];
  const e20 = ema(c, 20), e50 = ema(c, 50), e200 = ema(c, 200);
  const rsis = rsiSeries(c);
  const rsi = rsis[rsis.length - 1];
  const macdS = macdSeries(c);
  const m = { macd: macdS.line[c.length - 1], signal: macdS.signal[c.length - 1], hist: macdS.hist[c.length - 1] };
  const s50series = smaSeries(c, 50), s200series = smaSeries(c, 200);
  const s50 = smaLast(c, 50), s200 = smaLast(c, 200);
  const a = atr(h, l, c);
  const bb = bollinger(c);
  const cyc = cycles(dates, c);
  const sr = levels(h, l, c);
  const sigs = signals(dates, c, s50series, s200series, macdS, rsis, bb);
  const dayChange = c.length >= 2 ? ((last - c[c.length - 2]) / c[c.length - 2]) * 100 : null;
  const bounce = dipBounceStats(c);
  const csp = cspSignal(dayChange, last, s200, cyc, sr, a, bounce);
  const bottom = bottomSignal(o, h, l, c, v, rsis, e20, sr);
  const hi52 = Math.max(...c.slice(-252)), lo52 = Math.min(...c.slice(-252));
  const ret = (n) => (c.length > n ? ((last - c[c.length - 1 - n]) / c[c.length - 1 - n]) * 100 : null);
  const avgVol = v.length >= 20 ? v.slice(-20).reduce((a, b) => a + b, 0) / 20 : null;
  const distHigh = hi52 ? ((last - hi52) / hi52) * 100 : null;
  const distLow = lo52 ? ((last - lo52) / lo52) * 100 : null;

  // ================= TWO-LAYER VERDICT =================
  // Layer 1 — LONG-TERM TREND decides the direction (Buy/Hold/Sell class).
  // Built only from structural, slow-moving evidence: 200-day, 50/200 regime,
  // weekly trend, market cycle, 6-12 month structure. A red week can't flip it.
  const mtf = weeklyTrend(c);
  const r6 = ret(126);
  const r12 = ret(252);
  let lt = 50;
  const trendFactors = [];
  if (s200 != null) {
    if (last > s200) { lt += 15; trendFactors.push({ t: "bull", s: "Price above 200-day SMA (primary uptrend)" }); }
    else { lt -= 15; trendFactors.push({ t: "bear", s: "Price below 200-day SMA (primary downtrend)" }); }
  }
  if (s50 != null && s200 != null) {
    if (s50 > s200) { lt += 9; trendFactors.push({ t: "bull", s: "50-day above 200-day (golden-cross regime)" }); }
    else { lt -= 9; trendFactors.push({ t: "bear", s: "50-day below 200-day (death-cross regime)" }); }
  }
  if (mtf.trend === "up") { lt += 9; trendFactors.push({ t: "bull", s: "Weekly (10-week) trend rising" }); }
  else if (mtf.trend === "down") { lt -= 9; trendFactors.push({ t: "bear", s: "Weekly (10-week) trend falling" }); }
  if (cyc.current === "bull") { lt += 6; trendFactors.push({ t: "bull", s: `Bullish market cycle (${cyc.days_in_phase}d)` }); }
  else if (cyc.current === "bear") { lt -= 6; trendFactors.push({ t: "bear", s: `Bearish market cycle (${cyc.days_in_phase}d)` }); }
  if (r12 != null) {
    if (r12 > 15) { lt += 7; trendFactors.push({ t: "bull", s: `+${r12.toFixed(0)}% over 12 months (long-term winner)` }); }
    else if (r12 < -15) { lt -= 7; trendFactors.push({ t: "bear", s: `${r12.toFixed(0)}% over 12 months (long-term loser)` }); }
  }
  if (r6 != null) {
    if (r6 > 10) { lt += 4; trendFactors.push({ t: "bull", s: `+${r6.toFixed(0)}% over 6 months` }); }
    else if (r6 < -10) { lt -= 4; trendFactors.push({ t: "bear", s: `${r6.toFixed(0)}% over 6 months` }); }
  }
  if (distHigh != null && distHigh > -12 && (s200 == null || last > s200)) {
    lt += 4; trendFactors.push({ t: "bull", s: "Consolidating near 52-week highs" });
  }
  lt = Math.max(0, Math.min(100, Math.round(lt)));
  const ltDir = lt >= 60 ? "up" : lt <= 40 ? "down" : "mixed";

  // Layer 2 — SHORT-TERM TIMING only tunes the entry WITHIN that direction.
  // Oversold in an uptrend = dip entry (bullish!), overbought = wait; the
  // same signals invert inside a downtrend (bounces there are exit windows).
  let st = 50;
  const timingFactors = [];
  if (rsi != null) {
    if (rsi < 35 && ltDir === "up") { st += 15; timingFactors.push({ t: "bull", s: `Oversold dip (RSI ${rsi.toFixed(0)}) inside an uptrend — favorable entry` }); }
    else if (rsi < 35 && ltDir === "down") { st -= 4; timingFactors.push({ t: "bear", s: `Oversold (RSI ${rsi.toFixed(0)}) but the long-term trend is down — falling knife, not a dip` }); }
    else if (rsi > 70) { st -= 10; timingFactors.push({ t: "neutral", s: `Extended (RSI ${rsi.toFixed(0)}) — better to wait for a pullback` }); }
    else timingFactors.push({ t: "neutral", s: `RSI ${rsi.toFixed(0)} (neutral timing)` });
  }
  if (m.hist != null) {
    if (m.hist > 0) { st += 6; timingFactors.push({ t: "bull", s: "MACD momentum turning up" }); }
    else { st -= 6; timingFactors.push({ t: "bear", s: "MACD momentum still down" }); }
  }
  const w1 = ret(5);
  if (w1 != null && w1 <= -5 && ltDir === "up") {
    st += 6; timingFactors.push({ t: "bull", s: `Pulled back ${w1.toFixed(0)}% this week inside an uptrend` });
  } else if (w1 != null && w1 >= 8 && ltDir === "down") {
    st -= 6; timingFactors.push({ t: "bear", s: `+${w1.toFixed(0)}% bounce this week is counter-trend — rallies in downtrends fade` });
  }
  if (distLow != null && distLow < 8 && ltDir !== "down") {
    st += 4; timingFactors.push({ t: "bull", s: "Sitting on 52-week-low support" });
  }
  st = Math.max(0, Math.min(100, Math.round(st)));

  // Verdict: LONG-TERM decides the class; timing picks within it. A downtrend
  // can never produce Buy, and an uptrend's dip can never produce Sell.
  let recommendation;
  if (ltDir === "up") recommendation = st >= 55 ? "Buy" : st >= 40 ? "Accumulate" : "Hold";
  else if (ltDir === "down") recommendation = st >= 60 ? "Reduce" : st >= 40 ? "Reduce" : "Sell";
  else recommendation = st >= 60 ? "Accumulate" : st >= 35 ? "Hold" : "Reduce";
  const score = Math.round(0.7 * lt + 0.3 * st);

  const factors = [...trendFactors, ...timingFactors];
  const dirWord = ltDir === "up" ? "UP" : ltDir === "down" ? "DOWN" : "MIXED";
  let verdict_reason =
    `${recommendation} — driven by the LONG-TERM trend, which is ${dirWord} (trend score ${lt}/100), ` +
    `not by this week's move. `;
  const tf = trendFactors.slice(0, 3).map((f) => f.s);
  if (tf.length) verdict_reason += `Structure: ${tf.join("; ")}. `;
  const tm = timingFactors.slice(0, 2).map((f) => f.s);
  if (tm.length) verdict_reason += `Timing (secondary): ${tm.join("; ")}.`;

  return {
    price: last,
    day_change_pct: dayChange,
    verdict_reason,
    score,
    recommendation,
    trend: { score: lt, direction: ltDir, factors: trendFactors },
    timing: { score: st, factors: timingFactors },
    factors,
    cycle: cyc,
    levels: sr,
    signals: sigs,
    csp_signal: csp,
    dip_bounce: bounce,
    bottom: bottom,
    mtf: mtf,
    indicators: {
      rsi: rsi != null ? Math.round(rsi * 10) / 10 : null,
      macd: m.macd != null ? Math.round(m.macd * 100) / 100 : null,
      macd_signal: m.signal != null ? Math.round(m.signal * 100) / 100 : null,
      macd_hist: m.hist != null ? Math.round(m.hist * 100) / 100 : null,
      ema20: e20[e20.length - 1], ema50: e50[e50.length - 1], ema200: e200[e200.length - 1],
      sma50: s50, sma200: s200, atr: a != null ? Math.round(a * 100) / 100 : null,
      ret_1m: ret(21), ret_3m: ret(63), ret_6m: r6, ret_1y: ret(252),
      dist_52w_high: distHigh != null ? Math.round(distHigh * 10) / 10 : null,
      dist_52w_low: distLow != null ? Math.round(distLow * 10) / 10 : null,
      high_52w: hi52, low_52w: lo52,
      avg_volume: avgVol != null ? Math.round(avgVol) : null,
      last_volume: v[v.length - 1] || null,
    },
    chart: {
      dates,
      open: o.map((x) => Math.round(x * 100) / 100),
      high: h.map((x) => Math.round(x * 100) / 100),
      low: l.map((x) => Math.round(x * 100) / 100),
      close: c.map((x) => Math.round(x * 100) / 100),
      volume: v,
      ema20: e20, ema50: e50, ema200: e200,
      bb_upper: bb.upper, bb_mid: bb.mid, bb_lower: bb.lower,
      rsi: rsis.map((x) => (x != null ? Math.round(x * 10) / 10 : null)),
      macd: macdS.line, macd_signal: macdS.signal, macd_hist: macdS.hist,
    },
  };
}

// Build a plain-English thesis: is the move market-driven or stock-specific,
// what does the trend/cycle say, and how have similar dips resolved?
function buildThesis(t, out, spyCloses) {
  const parts = [];
  const day = out.day_change_pct;
  const c = out.chart.close;
  const monthRet = c.length > 21 ? ((c[c.length - 1] - c[c.length - 22]) / c[c.length - 22]) * 100 : null;

  let spyDay = null, spyMonth = null;
  if (spyCloses && spyCloses.length > 22) {
    const m = spyCloses.length - 1;
    spyDay = ((spyCloses[m] - spyCloses[m - 1]) / spyCloses[m - 1]) * 100;
    spyMonth = ((spyCloses[m] - spyCloses[m - 22]) / spyCloses[m - 22]) * 100;
  }

  // Today's move: market-wide or specific to this name?
  if (day != null && day <= -1.5) {
    if (spyDay != null && spyDay <= -1.0) {
      parts.push(`${t} is down ${day.toFixed(1)}% today alongside a broad market pullback ` +
        `(S&P 500 ${spyDay.toFixed(1)}%) — much of the weakness is market-driven, not company news.`);
    } else if (spyDay != null && spyDay > -0.3) {
      parts.push(`${t} is down ${day.toFixed(1)}% today while the broader market is flat ` +
        `(S&P 500 ${spyDay >= 0 ? "+" : ""}${spyDay.toFixed(1)}%) — this looks stock-specific ` +
        `(sector rotation, downgrades, or company news), so check headlines before buying the dip.`);
    } else if (spyDay != null) {
      parts.push(`${t} is down ${day.toFixed(1)}% today, more than the market (S&P 500 ${spyDay.toFixed(1)}%) — ` +
        `partly market weakness, partly its own.`);
    }
  } else if (day != null && day >= 1.5 && spyDay != null) {
    parts.push(`${t} is up ${day.toFixed(1)}% today vs S&P 500 ${spyDay >= 0 ? "+" : ""}${spyDay.toFixed(1)}% — ` +
      `${day > spyDay + 1 ? "outpacing the market (relative strength)" : "moving with the market"}.`);
  }

  // The last month vs the market: relative context from ITS OWN numbers.
  if (monthRet != null && spyMonth != null) {
    const spread = monthRet - spyMonth;
    if (spread <= -8) {
      parts.push(`Over the past month it has lagged the market by ${Math.abs(spread).toFixed(0)}pp ` +
        `(${monthRet.toFixed(0)}% vs S&P ${spyMonth >= 0 ? "+" : ""}${spyMonth.toFixed(0)}%) — ` +
        `money is rotating away from this name, so it likely needs its own catalyst, not just a market bounce.`);
    } else if (spread >= 8) {
      parts.push(`Over the past month it has beaten the market by ${spread.toFixed(0)}pp — a leader, ` +
        `and leaders tend to recover first when pressure lifts.`);
    }
  }

  // Stock character — derived from this ticker's own profile so every thesis
  // is specific: momentum phase, 52-week position, and typical volatility.
  const ret6 = out.indicators.ret_6m;
  const dHigh = out.indicators.dist_52w_high;   // % below 52w high (negative)
  const dLow = out.indicators.dist_52w_low;     // % above 52w low
  const atrPct = out.indicators.atr != null && out.price ? (out.indicators.atr / out.price) * 100 : null;
  if (ret6 != null && ret6 > 50 && dHigh != null && dHigh <= -10) {
    parts.push(`${t} is a high-momentum name (+${ret6.toFixed(0)}% over 6 months) digesting a big run — ` +
      `pullbacks of this size are routine for it, not necessarily a broken story.`);
  } else if (dHigh != null && dHigh > -8) {
    parts.push(`It is trading within ${Math.abs(dHigh).toFixed(0)}% of its 52-week high — this is strength ` +
      `being bought, not a stock in distress.`);
  } else if (dLow != null && dLow < 12) {
    parts.push(`It sits ${dLow.toFixed(0)}% above its 52-week low — a persistent downtrend / deeply ` +
      `out-of-favor name that needs a real catalyst, so be selective about knife-catching.`);
  } else if (dHigh != null && dHigh < -35) {
    parts.push(`It is ${Math.abs(dHigh).toFixed(0)}% below its 52-week high — a deep drawdown where ` +
      `sentiment, not fundamentals, often sets the price day to day.`);
  }
  if (atrPct != null && atrPct >= 4) {
    parts.push(`Note: this is a high-volatility stock (average daily range ~${atrPct.toFixed(1)}% of price), ` +
      `so a ${day != null ? Math.abs(day).toFixed(0) : "big"}% day is less unusual here than it would be for a mega-cap.`);
  }

  // Trend + cycle.
  const above200 = out.indicators.sma200 != null && out.price > out.indicators.sma200;
  if (out.cycle?.current === "bull" && above200) {
    parts.push(`The primary trend is still up (bullish cycle for ${out.cycle.days_in_phase}d, price above the 200-day) — ` +
      `dips inside an uptrend are typically buyable weakness rather than tops.`);
  } else if (out.cycle?.current === "bear") {
    parts.push(`The primary trend is down (bearish cycle for ${out.cycle.days_in_phase}d) — ` +
      `bounces are counter-trend until the 50-day recrosses the 200-day.`);
  }

  // Historical dip behavior.
  if (out.dip_bounce?.dips >= 3 && out.dip_bounce.win_rate != null) {
    parts.push(`History: ${out.dip_bounce.dips} similar one-day dips resolved higher ` +
      `${(out.dip_bounce.win_rate * 100).toFixed(0)}% of the time (avg ` +
      `${out.dip_bounce.avg_return >= 0 ? "+" : ""}${out.dip_bounce.avg_return}% in 10 sessions).`);
  }

  // Multi-timeframe agreement.
  if (out.mtf?.trend === "up")
    parts.push(`The weekly (higher) timeframe also points up, confirming the daily read.`);
  else if (out.mtf?.trend === "down")
    parts.push(`The weekly timeframe is still down, so any daily strength is counter-trend — treat bounces cautiously.`);

  parts.push(`Net: ${out.recommendation.toLowerCase()} at a technical score of ${out.score}/100.`);
  return parts.join(" ");
}

export default async function handler(req, res) {
  const ticker = String(req.query?.ticker || req.body?.ticker || "").toUpperCase().trim();
  const range = ["6mo", "1y", "2y", "5y"].includes(req.query?.range) ? req.query.range : "1y";
  if (!ticker) return res.status(400).json({ error: "ticker required" });
  try {
    const r = await fetch(CHART(ticker, range), {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" },
    });
    if (!r.ok) return res.status(502).json({ error: `Yahoo returned ${r.status}` });
    const j = await r.json();
    const result = j?.chart?.result?.[0];
    const meta = result?.meta;
    const ts = result?.timestamp || [];
    const q = result?.indicators?.quote?.[0] || {};
    if (!meta || !ts.length || !q.close) return res.status(404).json({ error: "no data" });

    // Drop any null bars so indicators line up.
    const dates = [], o = [], h = [], l = [], c = [], v = [];
    ts.forEach((t, i) => {
      if (q.close[i] == null) return;
      dates.push(new Date(t * 1000).toISOString().slice(0, 10));
      o.push(q.open[i]); h.push(q.high[i]); l.push(q.low[i]); c.push(q.close[i]); v.push(q.volume[i] || 0);
    });
    if (c.length < 30) return res.status(422).json({ error: "insufficient history" });

    const out = analyze(dates, o, h, l, c, v);

    // Market context for the thesis (best-effort; skipped for SPY itself).
    let spyCloses = null;
    if (ticker !== "SPY") {
      try {
        const sr2 = await fetch(CHART("SPY", "3mo"), {
          headers: { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" },
        });
        if (sr2.ok) {
          const sj = await sr2.json();
          spyCloses = (sj?.chart?.result?.[0]?.indicators?.quote?.[0]?.close || []).filter((x) => x != null);
        }
      } catch { /* thesis degrades gracefully */ }
    }
    const thesis = buildThesis(ticker, out, spyCloses);

    // NOTE: day change comes from the last two closes in analyze() —
    // meta.chartPreviousClose is the close before the RANGE start (i.e. the
    // 1y-ago close on a 1y chart), which once showed +82% as a "day" change.
    return res.status(200).json({
      ticker,
      name: meta.shortName || meta.longName || ticker,
      currency: meta.currency || "USD",
      range,
      thesis,
      ...out,
    });
  } catch (e) {
    return res.status(500).json({ error: String(e) });
  }
}
