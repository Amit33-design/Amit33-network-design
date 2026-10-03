// Walk-forward evaluation of the Analysis page's verdict.
//
// The verdict (Buy / Accumulate / Hold / Wait / Reduce / Sell) has been shown
// on every ticker without anyone measuring whether a Buy from it beats a
// Sell. This runs the SAME analyze() the page uses, at many past dates, on
// exactly the window the page would have seen (the last WINDOW bars — the
// page's default 1-year range), and records what each verdict was worth over
// the next HORIZON sessions against SPY over the same sessions.
//
// No look-ahead: each call sees only bars up to its cutoff. Picks made on the
// same date share one market, so significance is computed across DATES.
// Survivorship: the sample is today's listed stocks, which flatters every
// verdict a little (the delisted losers are missing) — the comparison
// BETWEEN verdicts is the trustworthy part, not the absolute levels.
import { analyze } from "./ta.js";

export const WINDOW = 252;
export const HORIZON = 20;
export const STEP = 10;            // a cutoff every 10 sessions

/** One ticker's walk: [{date, verdict, score, fwd_%, spy_%}]. Pure. */
export function walk(series, spy, { window = WINDOW, horizon = HORIZON, step = STEP } = {}) {
  const { dates, o, h, l, c, v } = series;
  const spyAt = new Map(spy.dates.map((d, i) => [d, spy.c[i]]));
  const out = [];
  for (let end = window; end + horizon <= c.length; end += step) {
    const s = end - window;
    let res;
    try {
      res = analyze(dates.slice(s, end), o.slice(s, end), h.slice(s, end),
                    l.slice(s, end), c.slice(s, end), v.slice(s, end), 25000, 1);
    } catch { continue; }
    const d0 = dates[end - 1], d1 = dates[end - 1 + horizon];
    const p0 = c[end - 1], p1 = c[end - 1 + horizon];
    const b0 = spyAt.get(d0), b1 = spyAt.get(d1);
    if (!p0 || !p1 || !b0 || !b1) continue;
    out.push({ date: d0, verdict: res.recommendation, score: res.score,
               "fwd_%": (p1 / p0 - 1) * 100, "spy_%": (b1 / b0 - 1) * 100 });
  }
  return out;
}

const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
function tStat(a) {
  if (a.length < 3) return null;
  const m = mean(a);
  const sd = Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1));
  return sd > 0 ? Math.round((m / (sd / Math.sqrt(a.length))) * 100) / 100 : null;
}

function rankCorr(xs, ys) {
  const rank = (a) => {
    const idx = a.map((v, i) => [v, i]).sort((p, q) => p[0] - q[0]);
    const r = new Array(a.length);
    idx.forEach(([, i], k) => { r[i] = k; });
    return r;
  };
  const rx = rank(xs), ry = rank(ys), n = xs.length;
  const mx = mean(rx), my = mean(ry);
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) { num += (rx[i] - mx) * (ry[i] - my); dx += (rx[i] - mx) ** 2; dy += (ry[i] - my) ** 2; }
  return dx && dy ? num / Math.sqrt(dx * dy) : null;
}

export const VERDICTS = ["Buy", "Accumulate", "Hold", "Wait", "Reduce", "Sell"];

/** Per-verdict outcomes, date-clustered, plus the score's rank-IC. Pure. */
export function summarise(rows) {
  const byVerdict = {};
  for (const vd of VERDICTS) {
    const rs = rows.filter((r) => r.verdict === vd);
    if (!rs.length) continue;
    const byDate = new Map();
    for (const r of rs) {
      const a = r["fwd_%"] - r["spy_%"];
      byDate.set(r.date, [...(byDate.get(r.date) || []), a]);
    }
    const dateAlphas = [...byDate.values()].map(mean);
    byVerdict[vd] = {
      cases: rs.length, dates: byDate.size,
      "avg_alpha_%": Math.round(mean(rs.map((r) => r["fwd_%"] - r["spy_%"])) * 100) / 100,
      "avg_return_%": Math.round(mean(rs.map((r) => r["fwd_%"])) * 100) / 100,
      beat_spy_rate: Math.round((rs.filter((r) => r["fwd_%"] > r["spy_%"]).length / rs.length) * 1000) / 1000,
      alpha_t_by_date: tStat(dateAlphas),
    };
  }
  // Does a higher score mean a better next 20 sessions? Spearman per date,
  // averaged, with its t across dates.
  const byDate = new Map();
  for (const r of rows) byDate.set(r.date, [...(byDate.get(r.date) || []), r]);
  const ics = [];
  for (const rs of byDate.values()) {
    if (rs.length < 10) continue;
    const ic = rankCorr(rs.map((r) => r.score), rs.map((r) => r["fwd_%"] - r["spy_%"]));
    if (ic != null) ics.push(ic);
  }
  const b = byVerdict.Buy, s = byVerdict.Sell;
  return {
    cases: rows.length,
    dates: byDate.size,
    by_verdict: byVerdict,
    score_ic: ics.length ? Math.round(mean(ics) * 1000) / 1000 : null,
    score_ic_t: tStat(ics),
    buy_minus_sell_pp: b && s ? Math.round((b["avg_alpha_%"] - s["avg_alpha_%"]) * 100) / 100 : null,
  };
}
