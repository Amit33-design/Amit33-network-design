// Vercel serverless function: GET /api/peers?ticker=NVDA
// Sector peer comparison — a suggestion means little without knowing whether
// the whole group is doing the same thing. Returns the ticker plus 4 peers
// with 6-month return, RSI, distance from the 52-week high and a trend read,
// so you can see if a name is leading or lagging its own sector.

const CHART = (t, range) =>
  `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(t)}?range=${range}&interval=1d`;
const UA = { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" };

// Curated peer groups: no paid screener needed, and a fixed map is auditable.
// Each list is a genuine competitive set, not just "same sector ETF".
//
// Coverage matters more than elegance here: a name with no group silently got
// NO peer panel at all, which is exactly what happened to the bitcoin miners
// (CIFR, WULF) — the group whose whole story is "the sector moved, not the
// company". When adding a name, put it with who it actually competes with.
const GROUPS = [
  // Semis & AI hardware
  ["NVDA", "AMD", "AVGO", "TSM", "MU", "ARM", "SMCI", "QCOM", "LRCX", "INTC"],
  ["AMAT", "KLAC", "LRCX", "ASML", "TER", "ENTG"],
  ["MRVL", "CRDO", "ALAB", "COHR", "LITE", "CIEN"],
  ["CLS", "FLEX", "JBL", "SANM", "BHE", "PLXS"],
  ["APH", "TEL", "GLW", "LFUS", "VSH"],
  ["SNDK", "MU", "WDC", "STX", "SIMO"],
  // Mega-cap tech
  ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX"],
  ["CRM", "NOW", "SNOW", "PANW", "ADBE", "ORCL", "WDAY"],
  ["PLTR", "AI", "SNOW", "DDOG", "MDB", "CFLT"],
  ["CRWD", "PANW", "ZS", "S", "OKTA", "FTNT"],
  // Bitcoin miners / AI-datacenter converts — CIFR and WULF live here.
  ["WULF", "CIFR", "RIOT", "MARA", "CLSK", "IREN", "CORZ", "HUT", "BITF", "HIVE"],
  ["COIN", "HOOD", "XYZ", "PYPL", "SOFI", "AFRM", "UPST"],
  ["MSTR", "COIN", "MARA", "RIOT", "GLXY"],
  // Power for datacenters — the other side of the AI trade
  ["VST", "CEG", "TLN", "NRG", "PEG", "EXC"],
  ["OKLO", "SMR", "LEU", "CCJ", "UEC", "BWXT"],
  // Energy
  ["XOM", "CVX", "COP", "SLB", "OXY", "EOG", "PSX"],
  ["FSLR", "ENPH", "SEDG", "RUN", "NXT", "ARRY"],
  ["BE", "PLUG", "BLDP", "FCEL"],
  // Mobility
  ["TSLA", "RIVN", "LCID", "F", "GM", "NIO"],
  ["UBER", "LYFT", "DASH", "ABNB"],
  // Aerospace, defense & space
  ["LMT", "RTX", "NOC", "GD", "BA", "LHX"],
  ["RKLB", "ASTS", "LUNR", "PL", "SPCE"],
  ["AXON", "PLTR", "KTOS", "AVAV", "LDOS"],
  // Health
  ["LLY", "UNH", "JNJ", "PFE", "MRK", "ABBV", "BMY"],
  ["VRTX", "REGN", "AMGN", "GILD", "BIIB", "MRNA"],
  ["ISRG", "SYK", "BSX", "MDT", "ZBH", "EW"],
  ["CI", "ELV", "HUM", "CNC", "MOH"],
  // Financials
  ["JPM", "BAC", "GS", "MS", "WFC", "C", "SCHW"],
  ["V", "MA", "AXP", "DFS", "COF"],
  ["BRK-B", "PGR", "ALL", "TRV", "CB", "AIG"],
  // Consumer
  ["WMT", "COST", "TGT", "HD", "LOW", "DG", "DLTR"],
  ["LULU", "NKE", "DECK", "ONON", "UAA", "SKX"],
  ["TPR", "RL", "PVH", "GIII", "CPRI", "VSXY"],
  ["BURL", "ROST", "TJX", "GPS", "ANF"],
  ["SBUX", "CMG", "MCD", "YUM", "DRI", "WING"],
  ["PG", "KO", "PEP", "CL", "KMB", "MDLZ"],
  ["YETI", "SWIM", "HELE", "NWL"],
  // Travel & leisure
  ["CCL", "RCL", "NCLH", "VIK", "LIND"],
  ["DAL", "UAL", "AAL", "LUV", "ALGT", "JBLU"],
  ["MAR", "HLT", "H", "WH", "IHG"],
  // Industrials & materials
  ["CAT", "DE", "URI", "PCAR", "CMI"],
  ["PWR", "DY", "MTZ", "PRIM", "STRL", "AGX"],
  ["FCX", "NEM", "AA", "SCCO", "TECK"],
  ["NUE", "STLD", "CLF", "X", "CMC"],
  ["ALB", "LTHM", "SQM", "MP"],
  ["AAON", "TT", "CARR", "JCI", "LII"],
  ["UPS", "FDX", "XPO", "ODFL", "CHRW", "CVLG"],
  // Media, telecom, real estate
  ["DIS", "CMCSA", "WBD", "PARA", "NFLX"],
  ["T", "VZ", "TMUS", "LUMN"],
  ["AMT", "PLD", "EQIX", "DLR", "SPG", "O"],
  // Homebuilders
  ["DHI", "LEN", "PHM", "NVR", "TOL", "KBH"],
];

// Fallback when a ticker is in no curated group: Yahoo's own sector/industry
// classification, mapped to a representative set. Coarser than a hand-built
// competitive set — an industrial conglomerate and a trucking firm can share
// a sector — so the response labels which kind of group it returned and the
// UI says so. Better a loose comparison, clearly labelled, than none at all.
const SECTOR_PROXIES = {
  Technology: ["MSFT", "NVDA", "AVGO", "CRM", "AMD"],
  "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "TMUS"],
  "Consumer Cyclical": ["AMZN", "HD", "MCD", "NKE", "TJX"],
  "Consumer Defensive": ["WMT", "COST", "PG", "KO", "PEP"],
  Healthcare: ["UNH", "LLY", "JNJ", "ABBV", "MRK"],
  "Financial Services": ["JPM", "BAC", "V", "MA", "GS"],
  Energy: ["XOM", "CVX", "COP", "SLB", "EOG"],
  Industrials: ["CAT", "DE", "UPS", "RTX", "HON"],
  "Basic Materials": ["FCX", "NEM", "NUE", "DOW", "LIN"],
  Utilities: ["NEE", "DUK", "SO", "VST", "CEG"],
  "Real Estate": ["PLD", "AMT", "EQIX", "SPG", "O"],
};

function curatedPeers(ticker, limit = 4) {
  const t = ticker.toUpperCase();
  const group = GROUPS.find((g) => g.includes(t));
  if (!group) return [];
  return group.filter((p) => p !== t).slice(0, limit);
}

/** Yahoo's sector for a ticker, or null. Best-effort: never throws. */
async function sectorOf(ticker) {
  try {
    const url = `https://query1.finance.yahoo.com/v10/finance/quoteSummary/${encodeURIComponent(ticker)}?modules=assetProfile`;
    const r = await fetch(url, { headers: UA });
    if (!r.ok) return null;
    const j = await r.json();
    return j?.quoteSummary?.result?.[0]?.assetProfile?.sector || null;
  } catch {
    return null;
  }
}

/** Peers plus how they were chosen, so the UI can be honest about it. */
async function peersFor(ticker, limit = 4) {
  const curated = curatedPeers(ticker, limit);
  if (curated.length) return { peers: curated, basis: "competitors", sector: null };

  const sector = await sectorOf(ticker);
  const proxy = (SECTOR_PROXIES[sector] || [])
    .filter((p) => p !== ticker.toUpperCase())
    .slice(0, limit);
  if (proxy.length) return { peers: proxy, basis: "sector", sector };
  return { peers: [], basis: "none", sector };
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

  const { peers, basis, sector } = await peersFor(ticker);
  if (!peers.length) {
    return res.status(200).json({
      ticker, peers: [], subject: null, basis,
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
  return res.status(200).json({
    ticker, subject, peers: others, standing, basis, sector,
    // Say where the comparison set came from — a curated competitive group is
    // a much stronger read than "same sector as the mega-caps".
    basis_note: basis === "competitors"
      ? "Direct competitors"
      : `Same sector (${sector}) — a broad comparison, not direct competitors`,
  });
}
