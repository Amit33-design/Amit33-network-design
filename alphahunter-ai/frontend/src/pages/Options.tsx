import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Recommendation } from "../lib/types";
import { ErrorBox, Loading } from "../components/Loading";

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
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-ink">Options Income</h1>
        <div className="flex gap-1 bg-white rounded-lg p-1 shadow-sm">
          <button
            onClick={() => setKind("coveredcalls")}
            className={`px-3 py-1 rounded text-sm ${
              kind === "coveredcalls" ? "bg-alpha text-white" : "text-slate-600"
            }`}
          >
            Covered Calls
          </button>
          <button
            onClick={() => setKind("csp")}
            className={`px-3 py-1 rounded text-sm ${
              kind === "csp" ? "bg-alpha text-white" : "text-slate-600"
            }`}
          >
            Cash-Secured Puts
          </button>
        </div>
      </div>

      {loading ? (
        <Loading label="Pulling option chains…" />
      ) : error ? (
        <ErrorBox error={error} />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rows.map((r) => (
            <div key={r.ticker} className="bg-white rounded-xl shadow-sm p-4">
              <div className="flex justify-between items-baseline">
                <span className="font-bold text-alpha text-lg">{r.ticker}</span>
                <span className="text-sm text-slate-500">Score {r.score.toFixed(0)}</span>
              </div>
              <div className="text-sm text-slate-600 mt-1">{r.company}</div>
              <div className="mt-3 text-sm bg-slate-50 rounded p-2">
                {kind === "coveredcalls" ? r.covered_call : r.cash_secured_put}
              </div>
              <div className="mt-2 text-xs text-slate-400">{r.confidence} confidence</div>
            </div>
          ))}
          {rows.length === 0 && (
            <div className="text-slate-500">No option ideas in the current scan.</div>
          )}
        </div>
      )}
    </div>
  );
}
