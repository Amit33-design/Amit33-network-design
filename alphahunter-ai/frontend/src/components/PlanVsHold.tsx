// Is the exit plan helping? Each screen's picks judged two ways on the same
// trades: the product's exit plan (stop / target / trail / 10-day review) and
// simply holding 10 sessions. A screen that trails SPY under the plan but not
// when held is picking fine stocks and exiting them badly — a different fix
// from a screen that picks bad stocks.
import type { Judged } from "../lib/evidence";

const pp = (x: number | null | undefined) => (x == null ? "—" : `${x >= 0 ? "+" : ""}${x.toFixed(2)}pp`);
const NAMES: Record<string, string> = {
  opportunity: "Pullbacks (Opportunities)", crash: "Strict crash", growth: "Growth leaders", moonshot: "Moonshots",
};

export default function PlanVsHold({ judged }: { judged: Judged | null }) {
  const rows = Object.entries(judged?.by_screen ?? {}).filter(([, r]) => r?.held_instead);
  if (!judged) return <div className="text-xs text-ink-muted">Loading…</div>;
  if (!rows.length) return <div className="text-xs text-ink-muted">Computed with the track record after the next daily scan.</div>;
  return (
    <div>
      <div className="text-xs text-ink-secondary mb-2">
        Same picks, two ways to trade them: the exit plan, or just holding 10 sessions. Alpha is per
        trade vs SPY over the same days. A big gap in favour of holding means the stops are cutting
        winners early for that kind of stock.
      </div>
      <div className="overflow-x-auto thin-scroll">
        <table className="table-data">
          <thead><tr>
            <th>Screen</th><th className="text-right">Exit plan</th><th className="text-right">Held 10 days</th>
            <th className="text-right">Holding − plan</th><th className="text-right">Sample</th>
          </tr></thead>
          <tbody>
            {rows.map(([k, r]) => {
              const h = r.held_instead!;
              const gap = h.hold_minus_plan_pp;
              const thin = h.dates < 10;
              return (
                <tr key={k}>
                  <td className="text-ink">{NAMES[k] ?? k}</td>
                  <td className={`text-right num ${(h["plan_avg_alpha_%"] ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>{pp(h["plan_avg_alpha_%"])}</td>
                  <td className={`text-right num ${(h["avg_alpha_%"] ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>
                    {pp(h["avg_alpha_%"])}
                    {h.alpha_t_by_date != null && <div className="text-2xs text-ink-muted">t = {h.alpha_t_by_date}</div>}
                  </td>
                  <td className={`text-right num ${gap == null ? "" : gap > 1 ? "text-warn font-semibold" : "text-ink-secondary"}`}>{pp(gap)}</td>
                  <td className={`text-right num text-2xs ${thin ? "text-warn" : "text-ink-muted"}`}>
                    {h.trades} trades · {h.dates} dates{thin ? " (thin)" : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-2 text-2xs text-ink-muted">
        Fewer than 10 scan dates is one stretch of market — read it as a question, not an answer.
      </div>
    </div>
  );
}
