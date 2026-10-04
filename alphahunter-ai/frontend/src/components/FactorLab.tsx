// Factor lab: candidate ingredients for the Analysis verdict, each tested
// point-in-time with overlap-corrected, split-half statistics
// (backend/factor_study.py). Only a "candidate" may be wired into the verdict.
import { useEffect, useState } from "react";

type HStat = {
  verdict: "candidate" | "lead" | "no_signal" | "wrong_sign" | "insufficient" | "collecting";
  why: string; ic?: number; t?: number | null; spread_pp?: number; dates?: number;
  first_half?: { t: number | null }; second_half?: { t: number | null }; matured_logs?: number;
};
type Factor = { key: string; hypothesis: string; expected_sign: number; h20: HStat; h60: HStat };
export type FactorStudy = {
  generated: string | null; stocks?: number; cutoffs?: number; period?: [string, string] | null;
  factors: Factor[]; revisions?: { logs: number; factors: Factor[] }; method?: string;
};

const TONE: Record<HStat["verdict"], string> = {
  candidate: "text-gain font-semibold", lead: "text-warn", no_signal: "text-ink-muted",
  wrong_sign: "text-loss", insufficient: "text-ink-muted", collecting: "text-ink-muted",
};
const LABEL: Record<HStat["verdict"], string> = {
  candidate: "✓ candidate", lead: "lead", no_signal: "no signal", wrong_sign: "wrong sign",
  insufficient: "too little data", collecting: "collecting",
};

export function useFactorStudy(): FactorStudy | null {
  const [d, setD] = useState<FactorStudy | null>(null);
  useEffect(() => {
    fetch("/factor_study.json").then((r) => (r.ok ? r.json() : null)).then(setD).catch(() => setD(null));
  }, []);
  return d;
}

function Cell({ s }: { s: HStat }) {
  return (
    <td className="text-right num text-xs align-top" title={s.why}>
      <div className={TONE[s.verdict]}>{LABEL[s.verdict]}</div>
      {s.t != null && (
        <div className="text-2xs text-ink-muted">
          IC {s.ic?.toFixed(3)} · t {s.t}
          {s.first_half?.t != null && <> · halves {s.first_half.t}/{s.second_half?.t}</>}
        </div>
      )}
      {s.spread_pp != null && <div className="text-2xs text-ink-muted">top−bottom 5th {s.spread_pp >= 0 ? "+" : ""}{s.spread_pp}pp</div>}
      {s.verdict === "collecting" && <div className="text-2xs text-ink-muted">{s.matured_logs ?? 0} logs matured</div>}
    </td>
  );
}

function Table({ rows }: { rows: Factor[] }) {
  return (
    <div className="overflow-x-auto thin-scroll">
      <table className="table-data">
        <thead><tr><th>Ingredient and why it might work</th><th className="text-right">Next 20 sessions</th><th className="text-right">Next 60 sessions</th></tr></thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f.key}>
              <td className="max-w-[340px]">
                <div className="text-ink text-xs font-medium">{f.key.replace(/_/g, " ")}</div>
                <div className="text-2xs text-ink-muted">{f.hypothesis} (expected {f.expected_sign > 0 ? "positive" : "negative"})</div>
              </td>
              <Cell s={f.h20} /><Cell s={f.h60} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function FactorLab({ data }: { data: FactorStudy | null }) {
  if (!data) return <div className="text-xs text-ink-muted">Loading…</div>;
  if (!data.generated) return <div className="text-xs text-ink-muted">The weekly factor study has not run yet.</div>;
  const cands = data.factors.flatMap((f) => ["h20", "h60"].filter((h) => (f as any)[h].verdict === "candidate").map((h) => `${f.key} (${h.slice(1)}d)`));
  return (
    <div className="space-y-3">
      <div className="text-xs text-ink-secondary">
        The Analysis verdict's chart ingredients were measured and carry no information. These are
        different kinds of ingredients, each a published anomaly, tested on {data.stocks} stocks at{" "}
        {data.cutoffs} past dates{data.period ? ` (${data.period[0]} → ${data.period[1]})` : ""}, using only
        what was known on each date. An ingredient enters the verdict only as a <b className="text-gain">candidate</b>:
        right direction, |t| ≥ 2.5 after correcting for ~10 tests, and confirmed in the second half on its own.
      </div>
      <div className={`text-xs rounded-panel border px-3 py-2 ${cands.length
        ? "border-gain/30 bg-gain-soft text-gain" : "border-line bg-surface-sunken text-ink-secondary"}`}>
        {cands.length
          ? <>Passed: <b>{cands.join(", ")}</b>. Eligible to be added to the verdict — and re-measured after.</>
          : <>Nothing has passed yet. The verdict stays as it is rather than being re-weighted on noise.</>}
      </div>
      <Table rows={data.factors} />
      {data.revisions && data.revisions.factors.length > 0 && (
        <>
          <div className="text-xs text-ink-secondary pt-2">
            <b className="text-ink">Analyst estimate revisions — forward test.</b> No free history of past estimates
            exists, so these are logged weekly from now on and judged as their outcomes arrive
            ({data.revisions.logs} weekly log{data.revisions.logs === 1 ? "" : "s"} so far).
          </div>
          <Table rows={data.revisions.factors} />
        </>
      )}
      {data.method && <div className="text-2xs text-ink-muted">{data.method}</div>}
    </div>
  );
}
