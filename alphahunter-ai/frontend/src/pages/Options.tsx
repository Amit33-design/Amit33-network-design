import { useEffect, useState } from "react";
import { api, isSnapshot } from "../lib/api";
import type { Recommendation } from "../lib/types";
import { ErrorBox, Loading } from "../components/Loading";
import SnapshotBanner from "../components/SnapshotBanner";

type Kind = "coveredcalls" | "csp";

export default function Options() {
  const [kind, setKind] = useState<Kind>("coveredcalls");
  const [rows, setRows] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    const call = kind === "coveredcalls" ? api.coveredCalls : api.csp;
    call(25)
      .then((r) => setRows(r.results))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [kind]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-semibold tracking-tight text-ink">Options Income</h1>
        <div className="flex gap-1 panel p-1">
          <button
            onClick={() => setKind("coveredcalls")}
            className={`px-3 py-1 rounded text-sm ${
              kind === "coveredcalls" ? "bg-brand text-white" : "text-ink-secondary"
            }`}
          >
            Covered Calls
          </button>
          <button
            onClick={() => setKind("csp")}
            className={`px-3 py-1 rounded text-sm ${
              kind === "csp" ? "bg-brand text-white" : "text-ink-secondary"
            }`}
          >
            Cash-Secured Puts
          </button>
        </div>
      </div>

      {!loading && isSnapshot() && <SnapshotBanner />}
      {loading ? (
        <Loading label="Pulling option chains…" />
      ) : error ? (
        <ErrorBox error={error} />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rows.map((r) => (
            <div key={r.ticker} className="panel p-4">
              <div className="flex justify-between items-baseline">
                <span className="font-bold text-brand text-lg">{r.ticker}</span>
                <span className="text-sm text-ink-secondary">Score {r.score.toFixed(0)}</span>
              </div>
              <div className="text-sm text-ink-secondary mt-1">{r.company}</div>
              <div className="mt-3 text-sm bg-surface-sunken rounded p-2">
                {kind === "coveredcalls" ? r.covered_call : r.cash_secured_put}
              </div>
              <div className="mt-2 text-xs text-ink-muted">{r.confidence} confidence</div>
            </div>
          ))}
          {rows.length === 0 && (
            <div className="md:col-span-2 lg:col-span-3 panel p-8 text-center">
              <div className="text-4xl mb-2">🧾</div>
              <div className="font-semibold text-ink">
                No {kind === "coveredcalls" ? "covered-call" : "cash-secured-put"} ideas in the latest scan
              </div>
              <div className="text-sm text-ink-secondary mt-1 max-w-md mx-auto">
                Option ideas come from the daily scan's qualifying names. When the market is
                calm the scan is thin — for a per-ticker cash-secured-put read, open the{" "}
                <b>Analysis</b> tab and enter any symbol (the CSP-on-dip signal there works live).
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
