// Vercel serverless function: GET /api/peers?ticker=NVDA
// Sector peer comparison — a suggestion means little without knowing whether
// the whole group is doing the same thing. Returns the ticker plus 4 peers
// with 6-month return, RSI, distance from the 52-week high and a trend read,
// so you can see if a name is leading or lagging its own sector.

const CHART = (t, range) =>
  `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(t)}?range=${range}&interval=1d`;
const UA = { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" };

// Static peer groups: no paid screener needed, and a fixed map is auditable.
// Each list is a genuine competitive set, not just "same sector ETF".
const GROUPS = [
  ["NVDA", "AMD", "AVGO", "TSM", "MU", "ARM", "SMCI", "QCOM", "LRCX", "INTC"],
  ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX"],
  ["CRM", "NOW", "SNOW", "PANW", "ADBE", "ORCL", "WDAY"],
  ["XOM", "CVX", "COP", "SLB", "OXY"],
  ["FSLR", "ENPH", "SEDG", "RUN"],
  ["TSLA", "RIVN", "LCID", "F", "GM"],
  ["COIN", "HOOD", "XYZ", "PYPL", "SOFI"],
  ["LLY", "UNH", "JNJ", "PFE", "MRK", "ABBV"],
  ["LMT", "RTX", "NOC", "GD", "BA"],
  ["WMT", "COST", "TGT", "HD", "LOW"],
  ["JPM", "BAC", "GS", "MS", "WFC"],
  ["PLTR", "AI", "SNOW", "DDOG", "MDB"],
];

function peersFor(ticker, limit = 4) {
  const t = ticker.toUpperCase();
  const group = GROUPS.find((g) => g.includes(t));
  if (!group) return [];
  return group.filter((p) => p !== t).slice(0, limit);
}

const rsiLast = (c, period = 14) => {
  if (c.length < period + 1) return null;
  let ag = 0, al = 0;
  for (let i = c.length - period; i < c.length; i++) {
    const d = c[i] - c[i - 1];
    if (d >= 0) ag += d; else al -= d;
  }
  ag /= period; al /= period;
  return al === 0 ? 100 : 100 - 100 / (1 + ag / al);
};
const smaLast = (a, n) => (a.length < n ? null : a.slice(-n).reduce((x, y) => x + y, 0) / n);
const r1 = (x) => (x == null ? null : Math.round(x * 10) / 10);

async function metricsFor(ticker) {
  try {
    const r = await fetch(CHART(ticker, "1y"), { headers: UA });
    if (!r.ok) return null;
    const j = await r.json();
    const res = j?.chart?.result?.[0];
    const c = (res?.indicators?.quote?.[0]?.close || []).filter((x) => x != null);
    if (c.length < 30) return null;
    const last = c[c.length - 1];
    const ret = (n) => (c.length > n ? ((last - c[c.length - 1 - n]) / c[c.length - 1 - n]) * 100 : null);
    const hi52 = Math.max(...c.slice(-252));
    const s200 = smaLast(c, 200);
    return {
      ticker,
      name: res.meta?.shortName || ticker,
      price: Math.round(last * 100) / 100,
      day_change_pct: r1(ret(1)),
      ret_1m: r1(ret(21)),
      ret_6m: r1(ret(126)),
      rsi: r1(rsiLast(c)),
      from_52w_high: hi52 ? r1(((last - hi52) / hi52) * 100) : null,
      trend: s200 == null ? "unknown" : last > s200 ? "up" : "down",
    };
  } catch {
    return null;
  }
}

export default async function handler(req, res) {
  const ticker = String(req.query?.ticker || "").toUpperCase().trim();
  if (!ticker) return res.status(400).json({ error: "ticker required" });

  const peers = peersFor(ticker);
  if (!peers.length) {
    return res.status(200).json({
      ticker, peers: [], subject: null,
      note: "No peer group mapped for this ticker yet.",
    });
  }

  const rows = (await Promise.all([ticker, ...peers].map(metricsFor))).filter(Boolean);
  const subject = rows.find((r) => r.ticker === ticker) || null;
  const others = rows.filter((r) => r.ticker !== ticker);

  // Rank the subject within its group on 6-month return — the single clearest
  // "is this the leader or the laggard?" read.
  let standing = null;
  if (subject && others.length && subject.ret_6m != null) {
    const scored = rows.filter((r) => r.ret_6m != null)
                       .sort((a, b) => b.ret_6m - a.ret_6m);
    const rank = scored.findIndex((r) => r.ticker === ticker) + 1;
    const median = scored[Math.floor(scored.length / 2)]?.ret_6m ?? 0;
    standing = {
      rank, of: scored.length,
      vs_peer_median_pp: r1(subject.ret_6m - median),
      verdict: rank === 1 ? "sector leader"
        : rank <= Math.ceil(scored.length / 2) ? "above peer median"
        : "lagging its peers",
    };
  }

  res.setHeader("Cache-Control", "s-maxage=600, stale-while-revalidate=1200");
  return res.status(200).json({ ticker, subject, peers: others, standing });
}
