import { useEffect, useState } from "react";
import { api, isSnapshot } from "../lib/api";
import type { Recommendation } from "../lib/types";
import RecGrid from "../components/RecGrid";
import { ErrorBox, Loading } from "../components/Loading";
import SnapshotBanner from "../components/SnapshotBanner";

type Feed = "top" | "oversold" | "breakouts";

export default function Opportunities() {
  const [feed, setFeed] = useState<Feed>("top");
  const [rows, setRows] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [snap, setSnap] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError("");
    const call =
      feed === "top" ? api.marketTop : feed === "oversold" ? api.oversold : api.breakouts;
    call(100)
      .then((r) => {
        setRows(r.results);
        setSnap(isSnapshot());
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [feed]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-ink">Opportunities</h1>
        <div className="flex gap-1 bg-white rounded-lg p-1 shadow-sm">
          {(["top", "oversold", "breakouts"] as Feed[]).map((f) => (
            <button
              key={f}
              onClick={() => setFeed(f)}
              className={`px-3 py-1 rounded text-sm capitalize ${
                feed === f ? "bg-alpha text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      {snap && <SnapshotBanner />}
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox error={error} />
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm p-8 text-center">
          <div className="text-4xl mb-2">🌤️</div>
          <div className="font-semibold text-ink">No matching setups right now</div>
          <div className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
            The market is calm — nothing hit this screen in the latest scan. Try the{" "}
            <b>oversold</b> or <b>breakouts</b> tabs, check the <b>Dashboard</b> Top Picks,
            or analyze any ticker on the <b>Analysis</b> tab.
          </div>
        </div>
      ) : (
        <RecGrid rows={rows} />
      )}
    </div>
  );
}
