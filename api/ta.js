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

// "Potential bottom" detector: how many classic bottoming tells are firing?
// Combines oversold RSI, bullish RSI divergence (price lower-low but RSI
// higher-low), proximity to 52-week low / support, capitulation-volume + a
// long-lower-wick reversal candle, and a short-term MA reclaim.
function bottomSignal(o, h, l, c, v, rsis, e20, sr) {
  const n = c.length;
  const last = c[n - 1];
  let score = 0;
  const factors = [];

  const rsi = rsis[n - 1];
  if (rsi != null && rsi < 30) { score += 25; factors.push({ t: "bull", s: `deeply oversold (RSI ${rsi.toFixed(0)})` }); }
  else if (rsi != null && rsi < 40) { score += 12; factors.push({ t: "bull", s: `oversold (RSI ${rsi.toFixed(0)})` }); }

  // Bullish RSI divergence over the last ~20 sessions.
  const w = Math.min(20, n - 1);
  const pMinIdx = c.lastIndexOf(Math.min(...c.slice(-w)));
  const prevMinIdx = c.slice(0, n - Math.floor(w / 2)).lastIndexOf(Math.min(...c.slice(-2 * w, -Math.floor(w / 2))));
  if (pMinIdx > prevMinIdx && prevMinIdx >= 0 && c[pMinIdx] < c[prevMinIdx] && rsis[pMinIdx] != null && rsis[prevMinIdx] != null && rsis[pMinIdx] > rsis[prevMinIdx]) {
    score += 22; factors.push({ t: "bull", s: "bullish RSI divergence (price lower low, RSI higher low)" });
  }

  // Near the 52-week low or a support level.
  const lo52 = Math.min(...c.slice(-252));
  if (lo52 && (last - lo52) / lo52 < 0.08) { score += 15; factors.push({ t: "bull", s: "at/near 52-week low" }); }
  const supp = (sr.support || [])[0];
  if (supp && Math.abs(last - supp) / last < 0.04) { score += 10; factors.push({ t: "bull", s: `testing support ~$${supp}` }); }

  // Capitulation volume + reversal (long lower wick) candle in last 3 days.
  const avgV = v.slice(-20).reduce((a, b) => a + b, 0) / Math.min(20, v.length);
  for (let i = n - 3; i < n; i++) {
    if (i < 1) continue;
    const body = Math.abs(c[i] - o[i]);
    const lowerWick = Math.min(o[i], c[i]) - l[i];
    if (v[i] > 1.8 * avgV && lowerWick > 1.5 * body && c[i] >= o[i]) {
      score += 16; factors.push({ t: "bull", s: "capitulation volume + hammer reversal candle" });
      break;
    }
  }

  // Short-term reclaim: back above the 20-day EMA after being below it.
  if (e20[n - 1] != null && e20[n - 2] != null && c[n - 2] < e20[n - 2] && last > e20[n - 1]) {
    score += 12; factors.push({ t: "bull", s: "reclaimed 20-day EMA" });
  }

  score = Math.min(100, score);
  const label = score >= 60 ? "high" : score >= 35 ? "possible" : "low";
  return { score, likelihood: label, factors };
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

  let score = 50;
  const factors = [];
  if (s200 != null) {
    if (last > s200) { score += 12; factors.push({ t: "bull", s: "Price above 200-day SMA (primary uptrend)" }); }
    else { score -= 10; factors.push({ t: "bear", s: "Price below 200-day SMA (primary downtrend)" }); }
  }
  if (s50 != null && s200 != null) {
    if (s50 > s200) { score += 6; factors.push({ t: "bull", s: "50-day above 200-day (golden-cross regime)" }); }
    else { score -= 4; factors.push({ t: "bear", s: "50-day below 200-day (death-cross regime)" }); }
  }
  if (rsi != null) {
    if (rsi < 30) { score += 8; factors.push({ t: "bull", s: `Oversold (RSI ${rsi.toFixed(0)}) — bounce setup` }); }
    else if (rsi > 70) { score -= 8; factors.push({ t: "bear", s: `Overbought (RSI ${rsi.toFixed(0)})` }); }
    else factors.push({ t: "neutral", s: `RSI ${rsi.toFixed(0)} (neutral)` });
  }
  if (m.hist != null) {
    if (m.hist > 0) { score += 6; factors.push({ t: "bull", s: "MACD above signal (momentum up)" }); }
    else { score -= 6; factors.push({ t: "bear", s: "MACD below signal (momentum down)" }); }
  }
  const r6 = ret(126);
  if (r6 != null) {
    if (r6 > 0) { score += 6; factors.push({ t: "bull", s: `+${r6.toFixed(0)}% over 6 months` }); }
    else { score -= 5; factors.push({ t: "bear", s: `${r6.toFixed(0)}% over 6 months` }); }
  }
  if (distHigh != null && distHigh > -10) { score += 5; factors.push({ t: "bull", s: "Within 10% of 52-week high" }); }
  if (distLow != null && distLow < 8) { score += 4; factors.push({ t: "bull", s: "Near 52-week low (deep value/oversold)" }); }
  if (cyc.current === "bull") { score += 4; factors.push({ t: "bull", s: `Bullish cycle (${cyc.days_in_phase}d)` }); }
  else if (cyc.current === "bear") { score -= 4; factors.push({ t: "bear", s: `Bearish cycle (${cyc.days_in_phase}d)` }); }
  score = Math.max(0, Math.min(100, Math.round(score)));
  const recommendation =
    score >= 70 ? "Buy" : score >= 58 ? "Accumulate" : score >= 45 ? "Hold" : score >= 32 ? "Reduce" : "Sell";

  return {
    price: last,
    score,
    recommendation,
    factors,
    cycle: cyc,
    levels: sr,
    signals: sigs,
    csp_signal: csp,
    dip_bounce: bounce,
    bottom: bottom,
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
    return res.status(200).json({
      ticker,
      name: meta.shortName || meta.longName || ticker,
      currency: meta.currency || "USD",
      range,
      day_change_pct: meta.chartPreviousClose
        ? ((out.price - meta.chartPreviousClose) / meta.chartPreviousClose) * 100
        : null,
      ...out,
    });
  } catch (e) {
    return res.status(500).json({ error: String(e) });
  }
}
