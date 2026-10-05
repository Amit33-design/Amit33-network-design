// Strategy lab: whole strategies, after costs, scored on the research brief's
// quality checklist (backend/strategy_lab.py). Ranked by checks passed, then
// net Sharpe. Nothing here is a recommendation until it passes the checklist.
import { Fragment, useEffect, useMemo, useState } from "react";
import Plot from "./LazyPlot";
import { chartColors, getTheme, onThemeChange, plotTheme } from "../lib/theme";

type M = Record<string, any>;
type S = {
  key: string; name: string; thesis: string; in_sample: boolean; rule: string;
  net: M; gross: M; avg_holdings: number; avg_turnover_pct?: number; "avg_turnover_%": number;
  "cost_drag_ann_%": number; checks: Record<string, boolean>; passed: number; of: number;
  "first_half_alpha_%": number; "second_half_alpha_%": number;
  "regime_alpha_%": Record<string, number | null>; "variant_alpha_%": (number | null)[];
};
type Lab = {
  generated: string | null; strategies: S[]; benchmarks: Record<string, M>; dates: string[];
  periods?: number; universe_avg?: number; assumptions?: M; caveats?: string[];
};

const CHECK_LABEL: Record<string, string> = {
  beats_spy_after_costs: "Beats SPY after costs (t ≥ 2)",
  sharpe_above_1: "Sharpe > 1",
  drawdown_under_30: "Max drawdown better than −30%",
  both_halves: "Positive alpha in both halves",
  both_regimes: "Positive in up and down markets",
  not_parameter_dependent: "Survives half / double the selection",
};

export function useStrategyLab(): Lab | null {
  const [d, setD] = useState<Lab | null>(null);
  useEffect(() => {
    fetch("/strategy_lab.json").then((r) => (r.ok ? r.json() : null)).then(setD).catch(() => setD(null));
  }, []);
  return d;
}

const n = (x: any, suf = "", d = 1) => (x == null ? "—" : `${Number(x).toFixed(d)}${suf}`);

export default function StrategyLab({ data }: { data: Lab | null }) {
  const [theme, setTheme] = useState(getTheme);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => onThemeChange(() => setTheme(getTheme())), []);
  const C = chartColors(theme);
  const curves = useMemo(() => {
    if (!data?.generated) return [];
    const spy = data.benchmarks?.SPY;
    const ew = data.benchmarks?.equal_weight_universe;
    return [
      ...data.strategies.slice(0, 4).map((s, i) => ({ x: data.dates, y: s.net.curve, type: "scatter", mode: "lines",
        name: s.name, line: { width: 1.6, color: C.series[i % C.series.length] } })),
      ...(spy ? [{ x: data.dates, y: spy.curve, type: "scatter", mode: "lines", name: "SPY", line: { width: 2, color: "#888", dash: "dot" } }] : []),
      ...(ew ? [{ x: data.dates, y: ew.curve, type: "scatter", mode: "lines", name: "Equal-weight universe", line: { width: 1.2, color: "#aaa", dash: "dash" } }] : []),
    ];
  }, [data, theme]);

  if (!data) return <div className="text-xs text-ink-muted">Loading…</div>;
  if (!data.generated) return <div className="text-xs text-ink-muted">The weekly strategy lab has not run yet.</div>;
  const spy = data.benchmarks?.SPY || {};
  const passedAll = data.strategies.filter((s) => s.passed === s.of && !s.in_sample);
  const a = data.assumptions || {};

  return (
    <div className="space-y-3">
      <div className="text-xs text-ink-secondary">
        Seven pre-stated strategies on ~{data.universe_avg} tradeable stocks over {data.periods} non-overlapping
        {" "}{a.hold_sessions}-session periods, equal weight, <b>{a.cost_bps_one_way} bps charged per side</b> on every
        dollar traded, names under ${a.min_price} or ${(a.min_dollar_volume / 1e6).toFixed(0)}M daily dollar volume
        excluded. SPY over the same periods: CAGR {n(spy["cagr_%"], "%")}, Sharpe {n(spy.sharpe, "", 2)},
        max drawdown {n(spy["max_drawdown_%"], "%")}.
      </div>
      <div className={`text-xs rounded-panel border px-3 py-2 ${passedAll.length
        ? "border-gain/30 bg-gain-soft text-gain" : "border-line bg-surface-sunken text-ink-secondary"}`}>
        {passedAll.length
          ? <>Passed every quality check: <b>{passedAll.map((s) => s.name).join(", ")}</b>.</>
          : <>No strategy passes every quality check yet. Ranked below by checks passed, then risk-adjusted return after costs.</>}
      </div>

      <div className="overflow-x-auto thin-scroll">
        <table className="table-data">
          <thead><tr>
            <th>Strategy</th><th className="text-right">Checks</th><th className="text-right">CAGR</th>
            <th className="text-right">Sharpe</th><th className="text-right">Sortino</th><th className="text-right">Max DD</th>
            <th className="text-right">Alpha /yr (t)</th><th className="text-right">Profit factor</th><th className="text-right">Cost drag</th>
          </tr></thead>
          <tbody>
            {data.strategies.map((s) => (
              <Fragment key={s.key}>
                <tr className="cursor-pointer" onClick={() => setOpen(open === s.key ? null : s.key)}>
                  <td className="text-ink text-xs">
                    <span className="mr-1 text-ink-muted">{open === s.key ? "▾" : "▸"}</span>{s.name}
                    {s.in_sample && <span className="ml-1 text-2xs text-warn">in-sample</span>}
                  </td>
                  <td className={`text-right num text-xs ${s.passed === s.of ? "text-gain font-semibold" : s.passed >= 4 ? "text-warn" : "text-ink-muted"}`}>{s.passed}/{s.of}</td>
                  <td className="text-right num text-xs">{n(s.net["cagr_%"], "%")}</td>
                  <td className="text-right num text-xs">{n(s.net.sharpe, "", 2)}</td>
                  <td className="text-right num text-xs">{n(s.net.sortino, "", 2)}</td>
                  <td className="text-right num text-xs text-loss">{n(s.net["max_drawdown_%"], "%")}</td>
                  <td className={`text-right num text-xs ${(s.net["alpha_ann_%"] ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>
                    {n(s.net["alpha_ann_%"], "%")} <span className="text-ink-muted">({n(s.net.alpha_t, "", 2)})</span>
                  </td>
                  <td className="text-right num text-xs">{n(s.net.profit_factor, "", 2)}</td>
                  <td className="text-right num text-xs text-ink-muted">{n(s["cost_drag_ann_%"], "%/yr", 2)}</td>
                </tr>
                {open === s.key && (
                  <tr><td colSpan={9} className="text-2xs text-ink-secondary">
                    <div className="mb-1"><b className="text-ink">Thesis:</b> {s.thesis} <span className="text-ink-muted">Rule: {s.rule}.</span></div>
                    <div className="grid sm:grid-cols-2 gap-x-6 gap-y-0.5">
                      {Object.entries(s.checks).map(([k, ok]) => (
                        <div key={k} className={ok ? "text-gain" : "text-loss"}>{ok ? "✓" : "✗"} {CHECK_LABEL[k] ?? k}</div>
                      ))}
                    </div>
                    <div className="mt-1 text-ink-muted">
                      Alpha per period: first half {n(s["first_half_alpha_%"], "%", 2)}, second half {n(s["second_half_alpha_%"], "%", 2)} ·
                      {" "}S&P up-trend {n(s["regime_alpha_%"]?.up, "%", 2)}, down-trend {n(s["regime_alpha_%"]?.down, "%", 2)} ·
                      {" "}half/double selection {s["variant_alpha_%"].map((x) => n(x, "%", 2)).join(" / ")} ·
                      {" "}before costs CAGR {n(s.gross["cagr_%"], "%")}, Sharpe {n(s.gross.sharpe, "", 2)} ·
                      {" "}~{s.avg_holdings} holdings, {n(s["avg_turnover_%"], "%")} turnover per rebalance · win rate vs SPY {n((s.net.win_rate_vs_spy ?? 0) * 100, "%", 0)}
                    </div>
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {curves.length > 0 && (
        <Plot data={curves as any}
          layout={{ ...plotTheme(theme), autosize: true, height: 300, margin: { l: 44, r: 10, t: 10, b: 30 },
                    legend: { orientation: "h", y: -0.18 }, yaxis: { ...plotTheme(theme).yaxis, title: { text: "Growth of $1, after costs" } } } as any}
          useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }} />
      )}
      <ul className="text-2xs text-ink-muted list-disc pl-4 space-y-0.5">
        {(data.caveats || []).map((c) => <li key={c}>{c}</li>)}
      </ul>
    </div>
  );
}
