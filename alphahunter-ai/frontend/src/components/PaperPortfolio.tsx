// "$100 in every Buy" — the most literal answer to "are these picks any good?".
// Rank correlations and alpha are the right tools for judging a ranker, but
// this is the number a person actually asks for.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StatTile, Badge } from "./ui";

type Holding = {
  ticker: string; company?: string; first_buy: string; action: string;
  entry: number; now?: number | null; value?: number | null;
  pnl?: number | null; "return_%"?: number | null; priced: boolean;
  score?: number; quality_grade?: string; repeats: number;
};
export type Paper = {
  error?: string;
  stake?: number; positions?: number; priced?: number;
  invested?: number; value?: number; pnl?: number; "return_%"?: number | null;
  win_rate?: number | null; winners?: number; losers?: number;
  benchmark?: string; "benchmark_return_%"?: number; "benchmark_value"?: number;
  "alpha_%"?: number; beat_benchmark?: boolean;
  best?: Holding | null; worst?: Holding | null;
  by_score_band?: { band: string; n: number; "avg_return_%": number; win_rate: number }[];
  score_separates?: boolean;
  holdings?: Holding[];
  generated?: string;
};

const money = (v?: number | null) =>
  v == null ? "—" : `${v < 0 ? "-" : ""}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const pct = (v?: number | null) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

export function usePaper(): Paper | null {
  const [p, setP] = useState<Paper | null>(null);
  useEffect(() => {
    fetch("/paper.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setP(d?.holdings?.length ? d : null))
      .catch(() => setP(null));
  }, []);
  return p;
}

export default function PaperPortfolio({ p }: { p: Paper }) {
  const [showAll, setShowAll] = useState(false);
  if (!p.holdings?.length) return null;

  const up = (p["return_%"] ?? 0) >= 0;
  const beat = p.beat_benchmark;
  const shown = showAll ? p.holdings : p.holdings.slice(0, 12);

  return (
    <div className="space-y-3">
      <div className="text-xs text-ink-muted">
        Every time the system said <b>Buy</b> or <b>Accumulate</b>, ${p.stake} went in at
        that day's price — <b>{p.positions}</b> distinct names since the first scan,
        each funded <b>once</b> (a name the screen repeats is the same idea, not a
        new ${p.stake}). Everything is still held, valued at the latest price.
        {p.priced !== p.positions && (
          <> {(p.positions ?? 0) - (p.priced ?? 0)} could not be priced and are carried at cost.</>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Put in" value={money(p.invested)} sub={`${p.positions} × $${p.stake}`} />
        <StatTile label="Worth now" value={money(p.value)} tone={up ? "gain" : "loss"} />
        <StatTile label="Profit / loss" value={money(p.pnl)} tone={up ? "gain" : "loss"}
          sub={pct(p["return_%"])} />
        <StatTile
          label={`Same money in ${p.benchmark ?? "SPY"}`}
          value={pct(p["benchmark_return_%"])}
          tone={beat ? "gain" : "loss"}
          sub={p["alpha_%"] != null
            ? `${beat ? "we're ahead by" : "we're behind by"} ${Math.abs(p["alpha_%"]).toFixed(1)}pp`
            : undefined} />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-secondary">
        <Badge tone={(p.win_rate ?? 0) >= 0.5 ? "gain" : "loss"}>
          {p.winners} winners · {p.losers} losers
        </Badge>
        {p.best && <span>best <b className="text-gain">{p.best.ticker} {pct(p.best["return_%"])}</b></span>}
        {p.worst && <span>worst <b className="text-loss">{p.worst.ticker} {pct(p.worst["return_%"])}</b></span>}
      </div>

      {!beat && p["alpha_%"] != null && (
        <div className="text-xs text-warn border border-warn/30 bg-warn-soft rounded-panel px-3 py-2">
          Straight answer: ${p.invested?.toLocaleString()} spread across every Buy is worth{" "}
          <b>{money(p.value)}</b> ({pct(p["return_%"])}), while the same money put into{" "}
          {p.benchmark ?? "SPY"} on the same days would be{" "}
          <b>{pct(p["benchmark_return_%"])}</b>. <b>Picking these names lost to just
          buying the index by {Math.abs(p["alpha_%"]).toFixed(1)} points.</b>
        </div>
      )}

      {/* Does a higher AI score actually mean a better outcome? If not, the
          score is decoration and saying so is the honest thing to do. */}
      {p.by_score_band && p.by_score_band.length > 1 && (
        <div className="border-t border-line pt-2">
          <div className="label-eyebrow mb-1">Does the AI score predict the outcome?</div>
          <div className="flex flex-wrap gap-3 text-xs">
            {p.by_score_band.map((b) => (
              <span key={b.band} className="text-ink-secondary">
                <b className="text-ink">{b.band}</b>{" "}
                <span className="text-ink-muted">n={b.n}</span>{" "}
                <b className={b["avg_return_%"] >= 0 ? "text-gain" : "text-loss"}>
                  {pct(b["avg_return_%"])}
                </b>
              </span>
            ))}
          </div>
          <div className={`mt-1 text-xs ${p.score_separates ? "text-gain" : "text-warn"}`}>
            {p.score_separates
              ? "Higher-scored names did do better — the score is carrying real information."
              : "Higher-scored names did NOT do better. On this history the score does not separate winners from losers, so treat it as a filter for what the screen found, not as conviction."}
          </div>
        </div>
      )}

      <div className="overflow-x-auto thin-scroll">
        <table className="table-data">
          <thead>
            <tr>{["Ticker", "Bought", "Entry", "Now", "Value", "P/L", "Return", "Score"].map((h) =>
              <th key={h}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {shown.map((h) => (
              <tr key={h.ticker}>
                <td>
                  <Link to={`/analysis?ticker=${h.ticker}`}
                        className="font-semibold text-brand hover:underline">{h.ticker}</Link>
                  {h.repeats > 0 && (
                    <span className="ml-1 text-2xs text-ink-muted"
                          title={`Re-picked ${h.repeats} more times — not re-funded`}>
                      ×{h.repeats + 1}
                    </span>
                  )}
                </td>
                <td className="text-ink-muted text-xs whitespace-nowrap">{h.first_buy}</td>
                <td className="num">${h.entry}</td>
                <td className="num">{h.now != null ? `$${h.now}` : "—"}</td>
                <td className="num">{money(h.value)}</td>
                <td className={`num font-semibold ${(h.pnl ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>
                  {h.priced ? money(h.pnl) : <span className="text-ink-muted">unpriced</span>}
                </td>
                <td className={`num font-semibold ${(h["return_%"] ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>
                  {h.priced ? pct(h["return_%"]) : "—"}
                </td>
                <td className="text-ink-secondary">{h.score ?? "—"}{h.quality_grade ? ` · ${h.quality_grade}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {p.holdings.length > 12 && (
        <button onClick={() => setShowAll(!showAll)}
                className="text-xs text-brand hover:underline">
          {showAll ? "Show fewer" : `Show all ${p.holdings.length} positions`}
        </button>
      )}
    </div>
  );
}
