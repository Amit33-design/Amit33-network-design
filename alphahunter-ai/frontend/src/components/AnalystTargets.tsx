// Consensus analyst price targets — informational display only (QA P2-6).
// No buy/sell language: targets have not been tested as a signal here.
import { useEffect, useState } from "react";

type T = { mean: number; high: number | null; low: number | null; median: number | null; analysts: number; currency: string };
type F = { as_of: string | null; source: string | null; targets: Record<string, T> };

let cache: Promise<F | null> | null = null;

export default function AnalystTargets({ ticker, price }: { ticker: string; price?: number | null }) {
  const [f, setF] = useState<F | null>(null);
  useEffect(() => {
    cache ??= fetch("/analysts.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    cache.then(setF);
  }, []);
  if (!f) return null;
  const t = f.as_of ? f.targets[ticker.toUpperCase()] : undefined;
  const vs = (x: number | null) => (x != null && price ? ` (${x >= price ? "+" : ""}${((x / price - 1) * 100).toFixed(1)}% vs price)` : "");
  return (
    <div className="panel p-3 text-xs text-ink-secondary">
      <span className="label-eyebrow mr-2">Analyst price targets</span>
      {t ? (
        <>
          mean <b className="text-ink">${t.mean}</b>{vs(t.mean)}
          {t.low != null && t.high != null && <> · range <b className="text-ink">${t.low}–${t.high}</b></>}
          {" "}· {t.analysts} analyst{t.analysts === 1 ? "" : "s"}
          <span className="text-ink-muted"> · {f.source}, as of {f.as_of}. Informational only — not tested as a signal.</span>
        </>
      ) : (
        <span className="text-ink-muted">
          No analyst coverage data{f.as_of ? ` (as of ${f.as_of})` : " yet — the weekly refresh has not run"}.
        </span>
      )}
    </div>
  );
}
