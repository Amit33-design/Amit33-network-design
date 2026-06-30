import { useState } from "react";
import { runScan } from "../lib/api";

// Triggers the GitHub Actions scan via the /api/run-scan serverless function.
// If the deploy has no GITHUB_DISPATCH_TOKEN configured, it links to the
// Actions "Run workflow" page instead so the button always does something.
export default function RunScanButton() {
  const [state, setState] = useState<"idle" | "running" | "done" | "link" | "error">("idle");
  const [actionsUrl, setActionsUrl] = useState<string>("");

  async function onClick() {
    if (state === "link" && actionsUrl) {
      window.open(actionsUrl, "_blank");
      return;
    }
    setState("running");
    const r = await runScan();
    if (r.triggered) {
      setState("done");
      setTimeout(() => setState("idle"), 8000);
    } else if (r.configured === false) {
      setActionsUrl(
        r.actionsUrl ||
          "https://github.com/Amit33-design/Amit33-network-design/actions/workflows/alphahunter-scan.yml"
      );
      setState("link");
    } else {
      setState("error");
      setTimeout(() => setState("idle"), 6000);
    }
  }

  const label =
    state === "running"
      ? "Starting scan…"
      : state === "done"
      ? "✓ Scan started (~20 min)"
      : state === "link"
      ? "Open Actions to run ↗"
      : state === "error"
      ? "Failed — retry"
      : "▶ Run Scan";

  return (
    <button
      onClick={onClick}
      disabled={state === "running"}
      title="Run a fresh AlphaHunter scan. Results refresh the site automatically (~20-30 min)."
      className="px-3 py-1.5 rounded text-sm font-semibold bg-white text-ink hover:bg-slate-100 disabled:opacity-60"
    >
      {label}
    </button>
  );
}
