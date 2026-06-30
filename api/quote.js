// Vercel serverless function: POST /api/quote  { tickers: ["AAPL", ...] }
// Returns live prices so the Portfolio Analyzer works on the go for ANY ticker
// (the static frontend can't fetch market data itself). Uses Yahoo Finance's
// open v8 chart endpoint server-side, where outbound internet is available.

const CHART = (t) =>
  `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(
    t
  )}?range=1d&interval=1d`;

async function quoteOne(ticker) {
  try {
    const r = await fetch(CHART(ticker), {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" },
    });
    if (!r.ok) return [ticker, null];
    const j = await r.json();
    const meta = j?.chart?.result?.[0]?.meta;
    if (!meta || meta.regularMarketPrice == null) return [ticker, null];
    const price = meta.regularMarketPrice;
    const prev = meta.chartPreviousClose ?? meta.previousClose ?? null;
    return [
      ticker,
      {
        price,
        currency: meta.currency || "USD",
        name: meta.shortName || meta.longName || ticker,
        day_change_pct: prev ? ((price - prev) / prev) * 100 : null,
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
  // Cap to keep the function fast and within rate limits.
  tickers = Array.from(new Set(tickers)).slice(0, 40);
  if (!tickers.length) return res.status(200).json({ quotes: {} });

  const entries = await Promise.all(tickers.map(quoteOne));
  const quotes = Object.fromEntries(entries.filter(([, v]) => v));
  return res.status(200).json({ quotes });
}
