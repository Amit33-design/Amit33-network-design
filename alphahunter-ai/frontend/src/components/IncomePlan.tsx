// Profit-target planner. A yearly income goal is arithmetic on three things:
// capital at work, the edge per trade, and trades per year. This uses the
// edge MEASURED from the system's own paper portfolio, so the answer is about
// this system rather than a hypothetical good one — and it does not flatter.
import { useEffect, useMemo, useState } from "react";
import { StatTile, Badge } from "./ui";

type Proj = {
  "edge_per_trade_%": number;
  "expected_annual_return_%": number;
  expected_annual_profit: number;
  range_low: number; range_high: number;
  profitable_edge: boolean;
};
export type IncomePlanData = {
  error?: string;
  edge?: { win_rate: number; avg_win_pct: number; avg_loss_pct: number; sample: number };
  as_measured?: Proj;
  with_stop_enforced?: Proj;
  stop_pct?: number;
};

const KEY = "alphahunter.plan";
const money = (v: number) =>
  `${v < 0 ? "-" : ""}$${Math.abs(Math.round(v)).toLocaleString()}`;

export function useIncomePlan(): IncomePlanData | null {
  const [d, setD] = useState<IncomePlanData | null>(null);
  useEffect(() => {
    fetch("/income_plan.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => setD(j?.edge ? j : null))
      .catch(() => setD(null));
  }, []);
  return d;
}

function load(k: string, fallback: number): number {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "{}");
    return Number.isFinite(raw[k]) ? raw[k] : fallback;
  } catch { return fallback; }
}
function save(patch: Record<string, number>) {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "{}");
    localStorage.setItem(KEY, JSON.stringify({ ...raw, ...patch }));
  } catch { /* private mode */ }
}

export default function IncomePlan({ d }: { d: IncomePlanData }) {
  const [capital, setCapital] = useState(() => load("capital", 25000));
  const [goal, setGoal] = useState(() => load("goal", 50000));
  const [useStop, setUseStop] = useState(true);

  useEffect(() => { save({ capital, goal }); }, [capital, goal]);

  const edge = d.edge!;
  const TRADES = 25, POSITIONS = 5;

  // Recomputed in the browser so the numbers move with YOUR capital, using the
  // same arithmetic as backend/income_plan.py.
  const calc = useMemo(() => {
    const avgLoss = useStop ? Math.abs(d.stop_pct ?? 7) : edge.avg_loss_pct;
    const perTrade = edge.win_rate * edge.avg_win_pct - (1 - edge.win_rate) * avgLoss;
    const positionSize = capital / POSITIONS;
    const expected = positionSize * (perTrade / 100) * TRADES;
    const perPositionAnnual = (perTrade / 100) * TRADES;
    const needed = perTrade > 0 ? (goal / perPositionAnnual) * POSITIONS : null;
    return {
      perTrade, expected, needed, avgLoss,
      annualPct: (expected / capital) * 100,
      requiredPct: (goal / capital) * 100,
      feasible: needed != null && needed <= capital,
    };
  }, [capital, goal, useStop, edge, d.stop_pct]);

  return (
    <div className="space-y-3">
      <div className="text-xs text-ink-muted">
        Built from this system's own record — <b>{edge.sample}</b> judged
        positions, <b>{(edge.win_rate * 100).toFixed(0)}%</b> winners, average
        win <b className="text-gain">+{edge.avg_win_pct.toFixed(1)}%</b>, average
        loss <b className="text-loss">−{edge.avg_loss_pct.toFixed(1)}%</b>.
        Assumes {POSITIONS} positions at a time and about {TRADES} completed
        trades a year.
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <label className="text-xs text-ink-secondary">
          <div className="label-eyebrow mb-1">Your capital</div>
          <input type="number" min={1000} step={1000} value={capital}
                 onChange={(e) => setCapital(Math.max(0, +e.target.value))}
                 className="px-2 py-1 w-36 num" />
        </label>
        <label className="text-xs text-ink-secondary">
          <div className="label-eyebrow mb-1">Yearly profit goal</div>
          <input type="number" min={0} step={5000} value={goal}
                 onChange={(e) => setGoal(Math.max(0, +e.target.value))}
                 className="px-2 py-1 w-36 num" />
        </label>
        <label className="text-xs text-ink-secondary flex items-center gap-2 pb-1">
          <input type="checkbox" checked={useStop}
                 onChange={(e) => setUseStop(e.target.checked)} />
          Cut every loss at {Math.abs(d.stop_pct ?? 7)}%
        </label>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Edge per trade" value={`${calc.perTrade >= 0 ? "+" : ""}${calc.perTrade.toFixed(2)}%`}
          tone={calc.perTrade > 0 ? "gain" : "loss"} />
        <StatTile label="Expected profit / yr" value={money(calc.expected)}
          tone={calc.expected > 0 ? "gain" : "loss"}
          sub={`${calc.annualPct >= 0 ? "+" : ""}${calc.annualPct.toFixed(1)}% on capital`} />
        <StatTile label="Your goal needs" value={`${calc.requiredPct.toFixed(0)}%`}
          tone={calc.requiredPct > 25 ? "loss" : "gain"} sub="annual return" />
        <StatTile label="Capital for that goal"
          value={calc.needed == null ? "—" : money(calc.needed)}
          tone={calc.feasible ? "gain" : "loss"}
          sub={calc.needed == null ? "edge is negative"
               : calc.feasible ? "you have enough" : `${(calc.needed / capital).toFixed(1)}× your capital`} />
      </div>

      <div className={`text-xs rounded-panel px-3 py-2 border ${
        calc.feasible ? "border-gain/30 bg-gain-soft text-gain"
                      : "border-warn/30 bg-warn-soft text-warn"}`}>
        {calc.perTrade <= 0 ? (
          <>The edge is negative at {calc.perTrade.toFixed(2)}% per trade, so no amount
          of capital reaches {money(goal)} a year — more money would only lose faster.
          The edge has to become positive first.</>
        ) : calc.feasible ? (
          <>Reachable: {money(capital)} at this edge expects about {money(calc.expected)} a
          year, which covers the {money(goal)} goal. Expect a wide spread around that
          — it is an average, not an income.</>
        ) : (
          <><b>{money(goal)} a year on {money(capital)} means a {calc.requiredPct.toFixed(0)}% annual
          return.</b> This edge expects {calc.annualPct.toFixed(1)}%, so the goal needs
          roughly {money(calc.needed!)} of capital — about {(calc.needed! / capital).toFixed(1)}× what
          you have. Sizing up to force the goal is how accounts get ruined. The honest
          options are more capital, more time, or a better edge.</>
        )}
      </div>

      {d.with_stop_enforced && d.as_measured && (
        <div className="border-t border-line pt-2 text-xs text-ink-secondary">
          <div className="label-eyebrow mb-1">Why the exit rule matters most</div>
          The average loss ({edge.avg_loss_pct.toFixed(1)}%) is currently{" "}
          <b>bigger than the average win</b> ({edge.avg_win_pct.toFixed(1)}%), which is why
          a {(edge.win_rate * 100).toFixed(0)}% win rate still nets almost nothing. Capping
          every loss at {Math.abs(d.stop_pct ?? 7)}% takes the edge from{" "}
          <Badge tone="loss">{d.as_measured["edge_per_trade_%"].toFixed(2)}%</Badge> to{" "}
          <Badge tone="gain">{d.with_stop_enforced["edge_per_trade_%"].toFixed(2)}%</Badge>{" "}
          per trade. That is arithmetic on the same names, not a backtest — a real stop
          also turns some dips that later recovered into realized losses — so treat it
          as the ceiling the discipline is worth, not a promise.
        </div>
      )}
    </div>
  );
}
