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
      {loading ? <Loading /> : error ? <ErrorBox error={error} /> : <RecGrid rows={rows} />}
    </div>
  );
}
