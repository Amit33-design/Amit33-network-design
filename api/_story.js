// The investment story for one ticker: what kind of business it is, what
// drives it, how the market currently feels about its group, and whether that
// story agrees with the chart.
//
// "Why" (in ta.js) explains the technical verdict. This is the other half —
// the part that makes NVDA's thesis different from XOM's. Structural context
// comes from _themes.js; sentiment is MEASURED from the theme's ETF, SPY and
// the VIX, never written by hand. `buildStory` is pure and unit-tested;
// `fetchStoryInputs` is the only part that touches the network.
import { resolveTheme } from "./_themes.js";

const UA = { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" };
const CHART = (t, range) =>
  `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(t)}?range=${range}&interval=1d`;
const SEARCH = (t) =>
  `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(t)}` +
  `&quotesCount=6&newsCount=0&listsCount=0`;

const pct = (c, n) => (c && c.length > n && c[c.length - 1 - n]
  ? ((c[c.length - 1] - c[c.length - 1 - n]) / c[c.length - 1 - n]) * 100 : null);
const sma = (c, n) => (c && c.length >= n ? c.slice(-n).reduce((a, b) => a + b, 0) / n : null);
const r1 = (x) => (x == null ? null : Math.round(x * 10) / 10);
const sgn = (x) => `${x >= 0 ? "+" : ""}${x.toFixed(0)}%`;

/** Sector/industry from Yahoo's crumb-free search. Exact symbol match only —
 *  search is fuzzy and "ARM" otherwise returns another company. */
export async function fetchClassification(ticker) {
  const r = await fetch(SEARCH(ticker), { headers: UA });
  // An outage is not "no such company": callers must be able to tell them apart.
  if (!r.ok) throw Object.assign(new Error(`search ${r.status}`), { upstream: true });
  const j = await r.json();
  const quotes = Array.isArray(j?.quotes) ? j.quotes : [];
  const q = quotes.find((x) => String(x?.symbol || "").toUpperCase() === ticker) || null;
  if (!q) return null;
  return {
    name: q.longname || q.shortname || ticker,
    sector: q.sector || q.sectorDisp || null,
    industry: q.industry || q.industryDisp || null,
    exchange: q.exchDisp || null,
    type: q.typeDisp || q.quoteType || null,
  };
}

async function closes(ticker, range) {
  try {
    const r = await fetch(CHART(ticker, range), { headers: UA });
    if (!r.ok) return null;
    const j = await r.json();
    const c = j?.chart?.result?.[0]?.indicators?.quote?.[0]?.close;
    return Array.isArray(c) ? c.filter((x) => x != null) : null;
  } catch { return null; }
}

/** Everything buildStory needs beyond the stock's own closes. Best-effort:
 *  each piece may come back null and the story simply says less. */
export function fetchSpy() { return closes("SPY", "1y"); }

/** This deployment's own origin, for reading its static files. */
export function originOf(req) {
  const host = req?.headers?.["x-forwarded-host"] || req?.headers?.host;
  return host ? `https://${host}` : null;
}

// themes.json is a static file on this same deployment, rebuilt daily in CI
// (backend/theme_pulse.py). Warm function instances keep it for 10 minutes.
let themesCache = { at: 0, data: null };
async function themePulse(origin) {
  if (!origin) return null;
  if (themesCache.data && Date.now() - themesCache.at < 600_000) return themesCache.data;
  try {
    const r = await fetch(`${origin}/themes.json`);
    if (!r.ok) return null;
    themesCache = { at: Date.now(), data: await r.json() };
    return themesCache.data;
  } catch { return null; }
}

export async function fetchStoryInputs(ticker, spyPromise, origin) {
  const vixP = closes("^VIX", "5d");
  const pulseP = themePulse(origin);
  const cls = await fetchClassification(ticker).catch(() => null);
  const theme = resolveTheme(ticker, cls?.sector, cls?.industry);
  const etf = theme?.etf && theme.etf !== ticker ? theme.etf : null;
  const [etfCloses, vix, spy] = await Promise.all([
    etf ? closes(etf, "6mo") : null,
    vixP,
    Promise.resolve(spyPromise).then((x) => x || null).catch(() => null),
  ]);
  const pulse = await pulseP;
  const entry = pulse?.themes?.find((x) => x.key === theme?.key);
  return {
    classification: cls, theme, etfCloses, vix: vix?.length ? vix[vix.length - 1] : null, spyCloses: spy,
    basket: entry?.basket ? { ...entry.basket, as_of: pulse.generated?.slice(0, 10) || null } : null,
  };
}

/** Pure: the story from already-fetched inputs. */
export function buildStory({ ticker, closes: c, indicators = {}, price, recommendation,
                             classification, theme, etfCloses, spyCloses, vix, basket = null }) {
  const ind = indicators;
  const atrPct = ind.atr != null && price ? (ind.atr / price) * 100 : null;
  const growth = theme?.growth || null;

  // ---- What kind of stock is this? (market cap is added by the UI, which
  // has it from the profile; everything else is known here.)
  const traits = [];
  let style;
  const ret6 = ind.ret_6m, dHigh = ind.dist_52w_high;
  if (growth === "speculative") style = "Speculative / early-stage";
  else if (growth === "secular" && ret6 != null && ret6 > 30 && (dHigh ?? -100) > -15) style = "Secular-growth leader";
  else if (growth === "secular" && dHigh != null && dHigh < -30) style = "Secular grower in a deep pullback";
  else if (growth === "secular") style = "Secular growth";
  else if (growth === "defensive") style = "Defensive / income";
  else if (growth === "cyclical") style = dHigh != null && dHigh < -35 ? "Cyclical, out of favour" : "Cyclical";
  else style = "Unclassified";
  if (atrPct != null) traits.push(atrPct >= 4 ? `high volatility (~${atrPct.toFixed(1)}%/day)`
    : atrPct <= 1.8 ? `low volatility (~${atrPct.toFixed(1)}%/day)` : `moderate volatility (~${atrPct.toFixed(1)}%/day)`);
  if (ret6 != null) traits.push(`${sgn(ret6)} over 6 months`);
  if (dHigh != null) traits.push(dHigh > -3 ? "at its 52-week high" : `${Math.abs(dHigh).toFixed(0)}% below its 52-week high`);

  // ---- Measured sentiment: the group vs the market, the stock vs its group.
  const s1 = pct(c, 21), s3 = pct(c, 63);
  const m1 = pct(spyCloses, 21), m3 = pct(spyCloses, 63);
  // The group is the theme's own equal-weight basket when CI has built one:
  // an ETF is often the wrong group (AI power vs XLU, mostly regulated
  // utilities). Its spread vs SPY is taken from the same bars the basket was
  // measured on, never mixed with today's live SPY.
  const useBasket = basket && basket.n >= 4 && basket.ret_3m != null && basket.vs_spy_3m != null;
  const e1 = useBasket ? basket.ret_1m : pct(etfCloses, 21);
  const e3 = useBasket ? basket.ret_3m : pct(etfCloses, 63);
  const g3 = useBasket ? basket.ret_3m - basket.vs_spy_3m : m3;
  const reads = [];
  let groupTone = 0, stockTone = 0;
  const etf = theme?.etf;
  if (e3 != null && g3 != null) {
    const d = e3 - g3;
    groupTone = d >= 5 ? 1 : d <= -5 ? -1 : 0;
    const who = useBasket
      ? `${theme.name} (${basket.n} stocks, equal-weight)`
      : `${theme.name} (${etf})`;
    const breadth = useBasket && basket.breadth_50d != null
      ? ` ${Math.round(basket.breadth_50d * 100)}% of them are above their 50-day — ` +
        (basket.breadth_50d >= 0.65 ? "a broad move." : basket.breadth_50d <= 0.35 ? "most are in short-term downtrends." : "a mixed picture underneath.")
      : "";
    reads.push({
      tone: groupTone,
      text: `${who} is ${sgn(e3)} over 3 months vs the S&P 500 ${sgn(g3)} — ` +
        (groupTone > 0 ? "money is flowing INTO this group."
          : groupTone < 0 ? "the market is rotating OUT of this group."
          : "in line with the market; no strong view on the group.") + breadth,
    });
  }
  if (s1 != null && e1 != null && (useBasket || (etf && etf !== ticker))) {
    const d = s1 - e1;
    stockTone = d >= 5 ? 1 : d <= -5 ? -1 : 0;
    reads.push({
      tone: stockTone,
      text: `${ticker} is ${sgn(s1)} this month vs its group ${sgn(e1)} — ` +
        (stockTone > 0 ? "leading its peers, so buyers are singling it out."
          : stockTone < 0 ? (groupTone >= 0
            ? "lagging peers while the group holds up, which points to something company-specific."
            : "lagging an already weak group.")
          : "moving with its group."),
    });
  }
  let market = null;
  if (spyCloses && spyCloses.length >= 200) {
    const above = spyCloses[spyCloses.length - 1] > sma(spyCloses, 200);
    const v = vix != null ? Math.round(vix * 10) / 10 : null;
    const vixWord = v == null ? null : v < 15 ? "calm (complacency is possible)"
      : v < 20 ? "normal" : v < 30 ? "elevated — fear is up" : "panic-level — violent, but historically near better entry points";
    market = {
      spy_above_200d: above, spy_1m: r1(m1), vix: v,
      text: `Market backdrop: the S&P 500 is ${above ? "above" : "BELOW"} its 200-day average ` +
        `(${above ? "uptrend" : "downtrend — most stocks struggle in one"})` +
        (v != null ? `; VIX ${v}, ${vixWord}.` : "."),
    };
  }

  // ---- Bottom line: does the story agree with the chart?
  const storyScore = (growth === "secular" ? 1 : 0) + groupTone + stockTone
    + (market && !market.spy_above_200d ? -1 : 0);
  const rec = String(recommendation || "");
  const setup = /buy|accumulate/i.test(rec) ? 1 : /sell|reduce/i.test(rec) ? -1 : 0;
  let bottom;
  if (storyScore >= 1 && setup > 0) bottom = "Story and setup agree: a business the market is paying up for, and the chart confirms it. The trade plan's stop is what protects you if that changes.";
  else if (storyScore >= 1 && setup < 0) bottom = "The story is intact but the price isn't cooperating. A watchlist name: wait for the trend to turn rather than buying weakness.";
  else if (storyScore >= 1) bottom = "Good story, undecided chart. Let the price confirm before committing — the entry matters as much as the business.";
  else if (storyScore <= -1 && setup > 0) bottom = "The chart looks constructive, but the market is not favouring this group. Treat it as a trade, not a long-term hold, and respect the stop.";
  else if (storyScore <= -1 && setup < 0) bottom = "Neither the story nor the setup argues for owning it now.";
  else if (storyScore <= -1) bottom = "Out-of-favour group and no clear setup. It needs a catalyst of its own.";
  else bottom = setup > 0 ? "A neutral backdrop with a constructive chart: the setup is doing the work here, not the story."
    : setup < 0 ? "A neutral backdrop with a weak chart: little reason to own it yet."
    : "No strong signal from either the story or the chart.";
  if (growth === "speculative") bottom += " Speculative: outcomes are wide — size it small.";

  return {
    business: classification ? {
      name: classification.name, sector: classification.sector, industry: classification.industry,
    } : null,
    type: { style, growth, traits },
    theme: theme ? {
      key: theme.key, name: theme.name, etf: theme.etf, matched: theme.matched,
      scope: theme.scope || null, drivers: theme.drivers || [], risks: theme.risks || [],
    } : null,
    pulse: {
      stock_1m: r1(s1), stock_3m: r1(s3), group_1m: r1(e1), group_3m: r1(e3),
      spy_1m: r1(m1), spy_3m: r1(m3), group_tone: groupTone, stock_tone: stockTone, reads,
      group_source: useBasket ? "basket" : (e3 != null ? "etf" : null),
      basket: useBasket ? { n: basket.n, breadth_50d: basket.breadth_50d, leaders: basket.leaders,
                            laggards: basket.laggards, as_of: basket.as_of } : null,
    },
    market,
    bottom_line: bottom,
  };
}
