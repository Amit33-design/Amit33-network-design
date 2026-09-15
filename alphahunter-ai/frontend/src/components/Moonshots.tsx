// Moonshots — the lottery-ticket profile: volatile and beaten down.
//
// Measured, not guessed: names like these doubled 19.0% of the time against a
// 4.8% base rate, over 62,202 samples. The same measurement says the MEDIAN
// outcome was +6.7%, so this list is presented as odds, never as picks.
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Badge, EmptyState } from "./ui";

type Moon = {
  ticker: string; company?: string; score: number; entry?: number | null;
  exit_plan?: { target: number; stop: number; horizon_days: number } | null;
  metrics?: {
    moonshot_score?: number; "volatility_%"?: number | null;
    "ret_12m_%"?: number | null; "dist_52w_high_%"?: number | null;
    reasons?: string[]; "measured_double_rate_%"?: number;
    "base_rate_%"?: number; "median_outcome_%"?: number; caveat?: string;
  };
};
export type MoonFeed = { date?: string | null; count: number; results: Moon[] };

export function useMoonshots(): MoonFeed | null {
  const [d, setD] = useState<MoonFeed | null>(null);
  useEffect(() => {
    fetch("/moonshot.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => setD(j?.results?.length ? j : null))
      .catch(() => setD(null));
  }, []);
  return d;
}

export default function Moonshots({ feed }: { feed: MoonFeed }) {
  const rows = feed.results;
  if (!rows.length) {
    return <EmptyState icon="🎲" title="No moonshot candidates today"
      hint={<>Nothing cleared the screen — volatile enough to double, and already
             beaten down.</>} />;
  }
  const m0 = rows[0].metrics || {};
  const rate = m0["measured_double_rate_%"] ?? 19;
  const base = m0["base_rate_%"] ?? 4.8;
  const median = m0["median_outcome_%"] ?? 6.7;

  return (
    <div className="space-y-3">
      {/* The odds come before the names, deliberately. */}
      <div className="text-xs text-warn border border-warn/30 bg-warn-soft rounded-panel px-3 py-2">
        <b>These are odds, not picks.</b> Measured over 62,202 samples, stocks with
        this profile doubled <b>{rate}%</b> of the time against a <b>{base}%</b> base
        rate — a real edge, and still a <b>{(100 - rate).toFixed(0)}% chance it doesn't</b>.
        The median outcome was only <b>+{median}%</b>: a fat right tail on a mediocre
        middle. Size these small and hold many, the opposite of how you'd size a
        Growth Leader. Roughly 7% of the universe delists each year, mostly from
        this same beaten-down bucket, so {rate}% is an upper bound.
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {rows.slice(0, 12).map((r) => {
          const m = r.metrics || {};
          const x = r.exit_plan;
          return (
            <div key={r.ticker} className="panel p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <Link to={`/analysis?ticker=${r.ticker}`}
                        className="font-bold text-brand hover:underline">{r.ticker}</Link>
                  <span className="ml-2 text-xs text-ink-muted truncate">{r.company}</span>
                </div>
                <div className="text-right shrink-0">
                  <div className="font-bold text-warn">{m.moonshot_score ?? "—"}</div>
                  <div className="text-2xs text-ink-muted">moonshot score</div>
                </div>
              </div>

              <div className="mt-2 flex flex-wrap gap-1.5">
                {m["volatility_%"] != null && (
                  <Badge tone={m["volatility_%"] >= 80 ? "warn" : "neutral"}>
                    {m["volatility_%"].toFixed(0)}% vol
                  </Badge>)}
                {m["ret_12m_%"] != null && (
                  <Badge tone="loss">{m["ret_12m_%"].toFixed(0)}% in 12m</Badge>)}
                {m["dist_52w_high_%"] != null && (
                  <Badge>{Math.abs(m["dist_52w_high_%"]).toFixed(0)}% off high</Badge>)}
              </div>

              {x && r.entry && (
                <div className="mt-2 text-xs text-ink-secondary num">
                  Buy ~${r.entry} · take profit <b className="text-gain">${x.target}</b>
                  {" "}· stop <b className="text-loss">${x.stop}</b>
                  {" "}· review after {x.horizon_days}d
                </div>
              )}
              {m.reasons?.length ? (
                <div className="mt-1 text-xs text-ink-secondary">
                  {m.reasons.slice(0, 3).join(" · ")}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
