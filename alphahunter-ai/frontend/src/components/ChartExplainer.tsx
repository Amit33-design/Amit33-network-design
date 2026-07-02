import { useState } from "react";

// Tap the ℹ️ on any chart to expand a plain-English explanation of what the
// graph shows and how to read it (plus an optional "right now" line built
// from the live data).
export default function ChartExplainer({
  title,
  points,
  current,
}: {
  title: string;
  points: string[];
  current?: string | null;
}) {
  const [open, setOpen] = useState(false);
  return (
    <span className="inline-block align-middle">
      <button
        onClick={() => setOpen(!open)}
        className="ml-2 text-xs px-2 py-0.5 rounded-full border border-slate-300 text-slate-500 hover:bg-slate-100"
        title={`What does the ${title} chart mean?`}
      >
        ℹ️ what is this?
      </button>
      {open && (
        <div className="mt-2 rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm text-slate-600 text-left">
          <div className="font-semibold text-ink mb-1">How to read {title}</div>
          <ul className="list-disc pl-5 space-y-1">
            {points.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
          {current && (
            <div className="mt-2 pt-2 border-t border-slate-200">
              <span className="font-semibold text-ink">Right now: </span>
              {current}
            </div>
          )}
        </div>
      )}
    </span>
  );
}
