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

  // Score 0-100 from trend + RSI + momentum + 52w position.
  let score = 50;
  const factors = [];
  if (s200 != null) {
    if (last > s200) { score += 12; factors.push("above 200-day avg (uptrend)"); }
    else { score -= 8; factors.push("below 200-day avg (downtrend)"); }
  }
  if (s50 != null && s200 != null && s50 > s200) { score += 6; factors.push("50/200 golden cross"); }
  if (r != null) {
    if (r < 30) { score += 8; factors.push(`oversold (RSI ${r.toFixed(0)})`); }
    else if (r > 70) { score -= 8; factors.push(`overbought (RSI ${r.toFixed(0)})`); }
  }
  if (mom6 != null) {
    if (mom6 > 0) { score += 8; factors.push(`+${mom6.toFixed(0)}% over 6mo`); }
    else { score -= 6; factors.push(`${mom6.toFixed(0)}% over 6mo`); }
  }
  if (distHigh != null) {
    if (distHigh > -10) { score += 6; factors.push("near 52-week high"); }
    else if (distHigh < -50) { score -= 6; factors.push("deep below 52-week high"); }
  }
  score = Math.max(0, Math.min(100, score));
  const rec =
    score >= 70 ? "Buy" : score >= 58 ? "Accumulate" : score >= 45 ? "Hold" : score >= 32 ? "Reduce" : "Sell";
  return { score: Math.round(score), recommendation: rec, rsi: r != null ? Math.round(r) : null,
           momentum_6mo_%: mom6 != null ? Math.round(mom6 * 10) / 10 : null,
           dist_52w_high_%: distHigh != null ? Math.round(distHigh * 10) / 10 : null,
           factors };
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
