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
// The verdict says the LONG-TERM trend decides, so judge it over a quarter as
// well as a month — a trend call can be right and slow.
export const LONG_HORIZON = 60;

/** The ingredients the verdict is built from, as numbers, for per-feature
 *  rank-IC: which of them carries any information about what comes next? */
export function features(res) {
  const ind = res.indicators || {};
  const px = res.price;
  const pct = (a, b) => (a != null && b ? (a / b - 1) * 100 : null);
  return {
    trend_score: res.trend?.score ?? null,
    timing_score: res.timing?.score ?? null,
    rsi: ind.rsi ?? null,
    macd_hist_pct: ind.macd_hist != null && px ? (ind.macd_hist / px) * 100 : null,
    ret_1m: ind.ret_1m ?? null, ret_3m: ind.ret_3m ?? null,
    ret_6m: ind.ret_6m ?? null, ret_1y: ind.ret_1y ?? null,
    dist_52w_high: ind.dist_52w_high ?? null, dist_52w_low: ind.dist_52w_low ?? null,
    vs_200d: pct(px, ind.sma200), sma50_vs_200: pct(ind.sma50, ind.sma200),
    atr_pct: ind.atr != null && px ? (ind.atr / px) * 100 : null,
    volume_ratio: ind.avg_volume ? (ind.last_volume || 0) / ind.avg_volume : null,
  };
}
export const STEP = 10;            // a cutoff every 10 sessions

/** One ticker's walk: [{date, verdict, score, fwd_%, spy_%}]. Pure. */
export function walk(series, spy, { window = WINDOW, horizon = HORIZON, step = STEP } = {}) {
  const { dates, o, h, l, c, v } = series;
  const spyAt = new Map(spy.dates.map((d, i) => [d, spy.c[i]]));
  const out = [];
  for (let end = window; end + horizon <= c.length; end += step) {
    const longEnd = end - 1 + LONG_HORIZON;
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
    const pL = c[longEnd], bL = longEnd < dates.length ? spyAt.get(dates[longEnd]) : null;
    out.push({ date: d0, verdict: res.recommendation, score: res.score,
               "fwd_%": (p1 / p0 - 1) * 100, "spy_%": (b1 / b0 - 1) * 100,
               // Quarter-ahead alpha where the history reaches that far.
               "alpha60_%": pL && bL ? ((pL / p0 - 1) - (bL / b0 - 1)) * 100 : null,
               f: features(res) });
  }
  return out;
}

const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
// Overlapping windows are not independent observations. With a cutoff every
// STEP sessions and a HORIZON-session outcome, consecutive dates share
// HORIZON-STEP sessions of the same returns, so a plain t across dates is
// inflated by about sqrt(HORIZON/STEP). On pure random walks the uncorrected
// 60-session t reached 3 — a "finding" made of nothing but overlap.
export function overlapFactor(horizon, step) { return Math.sqrt(Math.max(1, horizon / step)); }

function tStat(a, overlap = 1) {
  if (a.length < 3) return null;
  const m = mean(a);
  const sd = Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1));
  return sd > 0 ? Math.round((m / (sd / Math.sqrt(a.length)) / overlap) * 100) / 100 : null;
}
const OV20 = overlapFactor(HORIZON, STEP), OV60 = overlapFactor(LONG_HORIZON, STEP);

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
      alpha_t_by_date: tStat(dateAlphas, OV20),
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
  // Per-ingredient rank-IC, same date-averaged method as the score, at both
  // horizons. This is what a re-weighting has to be built from.
  const featureKeys = rows.length && rows[0].f ? Object.keys(rows[0].f) : [];
  const icFor = (key, target, ov) => {
    const vals = [];
    for (const rs of byDate.values()) {
      const ok = rs.filter((r) => r.f?.[key] != null && target(r) != null);
      if (ok.length < 10) continue;
      const ic = rankCorr(ok.map((r) => r.f[key]), ok.map(target));
      if (ic != null) vals.push(ic);
    }
    return vals.length ? { ic: Math.round(mean(vals) * 1000) / 1000, t: tStat(vals, ov), dates: vals.length } : null;
  };
  const feature_ic = {};
  for (const k of featureKeys) {
    feature_ic[k] = {
      h20: icFor(k, (r) => r["fwd_%"] - r["spy_%"], OV20),
      h60: icFor(k, (r) => r["alpha60_%"], OV60),
    };
  }
  const by_verdict_60 = {};
  for (const vd of VERDICTS) {
    const rs = rows.filter((r) => r.verdict === vd && r["alpha60_%"] != null);
    if (rs.length < 30) continue;
    const bd = new Map();
    for (const r of rs) bd.set(r.date, [...(bd.get(r.date) || []), r["alpha60_%"]]);
    by_verdict_60[vd] = {
      cases: rs.length, dates: bd.size,
      "avg_alpha_%": Math.round(mean(rs.map((r) => r["alpha60_%"])) * 100) / 100,
      alpha_t_by_date: tStat([...bd.values()].map(mean), OV60),
    };
  }
  const b = byVerdict.Buy, s = byVerdict.Sell;
  return {
    feature_ic,
    by_verdict_60,
    cases: rows.length,
    dates: byDate.size,
    by_verdict: byVerdict,
    score_ic: ics.length ? Math.round(mean(ics) * 1000) / 1000 : null,
    score_ic_t: tStat(ics, OV20),
    buy_minus_sell_pp: b && s ? Math.round((b["avg_alpha_%"] - s["avg_alpha_%"]) * 100) / 100 : null,
  };
}
