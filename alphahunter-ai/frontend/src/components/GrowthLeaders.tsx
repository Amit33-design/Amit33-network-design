// Growth leaders — growing businesses whose stock is already working. The
// opposite screen to the oversold list: strength, not wreckage.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, EmptyState } from "./ui";

type Growth = {
  ticker: string; company?: string; score: number;
  action?: string; confidence?: string; quality_grade?: string;
  entry?: number | null;
  exit_plan?: { target: number; stop: number; horizon_days: number;
                target_pct: number; stop_pct: number } | null;
  metrics?: {
    growth_score?: number; revenue_growth?: number | null;
    earnings_growth?: number | null; gross_margin?: number | null;
    rs_vs_spy_60d?: number | null; dist_52w_high?: number | null;
    reasons?: string[]; warnings?: string[];
  };
};
export type GrowthFeed = { date?: string | null; count: number; results: Growth[] };

const pct = (v?: number | null, digits = 0) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;

export function useGrowth(): GrowthFeed | null {
  const [d, setD] = useState<GrowthFeed | null>(null);
  useEffect(() => {
    fetch("/growth.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => setD(j?.results?.length ? j : null))
      .catch(() => setD(null));
  }, []);
  return d;
}

export default function GrowthLeaders({ feed }: { feed: GrowthFeed }) {
  const rows = feed.results;
  if (!rows.length) {
    return <EmptyState icon="🌱" title="No growth leaders today"
      hint={<>Nothing cleared the growth screen — a growing business, an intact
             uptrend, beating the market, and not overheated.</>} />;
  }
  return (
    <div className="space-y-3">
      <div className="text-xs text-ink-muted">
        Growing businesses whose stock is already working: revenue growth, an
        intact uptrend above the 200-day, near the 52-week high and beating SPY.
        Names running too hot are <b>excluded</b>, not rewarded — buying a
        vertical chart after the move is how growth screens lose money. Each row
        carries the exit that goes with it.
      </div>
      {/* Say plainly that this screen has no track record yet. The oversold
          screen has months of measured results; this one started today, and
          presenting them as equally proven would be dishonest. */}
      <div className="text-2xs text-warn border border-warn/30 bg-warn-soft rounded-panel px-3 py-1.5">
        <b>New screen, no track record yet.</b> These picks are now recorded daily
        and judged alongside the oversold ones, so the paper portfolio will show
        whether this screen actually works. Until it has months behind it, treat
        it as a reasoned starting point rather than a measured edge.
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
                  <div className="font-bold text-gain">{m.growth_score ?? r.score}</div>
                  <div className="text-2xs text-ink-muted">growth score</div>
                </div>
              </div>

              <div className="mt-2 flex flex-wrap gap-1.5">
                {m.revenue_growth != null && (
                  <Badge tone="gain">rev {pct(m.revenue_growth)}</Badge>)}
                {m.gross_margin != null && (
                  <Badge>{pct(m.gross_margin)} margin</Badge>)}
                {m.rs_vs_spy_60d != null && (
                  <Badge tone={m.rs_vs_spy_60d >= 0 ? "gain" : "loss"}>
                    {m.rs_vs_spy_60d >= 0 ? "+" : ""}{m.rs_vs_spy_60d}pp vs SPY
                  </Badge>)}
                {m.dist_52w_high != null && (
                  <Badge>{Math.abs(m.dist_52w_high).toFixed(0)}% off high</Badge>)}
              </div>

              {x && r.entry && (
                <div className="mt-2 text-xs text-ink-secondary num">
                  Buy ~${r.entry} · take profit{" "}
                  <b className="text-gain">${x.target}</b> ({x.target_pct >= 0 ? "+" : ""}{x.target_pct}%)
                  {" "}· stop <b className="text-loss">${x.stop}</b> ({x.stop_pct}%)
                  {" "}· review after {x.horizon_days}d
                </div>
              )}
              {m.reasons?.length ? (
                <div className="mt-1 text-xs text-ink-secondary">{m.reasons.slice(0, 3).join(" · ")}</div>
              ) : null}
              {m.warnings?.length ? (
                <div className="mt-1 text-xs text-warn">{m.warnings.slice(0, 2).join(" · ")}</div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
