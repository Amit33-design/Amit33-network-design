// Range-vs-trend regime and entry timing.
//
// Parity with backend/indicators/range_regime.py — same constants, same three
// conditions for "lateral". Change one, change both.
//
// The point: "Buy" without a price is close to useless. A stock that has
// oscillated between $80 and $120 all year is a buy at $85 and a bad trade at
// $118, and the same technicals can be true at both.

export const WINDOW = 252;
const LATERAL_NET_MOVE = 18.0;
const LATERAL_R2 = 0.35;
const TREND_R2 = 0.55;
const MIN_CROSSINGS = 3;
const BUY_ZONE = 0.35;
const WAIT_ZONE = 0.65;

function r2OfLogTrend(closes) {
  const pts = [];
  closes.forEach((c, i) => { if (c > 0) pts.push([i, Math.log(c)]); });
  const n = pts.length;
  if (n < 20) return null;
  const mx = pts.reduce((a, p) => a + p[0], 0) / n;
  const my = pts.reduce((a, p) => a + p[1], 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (const [x, y] of pts) {
    sxy += (x - mx) * (y - my); sxx += (x - mx) ** 2; syy += (y - my) ** 2;
  }
  if (sxx <= 0 || syy <= 0) return 0;
  return Math.max(0, Math.min(1, (sxy * sxy) / (sxx * syy)));
}

function midlineCrossings(closes, low, high) {
  const mid = (low + high) / 2;
  let crossings = 0, above = null;
  for (const c of closes) {
    const now = c > mid;
    if (above !== null && now !== above) crossings++;
    above = now;
  }
  return crossings;
}

function typicalWait(closes, target) {
  const visits = [];
  closes.forEach((c, i) => { if (c <= target) visits.push(i); });
  if (visits.length < 2) return null;
  const gaps = [];
  let last = visits[0];
  for (const v of visits.slice(1)) { if (v - last > 5) gaps.push(v - last); last = v; }
  if (!gaps.length) return null;
  gaps.sort((a, b) => a - b);
  return gaps[Math.floor(gaps.length / 2)];
}

export function rangeRegime(closes, window = WINDOW) {
  const px = (closes || []).filter((c) => c != null && c > 0).map(Number);
  if (px.length < 60) {
    return { regime: "unclear", action: "none",
             reason: "not enough history to judge a range" };
  }
  const w = px.length > window ? px.slice(-window) : px;
  const last = w[w.length - 1];
  const low = Math.min(...w), high = Math.max(...w);
  if (high <= low) {
    return { regime: "unclear", action: "none", reason: "degenerate price range" };
  }

  const position = (last - low) / (high - low);
  // Median of the first and last fifth, not single endpoint bars: otherwise
  // the answer depends on where the window happens to start.
  const seg = Math.max(3, Math.floor(w.length / 5));
  const med = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];
  const head = med(w.slice(0, seg)), tail = med(w.slice(-seg));
  const netMove = head > 0 ? (tail / head - 1) * 100 : 0;
  const width = ((high - low) / low) * 100;
  const r2 = r2OfLogTrend(w) ?? 0;
  const crossings = midlineCrossings(w, low, high);

  let regime;
  const lateral = Math.abs(netMove) < LATERAL_NET_MOVE && r2 < LATERAL_R2
    && crossings >= MIN_CROSSINGS;
  if (lateral) regime = "lateral";
  else if (r2 >= TREND_R2) regime = netMove > 0 ? "trending_up" : "trending_down";
  else if (netMove > LATERAL_NET_MOVE) regime = "trending_up";
  else if (netMove < -LATERAL_NET_MOVE) regime = "trending_down";
  else regime = "unclear";   // flat but never oscillated — no range to buy

  const r2pct = (x) => Math.round(x * 100) / 100;
  const out = {
    regime,
    position_in_range: Math.round(position * 1000) / 1000,
    range_low: r2pct(low), range_high: r2pct(high),
    "net_move_%": Math.round(netMove * 10) / 10,
    "range_width_%": Math.round(width * 10) / 10,
    trend_r2: Math.round(r2 * 1000) / 1000,
    midline_crossings: crossings,
    action: "none", entry_target: null,
    "upside_to_range_high_%": null, typical_wait_sessions: null,
    factors: [
      `${netMove >= 0 ? "+" : ""}${netMove.toFixed(0)}% over the window against a ${width.toFixed(0)}%-wide range`,
      `trend line explains ${(r2 * 100).toFixed(0)}% of the move`,
      `crossed the midline ${crossings} times`,
      `sitting ${(position * 100).toFixed(0)}% of the way up the range`,
    ],
    reason: "",
  };

  if (regime === "unclear") {
    out.reason = "Roughly flat over the window, but it never oscillated between two levels — so there is no range to buy the bottom of.";
    return out;
  }
  if (regime !== "lateral") {
    out.reason = `Trending ${regime === "trending_up" ? "up" : "down"}, not range-bound — the range low is not a reliable entry and position within it says little.`;
    return out;
  }

  const target = low + BUY_ZONE * (high - low);
  out.entry_target = r2pct(target);
  out["upside_to_range_high_%"] = Math.round((high / last - 1) * 1000) / 10;
  out.typical_wait_sessions = typicalWait(w, target);
  const money = (x) => `$${x.toFixed(2)}`;

  if (position <= BUY_ZONE) {
    out.action = "buy_zone";
    out.reason = `Sideways for the window and trading in the bottom ${(position * 100).toFixed(0)}% of its ${money(low)}-${money(high)} range — about ${out["upside_to_range_high_%"].toFixed(0)}% back to the top of the range.`;
  } else if (position >= WAIT_ZONE) {
    out.action = "wait";
    const waitTxt = out.typical_wait_sessions
      ? ` It has revisited that area roughly every ${out.typical_wait_sessions} sessions.` : "";
    out.reason = `Sideways for the window and already ${(position * 100).toFixed(0)}% of the way up its ${money(low)}-${money(high)} range. Buying here pays near the top of a range that has gone nowhere — wait for roughly ${money(target)}.${waitTxt}`;
  } else {
    out.action = "wait";
    out.reason = `Sideways for the window, mid-range at ${(position * 100).toFixed(0)}%. Neither cheap nor extended — a patient entry near ${money(target)} is worth more than the ${out["upside_to_range_high_%"].toFixed(0)}% left to the top of the range.`;
  }
  return out;
}
