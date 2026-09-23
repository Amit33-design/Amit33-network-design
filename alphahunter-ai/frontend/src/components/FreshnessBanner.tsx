// Says how old the scan data is — and says it loudly when it's stale.
//
// For nine days the daily scan was silently timing out while the dashboard
// header still showed today's date (its own workflow kept succeeding). Anyone
// using Opportunities or Growth in that window was acting on week-old screens
// with no way to know. This reads the manifest that the scan writes as its
// LAST step, so a dead pipeline shows up here as an ageing date.
import { useEffect, useState } from "react";

type Manifest = { scan_date?: string | null; completed_at?: string | null };

/** Weekdays between an ISO date and today. Holidays are ignored, which only
 *  ever makes the figure slightly high — the safe direction for a warning. */
export function tradingDaysSince(iso: string, now = new Date()): number {
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return 0;
  let n = 0;
  const cur = new Date(d);
  while (cur < now) {
    cur.setDate(cur.getDate() + 1);
    if (cur <= now && cur.getDay() !== 0 && cur.getDay() !== 6) n++;
  }
  // No "- 1": a scan dated today already counts 0 here. An earlier version
  // subtracted one anyway, which made yesterday's scan read as "today's" and
  // shaved a day off every stale warning.
  return n;
}

export const STALE_AFTER = 2;   // trading days

export function useScanFreshness(): { date: string | null; age: number | null } {
  const [m, setM] = useState<Manifest | null>(null);
  useEffect(() => {
    fetch("/freshness.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then(setM)
      .catch(() => setM(null));
  }, []);
  const date = m?.scan_date ?? null;
  return { date, age: date ? tradingDaysSince(date) : null };
}

const pretty = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined,
    { weekday: "short", month: "short", day: "numeric" });

/** A quiet line when fresh; an unmissable warning when stale. */
export default function FreshnessBanner({ what = "Scan data" }: { what?: string }) {
  const { date, age } = useScanFreshness();
  if (!date || age == null) return null;

  if (age <= STALE_AFTER) {
    return (
      <div className="mb-3 text-2xs text-ink-muted">
        {what} from <b className="text-ink-secondary">{pretty(date)}</b>
        {age === 0 ? " · today's scan" : ` · ${age} trading day${age === 1 ? "" : "s"} old`}
      </div>
    );
  }
  return (
    <div role="status"
         className="mb-3 rounded-panel border border-loss/40 bg-loss-soft px-3 py-2 text-xs text-loss">
      <b>{what} is {age} trading days old</b> — last updated {pretty(date)}.
      The daily scan has not completed since then, so prices, entries and
      rankings below may no longer reflect the market. Check anything here
      against a live quote before acting on it.
    </div>
  );
}
