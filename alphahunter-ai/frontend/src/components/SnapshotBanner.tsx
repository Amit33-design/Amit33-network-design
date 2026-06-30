// Shown when the UI is serving the bundled snapshot.json instead of a live
// backend (e.g. the static Vercel deployment with no API connected).
import { snapshotInfo } from "../lib/api";

export default function SnapshotBanner() {
  const { date, live } = snapshotInfo();
  return (
    <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
      <span className="font-semibold">Snapshot mode.</span> Showing the saved
      scan from <span className="font-semibold">{date}</span>
      {live
        ? " (from the daily AlphaHunter scan)."
        : " (seed data — sub-scores are illustrative)."}{" "}
      The daily GitHub Actions scan refreshes this automatically. For live,
      on-demand scans, run the FastAPI backend or set <code>VITE_API_TARGET</code>.
    </div>
  );
}
