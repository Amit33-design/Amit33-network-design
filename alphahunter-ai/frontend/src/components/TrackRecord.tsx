// Track Record — how past picks actually performed.
//
// Lives here rather than on the Dashboard: it is accountability reporting, not
// something to look at while deciding what to buy today, and it was crowding
// out the picks. Render <TrackRecord p={...} /> wherever it should appear.
import { useEffect, useState } from "react";
import { Section, StatTile } from "./ui";

interface Perf {
  generated?: string;
  picks: { date: string; ticker: string; score?: number; action?: string;
           entry: number; price: number; "return_%": number; days: number }[];
  summary: { picks: number; win_rate: number; "avg_return_%": number;
             best: any; worst: any; "avg_alpha_%"?: number;
             beat_benchmark_rate?: number; benchmark?: string } | null;
  segments?: Record<string, { key: string; picks: number; win_rate: number;
                              "avg_return_%": number }[]>;
}

const SEGMENT_LABELS: Record<string, string> = {
  quality_grade: "By quality grade",
  grade_x_score: "By grade × score band",
  setup: "By setup type",
  confidence: "By confidence",
  score_band: "By score band",
};

// Which cohorts actually made money — the feedback loop on our own signals.
function SegmentTable({ title, rows }: { title: string; rows: any[] }) {
  if (!rows?.length) return null;
  return (
    <div>
      <div className="label-eyebrow mb-1">{title}</div>
      <table className="w-full text-sm num">
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-t border-line first:border-0">
              <td className="py-1 pr-2 font-medium">{r.key}</td>
              <td className="py-1 pr-2 text-ink-muted text-xs">{r.picks}</td>
              <td className="py-1 pr-2">{(r.win_rate * 100).toFixed(0)}%</td>
              <td className={`py-1 pr-2 text-right ${
                r["avg_return_%"] >= 0 ? "text-gain" : "text-loss"}`}>
                {r["avg_return_%"] >= 0 ? "+" : ""}{r["avg_return_%"]}%
              </td>
              {r["avg_alpha_%"] != null && (
                <td className={`py-1 text-right font-semibold ${
                  r["avg_alpha_%"] >= 0 ? "text-gain" : "text-loss"}`}
                    title="Average alpha vs SPY over the same holding window">
                  {r["avg_alpha_%"] >= 0 ? "+" : ""}{r["avg_alpha_%"]}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}



/** Loads performance.json. Null until the daily scan has judged enough picks. */
export function useTrackRecord(): Perf | null {
  const [perf, setPerf] = useState<Perf | null>(null);
  useEffect(() => {
    fetch("/performance.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setPerf(d?.summary ? d : null))
      .catch(() => setPerf(null));
  }, []);
  return perf;
}

export default function TrackRecord({ perf }: { perf: Perf }) {
  if (!perf.summary) return null;
  return (
          <Section
        title="📈 Track Record"
        subtitle={`since picks aged ≥2 days · updated ${perf.generated ?? ""}`}
        badge={perf.summary["avg_alpha_%"] != null
          ? `${((perf.summary.beat_benchmark_rate ?? 0) * 100).toFixed(0)}% beat ${perf.summary.benchmark ?? "SPY"} · alpha ${perf.summary["avg_alpha_%"] >= 0 ? "+" : ""}${perf.summary["avg_alpha_%"]}%`
          : `${(perf.summary.win_rate * 100).toFixed(0)}% winners · avg ${perf.summary["avg_return_%"] >= 0 ? "+" : ""}${perf.summary["avg_return_%"]}%`}
        badgeColor={(perf.summary["avg_alpha_%"] ?? perf.summary["avg_return_%"]) >= 0 ? "#1b7f4b" : "#c0392b"}
        defaultOpen={false}
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <StatTile label="Picks judged" value={perf.summary.picks} />
          <StatTile label="Win rate" value={`${(perf.summary.win_rate * 100).toFixed(0)}%`}
                    tone={perf.summary.win_rate >= 0.5 ? "gain" : "loss"} />
          <StatTile label="Avg return" value={`${perf.summary["avg_return_%"] >= 0 ? "+" : ""}${perf.summary["avg_return_%"]}%`}
                    tone={perf.summary["avg_return_%"] >= 0 ? "gain" : "loss"} />
          {perf.summary["avg_alpha_%"] != null ? (
            <StatTile label={`Alpha vs ${perf.summary.benchmark ?? "SPY"}`}
                      value={`${perf.summary["avg_alpha_%"] >= 0 ? "+" : ""}${perf.summary["avg_alpha_%"]}%`}
                      sub="excess return, same window"
                      tone={perf.summary["avg_alpha_%"] >= 0 ? "gain" : "loss"} />
          ) : (
            <StatTile label="Best pick" value={`${perf.summary.best?.ticker}`}
                      sub={`+${perf.summary.best?.["return_%"]}%`} tone="gain" />
          )}
        </div>
        {perf.summary["avg_alpha_%"] != null && perf.summary["avg_alpha_%"] < 0 && (
          <div className="mb-4 rounded-lg bg-warn-soft border border-warn/30 p-3 text-sm text-ink">
            <b>Read this before acting.</b> Across all {perf.summary.picks} judged picks the
            average result is <b>{perf.summary["avg_alpha_%"]}% vs {perf.summary.benchmark ?? "SPY"}</b>,
            and only {((perf.summary.beat_benchmark_rate ?? 0) * 100).toFixed(0)}% beat the index —
            so the board as a whole has <b>not</b> outperformed simply holding the market.
            The cohort table below shows where the edge actually is (the highest score band).
          </div>
        )}
        {perf.segments && Object.values(perf.segments).some((r) => r?.length) && (
          <div className="mb-4">
            <div className="text-sm font-semibold text-ink mb-2">
              What's actually working
              <span className="ml-2 text-xs font-normal text-ink-muted">
                picks · win rate · avg return · alpha vs SPY (groups under 3 picks hidden)
              </span>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-4">
              {Object.entries(perf.segments).map(([k, rows]) => (
                <SegmentTable key={k} title={SEGMENT_LABELS[k] ?? k} rows={rows} />
              ))}
            </div>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-ink-muted text-left">
              <tr>{["Picked", "Ticker", "Action", "Entry", "Now", "Return", "Held"].map((h) => (
                <th key={h} className="px-2 py-1 whitespace-nowrap">{h}</th>))}
              </tr>
            </thead>
            <tbody>
              {perf.picks.slice(0, 15).map((p, i) => (
                <tr key={`${p.date}-${p.ticker}-${i}`} className="border-t">
                  <td className="px-2 py-1 text-ink-muted whitespace-nowrap">{p.date}</td>
                  <td className="px-2 py-1 font-semibold text-alpha">{p.ticker}</td>
                  <td className="px-2 py-1">{p.action ?? "—"}</td>
                  <td className="px-2 py-1">${p.entry}</td>
                  <td className="px-2 py-1">${p.price}</td>
                  <td className={`px-2 py-1 font-semibold ${p["return_%"] >= 0 ? "text-alpha" : "text-loss"}`}>
                    {p["return_%"] >= 0 ? "+" : ""}{p["return_%"]}%
                  </td>
                  <td className="px-2 py-1 text-ink-muted">{p.days}d</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
  );
}
