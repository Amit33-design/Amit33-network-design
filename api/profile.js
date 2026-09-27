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

import { fetchClassification } from "./_story.js";

const UA = { "User-Agent": "alphahunter-ai/1.0 (https://amit33-network-design.vercel.app)" };
const TICKER_RE = /^[A-Z]{1,6}([.-][A-Z]{1,2})?$/;
const WIKI_SEARCH = (q) =>
  `https://en.wikipedia.org/w/rest.php/v1/search/page?q=${encodeURIComponent(q)}&limit=3`;
const WIKI_SUMMARY = (key) =>
  `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(key)}`;

const COMPANY_WORDS = /\b(company|corporation|conglomerate|manufacturer|maker|producer|provider|operator|retailer|bank|insurer|holding|firm|developer|supplier|chain|group|trust|utility|airline|brand|multinational|business)\b/i;
const SUFFIX = /[,.]?\s+(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|holdings?|group|s\.a|n\.v|ag|se|lp|l\.p)\.?$/i;

/** The distinctive part of a company name: "NVIDIA Corporation" -> "nvidia". */
export function coreName(name) {
  let n = String(name || "").trim();
  for (let i = 0; i < 3; i++) n = n.replace(SUFFIX, "").trim();
  return n.toLowerCase();
}

/** Is this Wikipedia summary about THIS company? Pure, so it is tested. A
 *  same-named page about a person, place or product would be worse than no
 *  summary at all, so both the name and "this is a business" must match. */
export function wikiMatches(name, page) {
  const core = coreName(name);
  if (!core || !page?.extract) return false;
  const text = `${page.title || ""} ${page.description || ""} ${page.extract}`.toLowerCase();
  const firstWord = core.split(/\s+/)[0];
  if (firstWord.length < 3 || !text.includes(firstWord)) return false;
  return COMPANY_WORDS.test(`${page.description || ""} ${page.extract.slice(0, 400)}`);
}

/** First two or three sentences, up to ~500 chars. */
export function trimSummary(text, max = 500) {
  const t = String(text || "").replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  const cut = t.slice(0, max);
  const stop = cut.lastIndexOf(". ");
  return stop > max * 0.4 ? cut.slice(0, stop + 1) : cut.replace(/\s+\S*$/, "") + " …";
}

async function wikipediaSummary(name) {
  const r = await fetch(WIKI_SEARCH(name), { headers: UA });
  if (!r.ok) return null;
  const pages = (await r.json())?.pages || [];
  for (const p of pages.slice(0, 3)) {
    const s = await fetch(WIKI_SUMMARY(p.key), { headers: UA });
    if (!s.ok) continue;
    const page = await s.json();
    if (page?.type === "disambiguation") continue;
    if (wikiMatches(name, page)) {
      return { summary: trimSummary(page.extract), url: page?.content_urls?.desktop?.page || null };
    }
  }
  return null;
}

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
    const cls = await fetchClassification(ticker);
    if (!cls) {
      return res.status(404).json({
        code: "ticker_not_found", ticker,
        message: `No company information found for '${ticker}'.` });
    }
    // profiles.json (generated in CI) carries Yahoo's business summary but
    // not for every ticker. Without a fallback, most symbols showed only a
    // sector badge — "no details about what the stock does". Wikipedia's
    // summary is crumb-free; wikiMatches() guards against the wrong page.
    const wiki = req.query?.summary === "0" ? null
      : await wikipediaSummary(cls.name).catch(() => null);

    res.setHeader("Cache-Control", "s-maxage=86400, stale-while-revalidate=604800");
    return res.status(200).json({
      ticker, ...cls,
      summary: wiki?.summary || null,
      summary_source: wiki ? "wikipedia" : null,
      summary_url: wiki?.url || null,
      source: "yahoo-search",
    });
  } catch (e) {
    console.error(`[profile] ${ticker}:`, e);
    if (e?.upstream) {
      return res.status(502).json({
        code: "data_unavailable",
        message: "Company data is temporarily unavailable." });
    }
    return res.status(500).json({
      code: "profile_failed",
      message: "Couldn't load company information." });
  }
}
