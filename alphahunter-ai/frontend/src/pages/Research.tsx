// Strategy research: tools for studying how a rule would have traded, as
// opposed to the Dashboard's "what is the market doing and what do I do today".
// They moved here from the Dashboard, which had grown to ~16 stacked blocks.
import { useEffect, useState } from "react";
import Plot from "../components/LazyPlot";
import { Section } from "../components/ui";
import BacktestPanel, { useBacktest } from "../components/BacktestPanel";
import PairTrader, { usePairStudy } from "../components/PairTrader";
import DeferUntilVisible from "../components/DeferUntilVisible";
import { chartColors, plotTheme, onThemeChange, getTheme } from "../lib/theme";
import PickDateConditions from "../components/PickDateConditions";
import { useJudged } from "../lib/evidence";

type Dash = { domains: Record<string, { score: number }[]> };

export default function Research() {
  const backtest = useBacktest();
  const pairStudy = usePairStudy();
  const judged = useJudged();
  const [dash, setDash] = useState<Dash | null>(null);
  const [theme, setTheme] = useState(getTheme);
  useEffect(() => onThemeChange(() => setTheme(getTheme())), []);
  useEffect(() => {
    fetch("/dashboard.json").then((r) => (r.ok ? r.json() : null)).then(setDash).catch(() => setDash(null));
  }, []);

  const all = dash ? Object.values(dash.domains).flat() : [];
  const buckets = [0, 20, 40, 50, 60, 70, 80].map((b, i, arr) => {
    const hi = arr[i + 1] ?? 101;
    return { label: `${b}-${hi === 101 ? 100 : hi}`, count: all.filter((s) => s.score >= b && s.score < hi).length };
  });

  return (
    <div>
      <div className="mb-5">
        <div className="label-eyebrow">Strategy research</div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Research</h1>
        <p className="text-xs text-ink-muted mt-1 max-w-2xl">
          How the rules would have traded, measured against SPY. Past results on a short
          history — read them as evidence for or against a rule, not as a forecast.
        </p>
      </div>

      {backtest && (
        <Section
          title="🧪 Strategy Backtest"
          subtitle={`top ${backtest.params?.top_n ?? 5} bought each scan day, held ${backtest.params?.hold_days ?? 10} trading days, vs ${backtest.params?.benchmark ?? "SPY"}`}
          badge={backtest["alpha_%"] != null
            ? `alpha ${backtest["alpha_%"] >= 0 ? "+" : ""}${backtest["alpha_%"]}pp`
            : undefined}
          badgeColor={(backtest["alpha_%"] ?? 0) >= 0 ? "#31a05c" : "#e2574c"}
          defaultOpen
        >
          <BacktestPanel bt={backtest} />
        </Section>
      )}

      <Section
        title="🗓 When do the picks work?"
        subtitle="does the market on the pick date predict which days beat SPY?"
        badge={judged?.pick_date_conditions?.conditions?.some((c) => c.notable) ? "pattern found" : undefined}
        badgeColor="#31a05c"
        defaultOpen
      >
        <PickDateConditions judged={judged} />
      </Section>

      {pairStudy && (
        <Section
          title="⚖️ Pair Trading"
          subtitle="hold two stocks at fixed weights — today's buy/sell order"
          badge={`${pairStudy.pairs.length} pairs`}
        >
          <PairTrader study={pairStudy} />
        </Section>
      )}

      {all.length > 0 && (
        <Section title="📊 Score distribution" subtitle="composite score across the watchlist">
          <DeferUntilVisible height={260}>
            <Plot
              data={[{ type: "bar", x: buckets.map((b) => b.label), y: buckets.map((b) => b.count),
                       marker: { color: chartColors(theme).series[0] } }]}
              layout={{ autosize: true, height: 260, margin: { l: 44, r: 12, t: 8, b: 40 },
                        ...plotTheme(theme),
                        xaxis: { ...plotTheme(theme).xaxis, title: { text: "Composite score" } },
                        yaxis: { ...plotTheme(theme).yaxis, title: { text: "Instruments" } } } as any}
              useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }}
            />
          </DeferUntilVisible>
        </Section>
      )}
    </div>
  );
}
