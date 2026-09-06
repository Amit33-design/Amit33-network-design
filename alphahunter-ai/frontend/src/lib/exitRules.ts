// Exit rules, client side.
//
// SOURCE OF TRUTH: backend/exit_rules.py. This is a deliberate port, not a
// second design — the constants and the order of checks must match it. It
// exists because the static deploy has no Python at request time, and asking a
// serverless function per holding would make the page slow for no benefit; the
// arithmetic is trivial.
//
// If you change a threshold, change it in both places.

export const DEFAULT_HORIZON_DAYS = 10;
export const DEFAULT_TARGET_PCT = 12.0;
export const DEFAULT_STOP_PCT = -7.0;
export const TRAIL_ARMS_AT_PCT = 8.0;
export const TRAIL_GIVEBACK_PCT = 5.0;

export type ExitPlan = {
  entry: number; target: number; stop: number;
  horizonDays: number; targetPct: number; stopPct: number;
};

export type ExitAction = "hold" | "take_profit" | "sell" | "close_stale";
export type ExitCheck = {
  action: ExitAction; reason: string; gainPct: number; daysHeld: number;
};

export function buildPlan(
  entry: number,
  opts: { atr?: number | null; horizonDays?: number } = {},
): ExitPlan {
  const horizonDays = opts.horizonDays ?? DEFAULT_HORIZON_DAYS;
  let targetPct = DEFAULT_TARGET_PCT;
  let stopPct = DEFAULT_STOP_PCT;

  if (opts.atr && opts.atr > 0 && entry > 0) {
    // Scale to the HOLDING PERIOD, not a single day: volatility grows with the
    // square root of time, so a 2%-a-day stock has a ~6.5% range over 10
    // sessions. Clamped so a bad ATR reading can't produce an absurd plan.
    const atrPct = (opts.atr / entry) * 100;
    const horizonMove = atrPct * Math.sqrt(horizonDays);
    targetPct = Math.max(5, Math.min(30, horizonMove));
    stopPct = -Math.max(3, Math.min(15, horizonMove * 0.6));   // ~1.67:1
  }

  return {
    entry: round2(entry),
    target: round2(entry * (1 + targetPct / 100)),
    stop: round2(entry * (1 + stopPct / 100)),
    horizonDays,
    targetPct: round2(targetPct),
    stopPct: round2(stopPct),
  };
}

export function checkExit(
  plan: ExitPlan,
  price: number,
  opts: { daysHeld?: number; peakPrice?: number | null } = {},
): ExitCheck {
  const daysHeld = opts.daysHeld ?? 0;
  const gainPct = (price / plan.entry - 1) * 100;
  const base = { gainPct: round2(gainPct), daysHeld };

  // 1. Stop first. If a gap took price through both levels, the loss is what
  //    actually happened to you.
  if (price <= plan.stop) {
    return { ...base, action: "sell", reason:
      `Stop hit at $${plan.stop.toFixed(2)} (${plan.stopPct.toFixed(1)}%). The reason for owning it is gone — take the small loss.` };
  }

  // 2. Target.
  if (price >= plan.target) {
    return { ...base, action: "take_profit", reason:
      `Target hit at $${plan.target.toFixed(2)} (+${plan.targetPct.toFixed(1)}%). Book it — this is the move the setup was predicting.` };
  }

  // 3. Trailing stop, once there is a gain worth protecting.
  if (opts.peakPrice != null && opts.peakPrice > plan.entry) {
    const peakGain = (opts.peakPrice / plan.entry - 1) * 100;
    const giveback = ((opts.peakPrice - price) / opts.peakPrice) * 100;
    if (peakGain >= TRAIL_ARMS_AT_PCT && giveback >= TRAIL_GIVEBACK_PCT) {
      return { ...base, action: "take_profit", reason:
        `Was up ${peakGain.toFixed(1)}% and has given back ${giveback.toFixed(1)}% from the high. Protect the gain rather than watch it round-trip.` };
    }
  }

  // 4. Time. The measured edge is a multi-week move; past that the thesis has
  //    not worked, whatever the price is doing.
  if (daysHeld >= plan.horizonDays) {
    return { ...base, action: "close_stale", reason:
      `${daysHeld} trading days held with no target or stop hit (${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(1)}%). The setup's window has passed — free the capital.` };
  }

  const left = plan.horizonDays - daysHeld;
  return { ...base, action: "hold", reason:
    `${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(1)}% · target $${plan.target.toFixed(2)} / stop $${plan.stop.toFixed(2)} · ${left} day${left === 1 ? "" : "s"} left in the window` };
}

/** Trading days between two ISO dates (weekends excluded, holidays ignored). */
export function tradingDaysBetween(fromISO: string, toDate = new Date()): number {
  const from = new Date(fromISO + "T00:00:00");
  if (Number.isNaN(from.getTime())) return 0;
  let days = 0;
  const cur = new Date(from);
  while (cur < toDate) {
    cur.setDate(cur.getDate() + 1);
    const d = cur.getDay();
    if (d !== 0 && d !== 6) days++;
  }
  return days;
}

const round2 = (v: number) => Math.round(v * 100) / 100;

export const ACTION_LABEL: Record<ExitAction, string> = {
  take_profit: "TAKE PROFIT",
  sell: "SELL — STOP",
  close_stale: "CLOSE — STALE",
  hold: "HOLD",
};
