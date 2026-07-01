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

function macd(closes) {
  const e12 = ema(closes, 12), e26 = ema(closes, 26);
  const line = closes.map((_, i) => (e12[i] != null && e26[i] != null ? e12[i] - e26[i] : null));
  const valid = line.filter((x) => x != null);
  const sig = ema(valid, 9);
  // align signal back to full length
  const pad = line.length - valid.length;
  const signal = line.map((_, i) => (i >= pad ? sig[i - pad] : null));
  const last = line.length - 1;
  return {
    macd: line[last], signal: signal[last],
    hist: line[last] != null && signal[last] != null ? line[last] - signal[last] : null,
  };
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
  const m = macd(c);
  const s50 = smaLast(c, 50), s200 = smaLast(c, 200);
  const a = atr(h, l, c);
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
  score = Math.max(0, Math.min(100, Math.round(score)));
  const recommendation =
    score >= 70 ? "Buy" : score >= 58 ? "Accumulate" : score >= 45 ? "Hold" : score >= 32 ? "Reduce" : "Sell";

  return {
    price: last,
    score,
    recommendation,
    factors,
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
      close: c.map((x) => Math.round(x * 100) / 100),
      volume: v,
      ema20: e20, ema50: e50, ema200: e200,
      rsi: rsis.map((x) => (x != null ? Math.round(x * 10) / 10 : null)),
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
