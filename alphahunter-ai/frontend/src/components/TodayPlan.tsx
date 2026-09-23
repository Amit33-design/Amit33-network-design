// Today's plan: decide, size, act, exit — in one place.
//
// The audit found eight dashboard sections and six separate lists of stocks,
// with buying on one page and exiting on another. It also found that no screen
// has yet proven itself at its exit plan — but ONE rule has out-of-sample
// evidence: take the top 5 names from each scan, hold them, and exit at the
// target or stop. So the plan is that rule applied to today, and it says
// plainly how strong (and how thin) that evidence is.
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "./ui";

type Pick = {
  ticker: string; company?: string; score: number; entry?: number | null;
  exit_plan?: { target: number; stop: number; horizon_days: number;
                target_pct: number; stop_pct: number } | null;
  entry_timing?: { action: "wait" | "buy_zone"; entry_target?: number | null;
                   reason?: string } | null;
};
type Backtest = {
  params?: { top_n: number; hold_days: number };
  "strategy_return_%"?: number; "benchmark_return_%"?: number;
  "max_drawdown_%"?: number; trades?: number; distinct_names?: number;
  sweep?: { out_of_sample?: { hold_days: number; "alpha_%": number; trades: number } | null;
            held_up?: boolean };
};

const TOP_N = 5;
const money = (v: number) => `$${Math.round(v).toLocaleString()}`;
const pct = (v?: number | null) => v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

function account(): number {
  try {
    const v = Number(localStorage.getItem("alphahunter.account"));
    return v > 0 ? v : 25000;
  } catch { return 25000; }
}

export default function TodayPlan({ positionScale = 1, regime }:
  { positionScale?: number; regime?: string }) {
  const [picks, setPicks] = useState<Pick[] | null>(null);
  const [bt, setBt] = useState<Backtest | null>(null);

  useEffect(() => {
    fetch("/snapshot.json").then((r) => (r.ok ? r.json() : null))
      .then((j) => setPicks(j?.results ?? [])).catch(() => setPicks([]));
    fetch("/backtest.json").then((r) => (r.ok ? r.json() : null))
      .then(setBt).catch(() => setBt(null));
  }, []);

  // The rule: top N by score. Names the range layer says to WAIT on are held
  // back rather than bought at the top of a year-long range.
  const { buys, waits } = useMemo(() => {
    const ranked = [...(picks ?? [])].sort((a, b) => b.score - a.score);
    const waits = ranked.slice(0, TOP_N).filter((p) => p.entry_timing?.action === "wait");
    const buys = ranked.slice(0, TOP_N).filter((p) => p.entry_timing?.action !== "wait");
    return { buys, waits };
  }, [picks]);

  if (!picks) return null;
  if (!picks.length) {
    return <div className="text-xs text-ink-muted">No scan results to plan from yet.</div>;
  }

  const acct = account();
  const perPosition = (acct / TOP_N) * positionScale;
  const oos = bt?.sweep?.out_of_sample;

  return (
    <div className="space-y-3">
      {/* The evidence first — what this rule has and has not proven. */}
      <div className="text-xs text-ink-secondary leading-relaxed">
        <b className="text-ink">The rule:</b> buy the top {TOP_N} from today's scan, then exit at each
        name's take-profit or stop, or review it after {buys[0]?.exit_plan?.horizon_days ?? 10} trading days.
        {bt?.["strategy_return_%"] != null && (
          <> Backtested, it returned <b className="text-gain">{pct(bt["strategy_return_%"])}</b> against
          SPY's {pct(bt["benchmark_return_%"])}
          {oos ? <>; picked on the first half of the history and run on the second,
            it held up at <b className="text-gain">{pct(oos["alpha_%"])} vs SPY</b> over {oos.trades} trades
            (best on a {oos.hold_days}-day hold)</> : null}.</>
        )}{" "}
        <span className="text-warn">
          That rests on about 2.5 months of data, with a{" "}
          {bt?.["max_drawdown_%"] != null ? `${bt["max_drawdown_%"].toFixed(0)}%` : "large"} drawdown along the way —
          it is the best evidence in this product, not a guarantee.
        </span>
      </div>

      <div className="overflow-x-auto thin-scroll">
        <table className="table-data">
          <thead>
            <tr>{["Buy", "At", "Take profit", "Stop", "Size", ""].map((h) => <th key={h}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {buys.map((p) => {
              const shares = p.entry ? Math.floor(perPosition / p.entry) : 0;
              return (
                <tr key={p.ticker}>
                  <td>
                    <Link to={`/analysis?ticker=${p.ticker}`} className="font-semibold text-brand hover:underline">
                      {p.ticker}
                    </Link>
                    <span className="ml-2 text-2xs text-ink-muted hidden sm:inline">{p.company}</span>
                  </td>
                  <td className="num">{p.entry ? `$${p.entry}` : "—"}</td>
                  <td className="num text-gain">
                    {p.exit_plan ? `$${p.exit_plan.target} (${pct(p.exit_plan.target_pct)})` : "—"}
                  </td>
                  <td className="num text-loss">
                    {p.exit_plan ? `$${p.exit_plan.stop} (${pct(p.exit_plan.stop_pct)})` : "—"}
                  </td>
                  <td className="num">
                    {shares > 0 ? `${shares} sh ≈ ${money(shares * (p.entry ?? 0))}` : "—"}
                  </td>
                  <td className="text-right">
                    <Badge tone="neutral">score {p.score}</Badge>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {waits.length > 0 && (
        <div className="text-xs text-warn">
          <b>Held back:</b>{" "}
          {waits.map((w) => `${w.ticker} (wait for ≈$${w.entry_timing?.entry_target})`).join(" · ")}
          {" "}— in the top {TOP_N}, but near the top of a year-long range.
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-ink-muted">
        <span>
          Sized as {money(acct)} ÷ {TOP_N}
          {positionScale < 1 ? ` × ${Math.round(positionScale * 100)}% for a ${regime} market` : ""}
          {" "}= <b className="text-ink-secondary">{money(perPosition)}</b> per position.
        </span>
        <Link to="/portfolio" className="text-brand hover:underline">
          Check what to exit in your holdings →
        </Link>
      </div>
    </div>
  );
}
