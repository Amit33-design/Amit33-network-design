// "When do the picks work?" — does anything known on the pick date separate
// the scan days that beat SPY from the ones that did not? Computed in
// backend/date_conditions.py; shown as measured, including when the answer
// is "nothing does".
import type { Judged } from "../lib/evidence";

const pp = (x: number | null) => (x == null ? "—" : `${x >= 0 ? "+" : ""}${x.toFixed(2)}pp`);
const pct = (x: number | null) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export default function PickDateConditions({ judged }: { judged: Judged | null }) {
  const pdc = judged?.pick_date_conditions;
  if (!judged) return <div className="text-xs text-ink-muted">Loading…</div>;
  if (!pdc?.conditions?.length) {
    return <div className="text-xs text-ink-muted">
      Not computed yet — it is built with the track record after the next daily scan.
    </div>;
  }
  const s = judged.summary;
  const anyNotable = pdc.conditions.some((c) => c.notable);
  return (
    <div className="space-y-3">
      <div className="text-xs text-ink-secondary">
        Overall: {s?.dates ?? "—"} scan dates, average {pp(s?.["avg_alpha_%"] ?? null)} vs SPY per pick,
        {" "}{pct(s?.dates_beating_spy ?? null)} of dates beat SPY
        {s?.alpha_t_by_date != null && <> (t = {s.alpha_t_by_date} across dates)</>}.
        {" "}If a condition known <i>on the pick date</i> separated the good days from the bad,
        it would tell you when to act and when to sit out.
      </div>
      <div className={`rounded-panel border px-3 py-2 text-xs ${anyNotable
        ? "border-gain/30 bg-gain-soft text-gain" : "border-line bg-surface-sunken text-ink-secondary"}`}>
        {anyNotable
          ? "At least one condition measurably separates good days from bad — see below. Still a short history: treat it as a lead to keep testing, not a rule."
          : pdc.conditions.some((c) => c.suggestive)
            ? "Nothing clears the bar yet. One condition is suggestive (amber) — a lead the record keeps testing as dates accumulate, not a rule to trade on."
            : "None of these conditions measurably predicts which days work. There is no evidence-based \"sit today out\" signal yet — say so, rather than invent one."}
      </div>
      <div className="overflow-x-auto thin-scroll">
        <table className="table-data">
          <thead>
            <tr>
              <th>Condition on the pick date</th>
              <th className="text-right">When true</th>
              <th className="text-right">When false</th>
              <th className="text-right">Difference</th>
            </tr>
          </thead>
          <tbody>
            {pdc.conditions.map((c) => (
              <tr key={c.key}>
                <td className="max-w-[280px]">
                  <div className="text-ink">{c.question}</div>
                  <div className={`text-2xs ${c.notable ? "text-gain" : c.suggestive ? "text-warn" : "text-ink-muted"}`}>{c.verdict}</div>
                </td>
                {[c.yes, c.no].map((sd, i) => (
                  <td key={i} className="text-right num text-xs">
                    <div className={(sd["avg_alpha_%"] ?? 0) >= 0 ? "text-gain" : "text-loss"}>{pp(sd["avg_alpha_%"])}</div>
                    <div className="text-2xs text-ink-muted">{sd.dates} dates · {pct(sd.dates_beating_spy)} beat</div>
                  </td>
                ))}
                <td className="text-right num text-xs">
                  <span className={c.notable ? "text-gain font-semibold" : c.suggestive ? "text-warn font-semibold" : "text-ink-muted"}>
                    t = {c.diff_t ?? "—"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pdc.method && <div className="text-2xs text-ink-muted">{pdc.method}</div>}
    </div>
  );
}
