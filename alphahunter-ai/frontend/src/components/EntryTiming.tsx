// Entry timing for a range-bound stock.
//
// "Buy" without a price is close to useless: a stock that oscillated between
// $80 and $120 all year is a buy at $85 and a bad trade at $118 on identical
// technicals. When the year has been lateral, this says which one you're
// looking at — and what to wait for.
import { Badge } from "./ui";

export type EntryTiming = {
  action: "buy_zone" | "wait";
  entry_target?: number | null;
  position_in_range?: number;
  range_low?: number; range_high?: number;
  typical_wait_sessions?: number | null;
  "upside_to_range_high_%"?: number | null;
  reason?: string;
};

export default function EntryTimingPanel(
  { t, price }: { t: EntryTiming; price?: number | null },
) {
  const waiting = t.action === "wait";
  const pos = (t.position_in_range ?? 0) * 100;

  return (
    <div className={`panel p-3 border-l-4 ${waiting ? "border-warn" : "border-gain"}`}>
      <div className="flex flex-wrap items-center gap-2 mb-1.5">
        <span className="font-semibold text-ink text-sm">⏳ Entry timing</span>
        <Badge tone={waiting ? "warn" : "gain"}>
          {waiting ? "WAIT FOR A BETTER PRICE" : "IN THE BUY ZONE"}
        </Badge>
        <span className="text-2xs text-ink-muted">range-bound for the past year</span>
      </div>

      {/* Where in the range we are, as a bar — the single most useful view. */}
      {t.range_low != null && t.range_high != null && (
        <div className="mt-1">
          <div className="relative h-6 rounded bg-surface-sunken border border-line">
            {/* buy zone = bottom third */}
            <div className="absolute inset-y-0 left-0 rounded-l bg-gain/20"
                 style={{ width: "35%" }} />
            <div className="absolute inset-y-0 w-0.5 bg-ink"
                 style={{ left: `${Math.max(0, Math.min(100, pos))}%` }}
                 title={`Now: $${price?.toFixed(2) ?? "—"} (${pos.toFixed(0)}% up the range)`} />
            {t.entry_target != null && t.range_high > t.range_low && (
              <div className="absolute inset-y-0 w-0.5 bg-gain"
                   style={{ left: `${((t.entry_target - t.range_low) / (t.range_high - t.range_low)) * 100}%` }}
                   title={`Target entry: $${t.entry_target.toFixed(2)}`} />
            )}
          </div>
          <div className="flex justify-between text-2xs text-ink-muted mt-0.5 num">
            <span>${t.range_low.toFixed(2)} low</span>
            {t.entry_target != null && (
              <span className="text-gain">buy ≈ ${t.entry_target.toFixed(2)}</span>
            )}
            <span>${t.range_high.toFixed(2)} high</span>
          </div>
        </div>
      )}

      <div className="mt-2 text-xs text-ink-secondary">{t.reason}</div>

      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-2xs text-ink-muted">
        <span>now <b className="text-ink">{pos.toFixed(0)}%</b> up the range</span>
        {t["upside_to_range_high_%"] != null && (
          <span><b className="text-ink">{t["upside_to_range_high_%"].toFixed(0)}%</b> left to the range high</span>
        )}
        {t.typical_wait_sessions != null && (
          <span title="Median sessions between visits to the buy zone, from this stock's own history">
            historically revisits the buy zone every <b className="text-ink">~{t.typical_wait_sessions}</b> sessions
          </span>
        )}
      </div>
    </div>
  );
}
