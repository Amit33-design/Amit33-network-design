import { useEffect, useMemo, useState } from "react";
import { api, isSnapshot } from "../lib/api";
import type { Recommendation } from "../lib/types";
import RecGrid from "../components/RecGrid";
import { ErrorBox, Loading } from "../components/Loading";
import SnapshotBanner from "../components/SnapshotBanner";

type Feed = "top" | "oversold" | "breakouts";

function FilterSelect({
  label, value, options, onChange,
}: {
  label: string; value: string; options: [string, string][]; onChange: (v: string) => void;
}) {
  return (
    <label className="text-xs text-ink-secondary flex items-center gap-1.5">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border rounded px-2 py-1 text-sm bg-white text-ink"
      >
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

export default function Opportunities() {
  const [feed, setFeed] = useState<Feed>("top");
  const [rows, setRows] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [snap, setSnap] = useState(false);
  const [setup, setSetup] = useState("all");
  const [quality, setQuality] = useState("all");
  const [confidence, setConfidence] = useState("all");

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

  const filtered = useMemo(() => rows.filter((r) => {
    const profile = (r.metrics as any)?.profile === "opportunity" ? "pullback" : "crash";
    if (setup !== "all" && profile !== setup) return false;
    if (quality === "ab" && !["A", "B"].includes(r.quality_grade ?? "")) return false;
    if (quality === "a" && r.quality_grade !== "A") return false;
    if (confidence === "high" && r.confidence !== "High") return false;
    if (confidence === "hm" && !["High", "Medium"].includes(r.confidence)) return false;
    return true;
  }), [rows, setup, quality, confidence]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-semibold tracking-tight text-ink">Opportunities</h1>
        <div className="flex gap-1 bg-white rounded-lg p-1 shadow-sm">
          {(["top", "oversold", "breakouts"] as Feed[]).map((f) => (
            <button
              key={f}
              onClick={() => setFeed(f)}
              className={`px-3 py-1 rounded text-sm capitalize ${
                feed === f ? "bg-brand text-white" : "text-ink-secondary hover:bg-surface-sunken"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      {snap && <SnapshotBanner />}

      {/* Filter bar */}
      {!loading && rows.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm px-3 py-2 mb-4 flex items-center gap-4 flex-wrap">
          <FilterSelect label="Setup" value={setup} onChange={setSetup}
            options={[["all", "All"], ["crash", "Crash dip"], ["pullback", "Pullback"]]} />
          <FilterSelect label="Quality" value={quality} onChange={setQuality}
            options={[["all", "All"], ["ab", "A / B"], ["a", "A only"]]} />
          <FilterSelect label="Confidence" value={confidence} onChange={setConfidence}
            options={[["all", "All"], ["hm", "High / Medium"], ["high", "High only"]]} />
          <span className="ml-auto text-xs text-ink-muted">
            {filtered.length} of {rows.length} shown
          </span>
        </div>
      )}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox error={error} />
      ) : rows.length === 0 ? (
        <div className="panel p-8 text-center">
          <div className="text-4xl mb-2">🌤️</div>
          <div className="font-semibold text-ink">No matching setups right now</div>
          <div className="text-sm text-ink-secondary mt-1 max-w-md mx-auto">
            The market is calm — nothing hit this screen in the latest scan. Try the{" "}
            <b>oversold</b> or <b>breakouts</b> tabs, check the <b>Dashboard</b> Top Picks,
            or analyze any ticker on the <b>Analysis</b> tab.
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="panel p-8 text-center">
          <div className="text-4xl mb-2">🔍</div>
          <div className="font-semibold text-ink">No names match these filters</div>
          <div className="text-sm text-ink-secondary mt-1">
            {rows.length} names are in the scan — loosen the Setup / Quality / Confidence filters above.
          </div>
        </div>
      ) : (
        <RecGrid rows={filtered} />
      )}
    </div>
  );
}
