// Strategy backtest — the equity curve of a mechanical "buy the top N picks
// each scan day, hold H trading days" book against SPY over the same days.
// The Track Record section answers "how did individual picks do?"; this
// answers the different and more honest question "would running this have
// made money?".
import { useEffect, useState } from "react";
import Plot from "react-plotly.js";
import { StatTile, Badge } from "./ui";
import { chartColors, getTheme, onThemeChange, plotTheme } from "../lib/theme";

type Trade = { ticker: string; entry_date: string; exit_date: string; "return_%": number };
export type Backtest = {
  error?: string;
  params?: { top_n: number; hold_days: number; benchmark: string };
  start?: string; end?: string;
  trades?: number;
  "strategy_return_%"?: number;
  "benchmark_return_%"?: number;
  "alpha_%"?: number;
  "max_drawdown_%"?: number;
  "benchmark_max_drawdown_%"?: number;
  trade_win_rate?: number | null;
  "avg_trade_%"?: number | null;
  best_trade?: Trade | null;
  worst_trade?: Trade | null;
  sweep?: {
    error?: string;
    split_date?: string;
    best_in_sample?: { top_n: number; hold_days: number; "alpha_%": number };
    out_of_sample?: {
      top_n: number; hold_days: number;
      "alpha_%"?: number | null; trades?: number;
    };
    held_up?: boolean;
  };
  points?: { date: string; strategy: number; benchmark: number; positions: number }[];
};

const pct = (v?: number | null) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

/** Loads backtest.json. Returns null until CI has generated it, so callers can
 *  hide the section entirely rather than render an empty panel. */
export function useBacktest(): Backtest | null {
  const [bt, setBt] = useState<Backtest | null>(null);
  useEffect(() => {
    fetch("/backtest.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setBt(d?.points?.length ? d : null))
      .catch(() => setBt(null));
  }, []);
  return bt;
}

export default function BacktestPanel({ bt }: { bt: Backtest }) {
  const [theme, setTheme] = useState(getTheme);
  useEffect(() => onThemeChange(() => setTheme(getTheme())), []);

  if (!bt?.points?.length) return null;
  const C = chartColors(theme);
  const p = bt.params;
  const alpha = bt["alpha_%"] ?? 0;
  const beat = alpha >= 0;

  // Plot as % from the start so both lines share one readable axis.
  const x = bt.points.map((d) => d.date);
  const toPct = (k: "strategy" | "benchmark") =>
    bt.points!.map((d) => (d[k] - 1) * 100);

  return (
    <div className="space-y-3">
      <div className="text-xs text-ink-muted">
        A mechanical book: every scan day buy the top <b>{p?.top_n}</b> picks
        equal-weight and hold <b>{p?.hold_days}</b> trading days, overlapping.
        {" "}{p?.benchmark ?? "SPY"} is compounded over the exact same days, so
        this is not flattered by sitting in cash during a selloff.
        {" "}<b>{bt.trades}</b> trades, {bt.start} → {bt.end}.
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Strategy" value={pct(bt["strategy_return_%"])}
          tone={(bt["strategy_return_%"] ?? 0) >= 0 ? "gain" : "loss"} />
        <StatTile label={p?.benchmark ?? "SPY"} value={pct(bt["benchmark_return_%"])}
          tone={(bt["benchmark_return_%"] ?? 0) >= 0 ? "gain" : "loss"} />
        <StatTile label="Alpha" value={pct(alpha)} tone={beat ? "gain" : "loss"}
          sub={beat ? "ahead of the market" : "behind the market"} />
        <StatTile label="Max drawdown" value={pct(bt["max_drawdown_%"])} tone="loss"
          sub={`${p?.benchmark ?? "SPY"} ${pct(bt["benchmark_max_drawdown_%"])}`} />
      </div>

      <div className="panel p-2">
        <Plot
          data={[
            { x, y: toPct("strategy"), type: "scatter", mode: "lines", name: "Strategy",
              line: { color: C.gain, width: 2 }, hovertemplate: "%{x}<br>%{y:.2f}%<extra>Strategy</extra>" },
            { x, y: toPct("benchmark"), type: "scatter", mode: "lines",
              name: p?.benchmark ?? "SPY",
              line: { color: C.axis, width: 1.5, dash: "dot" },
              hovertemplate: `%{x}<br>%{y:.2f}%<extra>${p?.benchmark ?? "SPY"}</extra>` },
          ] as any}
          layout={{
            ...plotTheme(theme),
            height: 280,
            margin: { l: 46, r: 12, t: 8, b: 34 },
            showlegend: true,
            legend: { orientation: "h", y: 1.12, x: 0 },
            yaxis: { ...(plotTheme(theme) as any).yaxis, ticksuffix: "%", zeroline: true,
                     zerolinecolor: C.axis },
            hovermode: "x unified",
          } as any}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%" }}
          useResizeHandler
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-secondary">
        {bt.trade_win_rate != null && (
          <Badge tone={bt.trade_win_rate >= 0.5 ? "gain" : "loss"}>
            {(bt.trade_win_rate * 100).toFixed(0)}% of trades profitable
          </Badge>
        )}
        {bt["avg_trade_%"] != null && (
          <Badge tone={bt["avg_trade_%"] >= 0 ? "gain" : "loss"}>
            avg trade {pct(bt["avg_trade_%"])}
          </Badge>
        )}
        {bt.best_trade && (
          <span>best <b className="text-gain">{bt.best_trade.ticker} {pct(bt.best_trade["return_%"])}</b></span>
        )}
        {bt.worst_trade && (
          <span>worst <b className="text-loss">{bt.worst_trade.ticker} {pct(bt.worst_trade["return_%"])}</b></span>
        )}
      </div>

      {/* Walk-forward check: a grid search picked on the first half of the
          history, then re-run untouched on the second. The unseen number is
          the one worth believing. */}
      {bt.sweep?.out_of_sample?.["alpha_%"] != null && (
        <div className="text-xs text-ink-secondary border-t border-line pt-2">
          <span className="label-eyebrow">Walk-forward check</span>{" "}
          Tuning <b>top {bt.sweep.best_in_sample?.top_n} / {bt.sweep.best_in_sample?.hold_days}d</b>{" "}
          on scans before {bt.sweep.split_date} and re-running it on the unseen
          half gave{" "}
          <b className={bt.sweep.held_up ? "text-gain" : "text-loss"}>
            {pct(bt.sweep.out_of_sample["alpha_%"])} alpha
          </b>{" "}
          over {bt.sweep.out_of_sample.trades} trades — versus{" "}
          {pct(bt.sweep.best_in_sample?.["alpha_%"])} on the data it was chosen from.{" "}
          {bt.sweep.held_up
            ? "The edge survived data it had never seen."
            : "The in-sample edge did not survive, so treat the tuning as noise."}
        </div>
      )}

      {!beat && (
        <div className="text-xs text-warn border border-warn/30 bg-warn-soft rounded-panel px-3 py-2">
          Over this window the mechanical book <b>trailed {p?.benchmark ?? "SPY"} by {Math.abs(alpha).toFixed(1)} points</b>.
          Shown as measured rather than hidden — the picks are research input, and
          buying the index would have done better over these {bt.trades} trades.
        </div>
      )}
    </div>
  );
}
