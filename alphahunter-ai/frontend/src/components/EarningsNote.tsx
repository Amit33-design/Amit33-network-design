// Next report date and the last result, under the trade plan. A stop-loss
// does not protect a position through an earnings report.
import { earningsRisk, prettyDate, useEarnings } from "../lib/earnings";

export default function EarningsNote({ ticker, horizon = 10 }: { ticker: string; horizon?: number }) {
  const cal = useEarnings();
  const e = cal?.[ticker.toUpperCase()];
  if (!e) return null;
  const r = earningsRisk(e, horizon);
  // Same rule as the backend, so the file written before it existed is safe:
  // a "last" report older than ~2 quarters is not the latest result.
  const last = e.last && (Date.now() - new Date(e.last.date + "T00:00:00").getTime()) / 86400000 <= 200
    ? e.last : null;
  return (
    <div className={`mt-2 text-2xs rounded border px-2 py-1.5 ${r?.insideWindow
      ? "border-warn/40 bg-warn-soft text-warn" : "border-line text-ink-secondary"}`}>
      <span className="font-semibold">📅 Earnings: </span>
      {r ? <>next report <b>{prettyDate(r.next)}</b> ({r.sessions === 0 ? "today" : `in ${r.sessions} session${r.sessions === 1 ? "" : "s"}`})</>
         : <>no upcoming date published</>}
      {last && (
        <> · last {prettyDate(last.date)}
          {last.surprise_pct != null && <>: {last.surprise_pct >= 0 ? "beat" : "missed"} estimates by{" "}
            <b>{Math.abs(last.surprise_pct).toFixed(1)}%</b></>}
        </>
      )}
      {r?.insideWindow && (
        <div className="mt-0.5">
          The report falls inside this plan's {horizon}-session window. A stop cannot protect against an
          overnight earnings gap — the stock can open past it. Size down, or wait until after the report.
        </div>
      )}
    </div>
  );
}
