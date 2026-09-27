// Vercel serverless function: GET /api/thesis?ticker=NVDA
// Real-time, per-stock thesis — the compact "what's the story right now"
// endpoint the UI calls when you tap any stock (Dashboard cards, holdings...).
// Returns {ticker, name, price, day_change_pct, score, verdict, thesis} in one
// small payload. Heavier charting stays on /api/ta.

const CHART = (t, range) =>
  `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(t)}?range=${range}&interval=1d`;
import { rsiLast } from "./_indicators.js";
import { buildStory, fetchStoryInputs } from "./_story.js";

const UA = { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" };

const smaLast = (a, n) => (a.length < n ? null : a.slice(-n).reduce((x, y) => x + y, 0) / n);
const ret = (c, n) => (c.length > n ? ((c[c.length - 1] - c[c.length - 1 - n]) / c[c.length - 1 - n]) * 100 : null);

async function closesFor(ticker, range) {
  const r = await fetch(CHART(ticker, range), { headers: UA });
  if (!r.ok) return null;
  const j = await r.json();
  const res = j?.chart?.result?.[0];
  const q = res?.indicators?.quote?.[0];
  if (!q?.close) return null;
  return {
    meta: res.meta,
    c: q.close.filter((x) => x != null),
    h: (q.high || []).filter((x) => x != null),
    l: (q.low || []).filter((x) => x != null),
  };
}

function buildThesis(t, d, spy) {
  const c = d.c;
  const last = c[c.length - 1];
  const day = ret(c, 1);
  const month = ret(c, 21);
  const r6 = ret(c, 126);
  const hi52 = Math.max(...c.slice(-252)), lo52 = Math.min(...c.slice(-252));
  const dHigh = hi52 ? ((last - hi52) / hi52) * 100 : null;
  const dLow = lo52 ? ((last - lo52) / lo52) * 100 : null;
  const s50 = smaLast(c, 50), s200 = smaLast(c, 200);
  const rsi = rsiLast(c);
  // ATR% approximation from close-to-close moves when H/L are sparse.
  let atrPct = null;
  if (d.h.length >= 15 && d.l.length >= 15) {
    let s = 0;
    for (let i = d.c.length - 14; i < d.c.length; i++) s += (d.h[i] - d.l[i]) / d.c[i];
    atrPct = (s / 14) * 100;
  }
  const spyDay = spy ? ret(spy, 1) : null;
  const spyMonth = spy ? ret(spy, 21) : null;

  // Verdict score (same bands as the rest of the app).
  let score = 50;
  if (s200 != null) score += last > s200 ? 12 : -10;
  if (s50 != null && s200 != null) score += s50 > s200 ? 6 : -4;
  if (rsi != null) { if (rsi < 30) score += 8; else if (rsi > 70) score -= 8; }
  if (r6 != null) score += r6 > 0 ? 8 : -6;
  if (dHigh != null && dHigh > -10) score += 6;
  score = Math.max(0, Math.min(100, Math.round(score)));
  const verdict =
    score >= 70 ? "Buy" : score >= 58 ? "Accumulate" : score >= 45 ? "Hold" : score >= 32 ? "Reduce" : "Sell";

  const parts = [];
  if (day != null && day <= -1.5) {
    if (spyDay != null && spyDay <= -1.0)
      parts.push(`${t} is down ${day.toFixed(1)}% today with the whole market (S&P ${spyDay.toFixed(1)}%) — market-driven weakness.`);
    else if (spyDay != null && spyDay > -0.3)
      parts.push(`${t} is down ${day.toFixed(1)}% on a flat market — stock-specific; check headlines before buying the dip.`);
    else
      parts.push(`${t} is down ${day.toFixed(1)}% today, more than the market.`);
  } else if (day != null && day >= 1.5) {
    parts.push(`${t} is up ${day.toFixed(1)}% today${spyDay != null ? ` vs S&P ${spyDay >= 0 ? "+" : ""}${spyDay.toFixed(1)}%` : ""}${spyDay != null && day > spyDay + 1 ? " — relative strength" : ""}.`);
  }
  if (month != null && spyMonth != null) {
    const spread = month - spyMonth;
    if (spread <= -8) parts.push(`It has lagged the market by ${Math.abs(spread).toFixed(0)}pp over the past month — money is rotating away; it needs its own catalyst.`);
    else if (spread >= 8) parts.push(`It has beaten the market by ${spread.toFixed(0)}pp over the past month — a leader.`);
  }
  if (s200 != null) {
    parts.push(last > s200
      ? `The primary trend is up (above the 200-day${s50 != null && s200 != null && s50 > s200 ? ", golden-cross regime" : ""}) — dips are typically buyable weakness.`
      : `The primary trend is down (below the 200-day) — bounces are counter-trend.`);
  }
  if (r6 != null && r6 > 50 && dHigh != null && dHigh <= -10)
    parts.push(`A high-momentum name (+${r6.toFixed(0)}% in 6 months) digesting a big run — this size pullback is routine for it.`);
  else if (dHigh != null && dHigh > -8)
    parts.push(`Trading within ${Math.abs(dHigh).toFixed(0)}% of its 52-week high — strength being bought.`);
  else if (dLow != null && dLow < 12)
    parts.push(`Only ${dLow.toFixed(0)}% above its 52-week low — deeply out of favor; be selective.`);
  if (atrPct != null && atrPct >= 4)
    parts.push(`High-volatility name (~${atrPct.toFixed(1)}% average daily range) — big single days are normal here.`);
  if (rsi != null && (rsi < 32 || rsi > 70))
    parts.push(rsi < 32 ? `RSI ${rsi.toFixed(0)} is oversold — stretched to the downside.` : `RSI ${rsi.toFixed(0)} is overbought — stretched to the upside.`);
  parts.push(`Net: ${verdict.toLowerCase()} at a technical score of ${score}/100.`);

  return { day, score, verdict, thesis: parts.join(" "),
           indicators: { ret_6m: r6, dist_52w_high: dHigh,
                         atr: atrPct != null ? (atrPct / 100) * last : null } };
}

export default async function handler(req, res) {
  const ticker = String(req.query?.ticker || "").toUpperCase().trim();
  if (!ticker) return res.status(400).json({ error: "ticker required" });
  try {
    // ?story=1 adds the investment story (theme, group sentiment, market).
    // Opt-in: the watchlist calls this for every saved ticker and only needs
    // the verdict, so it should not pay for three extra fetches each.
    const wantStory = req.query?.story === "1";
    const spyP = ticker === "SPY" ? Promise.resolve(null)
      : closesFor("SPY", "1y").then((x) => x?.c ?? null).catch(() => null);
    const [d, spy, inputs] = await Promise.all([
      closesFor(ticker, "1y"), spyP,
      wantStory ? fetchStoryInputs(ticker, spyP).catch(() => null) : null,
    ]);
    if (!d || d.c.length < 30) return res.status(404).json({ error: "no data" });
    const out = buildThesis(ticker, d, spy);
    const story = inputs ? buildStory({
      ticker, closes: d.c, indicators: out.indicators, price: d.c[d.c.length - 1],
      recommendation: out.verdict, ...inputs,
    }) : null;
    res.setHeader("Cache-Control", "s-maxage=300, stale-while-revalidate=600");
    return res.status(200).json({
      ticker,
      name: d.meta?.shortName || d.meta?.longName || ticker,
      price: Math.round(d.c[d.c.length - 1] * 100) / 100,
      day_change_pct: out.day != null ? Math.round(out.day * 100) / 100 : null,
      score: out.score,
      verdict: out.verdict,
      thesis: out.thesis,
      story,
    });
  } catch (e) {
    // Never surface exception text (AGENTS.md §8).
    console.error(`[thesis] ${ticker}:`, e);
    return res.status(500).json({ code: "thesis_failed",
                                  message: "Couldn't build a thesis right now." });
  }
}
