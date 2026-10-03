// What this verdict has historically been worth. The Analysis page showed
// Buy/Hold/Sell on every ticker without a measurement behind it; this reads
// the weekly walk-forward test (api/_verdict_eval.js → verdict_eval.json),
// which ran the same logic at past dates and recorded the next 20 sessions.
import { useEffect, useState } from "react";

type VerdictStat = {
  cases: number; dates: number; "avg_alpha_%": number; beat_spy_rate: number;
  alpha_t_by_date: number | null;
};
type Eval = {
  generated: string | null; tickers?: number;
  params?: { horizon_sessions: number };
  period?: { from: string; to: string } | null;
  by_verdict: Record<string, VerdictStat>;
  score_ic?: number | null; score_ic_t?: number | null;
};

let cache: Promise<Eval | null> | null = null;
function useVerdictEval() {
  const [e, setE] = useState<Eval | null>(null);
  useEffect(() => {
    cache ??= fetch("/verdict_eval.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    cache.then(setE);
  }, []);
  return e;
}

/** Plain-English read of one verdict's record. Pure. */
export function readVerdict(s: VerdictStat | undefined, horizon = 20): { tone: string; text: string } | null {
  if (!s || s.cases < 30) return null;
  const a = s["avg_alpha_%"], t = s.alpha_t_by_date;
  const body = `${a >= 0 ? "+" : ""}${a.toFixed(1)}pp vs SPY over the next ${horizon} sessions on average, `
    + `beating it ${Math.round(s.beat_spy_rate * 100)}% of the time (${s.cases.toLocaleString()} cases, ${s.dates} dates`
    + (t != null ? `, t = ${t}` : "") + ").";
  if (t != null && t >= 2) return { tone: "text-gain", text: `has worked — ${body}` };
  if (t != null && t <= -2) return { tone: "text-loss", text: `has lagged the market — ${body}` };
  return { tone: "text-ink-secondary", text: `has shown no measurable edge — ${body}` };
}

export default function VerdictEvidence({ verdict }: { verdict?: string }) {
  const e = useVerdictEval();
  if (!e?.generated || !verdict) return null;
  const r = readVerdict(e.by_verdict[verdict], e.params?.horizon_sessions ?? 20);
  if (!r) return null;
  return (
    <div className="w-full text-2xs text-ink-muted"
         title={`Walk-forward test of this page's own logic on ${e.tickers ?? "?"} stocks`
           + (e.period ? `, ${e.period.from} to ${e.period.to}` : "")
           + `. Today's listed stocks only, so absolute returns are flattered; compare verdicts with each other.`}>
      <span className="font-semibold text-ink-secondary">Track record: </span>
      past <b>{verdict}</b> verdicts from this logic <span className={r.tone}>{r.text}</span>
    </div>
  );
}
