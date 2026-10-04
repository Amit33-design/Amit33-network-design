// Earnings calendar (public/earnings.json, written by the weekly factor-lab
// job). A stop-loss does not protect a position through an earnings report:
// the stock can open 20% away and the stop fills there. So the next report
// date is risk information, shown wherever the product suggests a trade.
import { useEffect, useState } from "react";

export type EarningsEntry = { next: string | null; last: { date: string; surprise_pct: number | null } | null };
type File = { generated: string | null; calendar: Record<string, EarningsEntry> };

let cache: Promise<File | null> | null = null;
export function useEarnings(): Record<string, EarningsEntry> | null {
  const [d, setD] = useState<Record<string, EarningsEntry> | null>(null);
  useEffect(() => {
    cache ??= fetch("/earnings.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    cache.then((f) => setD(f?.generated ? f.calendar : null));
  }, []);
  return d;
}

/** Weekday sessions from `from` (exclusive) to `to` (inclusive). Pure. */
export function sessionsUntil(toISO: string, from = new Date()): number {
  const to = new Date(toISO + "T00:00:00");
  const cur = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  let n = 0;
  while (cur < to) {
    cur.setDate(cur.getDate() + 1);
    if (cur.getDay() !== 0 && cur.getDay() !== 6) n++;
  }
  return n;
}

export type EarningsRisk = { next: string; sessions: number; insideWindow: boolean } | null;

/** Is the next report inside a holding window of `horizon` sessions? Pure. */
export function earningsRisk(e: EarningsEntry | undefined | null, horizon: number, now = new Date()): EarningsRisk {
  if (!e?.next) return null;
  const sessions = sessionsUntil(e.next, now);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (new Date(e.next + "T00:00:00") < today) return null;          // stale entry
  return { next: e.next, sessions, insideWindow: sessions <= horizon };
}

export const prettyDate = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
