// Moonshots — the lottery-ticket profile: volatile and beaten down.
//
// Measured, not guessed: names like these doubled 19.0% of the time against a
// 4.8% base rate, over 62,202 samples. The same measurement says the MEDIAN
// outcome was +6.7%, so this list is presented as odds, never as picks.
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Badge, EmptyState } from "./ui";
import { useJudged } from "../lib/evidence";

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
  const watch = useJudged()?.moonshot_watch ?? null;
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
        {" "}<b>How to hold them:</b> no stop-loss — a 10-day stop on a stock that moves 5% a
        day just sells the noise (the first 20 picks traded that way were all stopped out).
        Sell half at the double; review after a year.
      </div>
      {watch && (
        <div className="text-xs text-ink-secondary">
          <b className="text-ink">So far:</b> {watch.picks} names, oldest {watch.oldest_sessions} sessions
          in · <b className={watch.doubled_so_far ? "text-gain" : "text-ink"}>
            {watch.doubled_so_far} doubled ({watch["doubled_%"]}%)</b>
          {" "}· median {watch["median_return_%"] >= 0 ? "+" : ""}{watch["median_return_%"]}%
          {watch["avg_vs_spy_pp"] != null && <> · {watch["avg_vs_spy_pp"] >= 0 ? "+" : ""}{watch["avg_vs_spy_pp"]}pp vs SPY</>}.
          {" "}The claim is ~{rate}% within a year; most picks are weeks old.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {rows.slice(0, 12).map((r) => {
          const m = r.metrics || {};
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

              {r.entry ? (
                // Always this screen's own rule, computed from the entry, so
                // picks saved under the old 10-day plan never show its stop.
                <div className="mt-2 text-xs text-ink-secondary num">
                  Buy ~${r.entry} · sell half at the double{" "}
                  <b className="text-gain">${(r.entry * 2).toFixed(2)}</b>
                  {" "}· <b className="text-warn">no stop</b> — size it as money you could lose
                  {" "}· review in 12 months
                </div>
              ) : null}
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
