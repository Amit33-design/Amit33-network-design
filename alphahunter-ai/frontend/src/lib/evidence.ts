// Evidence status per screen, from the exit-judged track record.
//
// The audit's core finding: the dashboard led with screens that were either
// unproven or trailing the index, while the one strategy with positive
// out-of-sample evidence sat in a collapsed section. Every screen now carries
// a status computed from its own closed trades, judged at their exit plan.
import { useEffect, useState } from "react";

export type ScreenRecord = {
  trades: number; dates?: number; win_rate: number; avg_return_pct?: number;
  "avg_return_%": number; "avg_alpha_%"?: number | null;
  beat_spy_rate?: number | null; avg_days_held?: number;
};
export type Judged = {
  summary?: ScreenRecord | null;
  by_screen?: Record<string, ScreenRecord>;
};

// Below this many CLOSED trades, any figure is noise and is shown as such.
export const MIN_TRADES = 20;
// ...and from at least this many distinct scan dates. Picks made on the same
// day ride the same market: Growth's first 36 trades came from three dates,
// which is one market window, not 36 observations.
export const MIN_DATES = 10;

export type Status = {
  label: "Beating SPY" | "Trailing SPY" | "Mixed" | "Unproven";
  tone: "gain" | "loss" | "warn" | "neutral";
  detail: string;
};

export function statusFor(rec?: ScreenRecord | null): Status {
  if (!rec || !rec.trades) {
    return { label: "Unproven", tone: "neutral",
             detail: "No closed trades yet — nothing to judge this screen on." };
  }
  const n = rec.trades;
  const alpha = rec["avg_alpha_%"];
  if (n < MIN_TRADES) {
    return { label: "Unproven", tone: "neutral",
             detail: `Only ${n} closed trade${n === 1 ? "" : "s"} — under ${MIN_TRADES}, any result is noise.` };
  }
  if (rec.dates != null && rec.dates < MIN_DATES) {
    return { label: "Unproven", tone: "neutral",
             detail: `${n} trades, but from only ${rec.dates} scan date${rec.dates === 1 ? "" : "s"} — `
               + `one stretch of market, not ${n} independent results. Needs ${MIN_DATES}+ dates.` };
  }
  const beat = rec.beat_spy_rate ?? 0;
  const base = `${n} trades judged at their exit plan: avg ${rec["avg_return_%"] >= 0 ? "+" : ""}${rec["avg_return_%"]}%`
    + (alpha != null ? `, ${alpha >= 0 ? "+" : ""}${alpha}pp vs SPY over the same days` : "")
    + `, ${(rec.win_rate * 100).toFixed(0)}% winners.`;
  if (alpha != null && alpha > 0 && beat > 0.5) return { label: "Beating SPY", tone: "gain", detail: base };
  if (alpha != null && alpha <= 0) return { label: "Trailing SPY", tone: "loss", detail: base };
  return { label: "Mixed", tone: "warn", detail: base };
}

export function useJudged(): Judged | null {
  const [d, setD] = useState<Judged | null>(null);
  useEffect(() => {
    fetch("/exit_judged.json")
      .then((r) => (r.ok ? r.json() : null))
      .then(setD)
      .catch(() => setD(null));
  }, []);
  return d;
}
