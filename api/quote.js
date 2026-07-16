// Vercel serverless function: POST /api/quote  { tickers: ["AAPL", ...] }
// Returns a live price AND an on-the-go technical recommendation for ANY ticker
// (the static frontend can't fetch market data itself). Uses Yahoo Finance's
// open v8 chart endpoint server-side (no auth/crumb needed) and computes a
// trend/RSI/momentum-based Buy/Hold/Sell so portfolio holdings that weren't in
// the latest scan still get a signal.

const CHART = (t) =>
  `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(
    t
  )}?range=1y&interval=1d`;

function sma(arr, n) {
  if (arr.length < n) return null;
  const s = arr.slice(-n).reduce((a, b) => a + b, 0);
  return s / n;
}

function rsi(closes, period = 14) {
  if (closes.length < period + 1) return null;
  let gain = 0;
  let loss = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    if (d >= 0) gain += d;
    else loss -= d;
  }
  const ag = gain / period;
  const al = loss / period;
  if (al === 0) return 100;
  const rs = ag / al;
  return 100 - 100 / (1 + rs);
}

function technicals(closes) {
  const last = closes[closes.length - 1];
  const s50 = sma(closes, 50);
  const s200 = sma(closes, 200);
  const r = rsi(closes);
  const sixMoAgo = closes.length >= 127 ? closes[closes.length - 127] : closes[0];
  const mom6 = sixMoAgo ? ((last - sixMoAgo) / sixMoAgo) * 100 : null;
  const hi52 = Math.max(...closes.slice(-252));
  const distHigh = hi52 ? ((last - hi52) / hi52) * 100 : null;

  // Two-layer verdict: the LONG-TERM trend decides the Buy/Hold/Sell class
  // (200-day, 50/200 regime, 6-month structure); short-term RSI only tunes
  // the entry within it. A red week can't flip an uptrend name to Sell, and
  // a one-week bounce can't make a downtrend name a Buy.
  let lt = 50;
  const factors = [];
  if (s200 != null) {
    if (last > s200) { lt += 15; factors.push("above 200-day avg (long-term uptrend)"); }
    else { lt -= 15; factors.push("below 200-day avg (long-term downtrend)"); }
  }
  if (s50 != null && s200 != null) {
    if (s50 > s200) { lt += 9; factors.push("50/200 golden cross"); }
    else { lt -= 9; factors.push("50/200 death cross"); }
  }
  if (mom6 != null) {
    if (mom6 > 10) { lt += 7; factors.push(`+${mom6.toFixed(0)}% over 6mo`); }
    else if (mom6 < -10) { lt -= 7; factors.push(`${mom6.toFixed(0)}% over 6mo`); }
  }
  if (distHigh != null && distHigh > -12 && (s200 == null || last > s200)) {
    lt += 4; factors.push("consolidating near 52-week high");
  }
  lt = Math.max(0, Math.min(100, lt));
  const ltDir = lt >= 60 ? "up" : lt <= 40 ? "down" : "mixed";

  let st = 50;
  if (r != null) {
    if (r < 35 && ltDir === "up") { st += 15; factors.push(`oversold dip (RSI ${r.toFixed(0)}) in an uptrend — entry, not exit`); }
    else if (r < 35 && ltDir === "down") { st -= 4; factors.push(`oversold (RSI ${r.toFixed(0)}) but trend is down — falling knife`); }
    else if (r > 70) { st -= 10; factors.push(`extended (RSI ${r.toFixed(0)}) — wait for a pullback`); }
  }
  st = Math.max(0, Math.min(100, st));

  let rec;
  if (ltDir === "up") rec = st >= 55 ? "Buy" : st >= 40 ? "Accumulate" : "Hold";
  else if (ltDir === "down") rec = st < 40 ? "Sell" : "Reduce";
  else rec = st >= 60 ? "Accumulate" : st >= 35 ? "Hold" : "Reduce";
  const score = Math.round(0.7 * lt + 0.3 * st);
  const reason = factors.length
    ? `${rec} — long-term trend ${ltDir.toUpperCase()} (${Math.round(lt)}/100), timing ${Math.round(st)}/100: ${factors.slice(0, 4).join("; ")}`
    : `${rec} — long-term trend ${ltDir.toUpperCase()}`;
  return {
    score: Math.round(score),
    recommendation: rec,
    reason,
    rsi: r != null ? Math.round(r) : null,
    momentum_6mo: mom6 != null ? Math.round(mom6 * 10) / 10 : null,
    dist_52w_high: distHigh != null ? Math.round(distHigh * 10) / 10 : null,
    factors,
  };
}

async function quoteOne(ticker) {
  try {
    const r = await fetch(CHART(ticker), {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" },
    });
    if (!r.ok) return [ticker, null];
    const j = await r.json();
    const result = j?.chart?.result?.[0];
    const meta = result?.meta;
    if (!meta || meta.regularMarketPrice == null) return [ticker, null];
    const price = meta.regularMarketPrice;
    const prev = meta.chartPreviousClose ?? meta.previousClose ?? null;
    const closes = (result?.indicators?.quote?.[0]?.close || []).filter((x) => x != null);
    const tech = closes.length > 30 ? technicals([...closes, price]) : {};
    return [
      ticker,
      {
        price,
        currency: meta.currency || "USD",
        name: meta.shortName || meta.longName || ticker,
        day_change_pct: prev ? ((price - prev) / prev) * 100 : null,
        ...tech,
      },
    ];
  } catch {
    return [ticker, null];
  }
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed" });
  }
  let tickers = [];
  try {
    tickers = (req.body?.tickers || []).map((t) => String(t).toUpperCase().trim()).filter(Boolean);
  } catch {
    tickers = [];
  }
  tickers = Array.from(new Set(tickers)).slice(0, 40);
  if (!tickers.length) return res.status(200).json({ quotes: {} });

  const entries = await Promise.all(tickers.map(quoteOne));
  const quotes = Object.fromEntries(entries.filter(([, v]) => v));
  return res.status(200).json({ quotes });
}
