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
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search ticker…"
        aria-label="Search any ticker"
        className="w-32 sm:w-44 bg-white/10 text-white placeholder-slate-300 rounded px-3 py-1.5 text-sm
                   focus:outline-none focus:ring-2 focus:ring-alpha focus:bg-white/20 uppercase"
      />
      {q && (
        <button type="submit"
                className="absolute right-1 top-1/2 -translate-y-1/2 text-xs text-alpha font-semibold px-1.5">
          →
        </button>
      )}
    </form>
  );
}
