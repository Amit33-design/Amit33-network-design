import { useState } from "react";
import { runScan } from "../lib/api";

const ACTIONS_URL =
  "https://github.com/Amit33-design/Amit33-network-design/actions/workflows/alphahunter-scan.yml";

// Triggers the GitHub Actions scan via /api/run-scan. If the deploy has a
// GITHUB_DISPATCH_TOKEN it dispatches directly (works everywhere incl. mobile).
// Without it, we render a REAL anchor link (not window.open, which mobile
// popup-blockers reject from async callbacks) to the Actions page.
export default function RunScanButton() {
  const [state, setState] = useState<"idle" | "running" | "done" | "link" | "error">("idle");
  const [actionsUrl, setActionsUrl] = useState<string>(ACTIONS_URL);

  async function onClick() {
    setState("running");
    const r = await runScan();
    if (r.triggered) {
      setState("done");
      setTimeout(() => setState("idle"), 8000);
    } else if (r.configured === false) {
      setActionsUrl(r.actionsUrl || ACTIONS_URL);
      setState("link");
    } else {
      setState("error");
      setTimeout(() => setState("idle"), 6000);
    }
  }

  const cls =
    "px-3 py-1.5 rounded text-sm font-semibold bg-white text-ink hover:bg-slate-100 disabled:opacity-60 whitespace-nowrap";

  // Once we know there's no token, show a native link that opens reliably on
  // mobile and desktop.
  if (state === "link") {
    return (
      <a href={actionsUrl} target="_blank" rel="noopener noreferrer" className={cls}>
        Run Scan on GitHub ↗
      </a>
    );
  }

  const label =
    state === "running"
      ? "Starting…"
      : state === "done"
      ? "✓ Scan started"
      : state === "error"
      ? "Failed — retry"
      : "▶ Run Scan";

  return (
    <button onClick={onClick} disabled={state === "running"} className={cls}
            title="Run a fresh AlphaHunter scan; results refresh the site automatically.">
      {label}
    </button>
  );
}
