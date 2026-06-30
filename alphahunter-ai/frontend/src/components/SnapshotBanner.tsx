// Shown when the UI is serving the bundled snapshot.json instead of a live
// backend (e.g. the static Vercel deployment with no API connected).
export default function SnapshotBanner() {
  return (
    <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
      <span className="font-semibold">Snapshot mode.</span> Showing the latest
      saved scan (2026-06-25) because no live backend is connected. Run the
      FastAPI backend (or set <code>VITE_API_TARGET</code>) for live, on-demand
      scans. Composite sub-scores in this snapshot are illustrative.
    </div>
  );
}
