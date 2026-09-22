// Vercel serverless function: GET /api/profile?ticker=AAPL
//
// What the company does and which segment it is in, for ANY ticker, live.
//
// The static profiles.json generated in CI carries the long business summary
// (that needs a crumb, so only yfinance in Actions can fetch it). But relying
// on it alone meant the panel showed NOTHING until a cron had run, and nothing
// at all for a ticker outside the generated set — which is most of them. A
// feature that silently renders nothing is indistinguishable from one that was
// never built.
//
// Yahoo's search endpoint is crumb-free and returns the classification fields,
// so sector/industry/name are always available even when the summary is not.

const SEARCH = (t) =>
  `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(t)}` +
  `&quotesCount=6&newsCount=0&listsCount=0`;
const UA = { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" };
const TICKER_RE = /^[A-Z]{1,6}([.-][A-Z]{1,2})?$/;

export default async function handler(req, res) {
  const ticker = String(req.query?.ticker || "").toUpperCase().trim();
  if (!ticker) {
    return res.status(400).json({ code: "ticker_required",
                                  message: "Enter a ticker symbol." });
  }
  if (!TICKER_RE.test(ticker)) {
    return res.status(422).json({
      code: "invalid_ticker", ticker,
      message: `'${ticker}' isn't a valid ticker symbol.` });
  }

  try {
    const r = await fetch(SEARCH(ticker), { headers: UA });
    if (!r.ok) {
      console.error(`[profile] upstream ${r.status} for ${ticker}`);
      return res.status(502).json({
        code: "data_unavailable",
        message: "Company data is temporarily unavailable." });
    }
    const j = await r.json();
    const quotes = Array.isArray(j?.quotes) ? j.quotes : [];
    // Search is fuzzy, so take the exact symbol match rather than the first
    // result — querying "ARM" otherwise happily returns a different company.
    const q = quotes.find((x) => String(x?.symbol || "").toUpperCase() === ticker)
      || quotes.find((x) => x?.quoteType === "EQUITY")
      || null;

    if (!q) {
      return res.status(404).json({
        code: "ticker_not_found", ticker,
        message: `No company information found for '${ticker}'.` });
    }

    res.setHeader("Cache-Control", "s-maxage=86400, stale-while-revalidate=604800");
    return res.status(200).json({
      ticker,
      name: q.longname || q.shortname || ticker,
      sector: q.sector || q.sectorDisp || null,
      industry: q.industry || q.industryDisp || null,
      exchange: q.exchDisp || null,
      type: q.typeDisp || q.quoteType || null,
      // The summary is not in this endpoint; profiles.json supplies it when
      // available. Saying so beats implying the field is simply empty.
      summary: null,
      source: "yahoo-search",
    });
  } catch (e) {
    console.error(`[profile] ${ticker}:`, e);
    return res.status(500).json({
      code: "profile_failed",
      message: "Couldn't load company information." });
  }
}
