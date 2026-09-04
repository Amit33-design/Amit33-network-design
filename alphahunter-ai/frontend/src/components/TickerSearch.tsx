import { useState } from "react";
import { useNavigate } from "react-router-dom";

// Global ticker search — every professional trading app lets you jump to any
// symbol from anywhere. Navigates to the Analysis chart for whatever you type.
export default function TickerSearch() {
  const [q, setQ] = useState("");
  const navigate = useNavigate();

  function go(e: React.FormEvent) {
    e.preventDefault();
    const sym = q.trim().toUpperCase();
    if (!sym) return;
    navigate(`/analysis?ticker=${encodeURIComponent(sym)}`);
    setQ("");
  }

  return (
    <form onSubmit={go} className="relative">
      <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2
                       text-ink-inverse/40 text-sm">⌕</span>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search ticker…"
        aria-label="Search any ticker"
        className="w-32 sm:w-48 bg-white/10 text-ink-inverse placeholder-ink-inverse/40
                   rounded-md border border-white/10 pl-8 pr-7 py-1.5 text-sm uppercase
                   focus-visible:ring-brand/60 focus:bg-white/[0.15] transition-colors"
      />
      {q && (
        <button type="submit"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-xs text-brand font-semibold">
          →
        </button>
      )}
    </form>
  );
}
