import { useEffect, useState, type ReactNode } from "react";
import Plot from "react-plotly.js";
import { ErrorBox, Loading } from "../components/Loading";

interface Stock {
  ticker: string;
  company: string;
  domain: string;
  price: number | null;
  "day_%": number | null;
  score: number;
  action: string;
  quality_grade: string;
  rsi: number | null;
  above_ema200: boolean | null;
  cycle: string;
  "analyst_upside_%": number | null;
  spark?: number[];
}
interface Dash {
  as_of: string;
  count: number;
  domains: Record<string, Stock[]>;
}

const scoreColor = (s: number) => (s >= 65 ? "#1b7f4b" : s >= 50 ? "#b7791f" : "#c0392b");

function Sparkline({ data }: { data?: number[] }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * 100},${28 - ((v - min) / range) * 26 - 1}`)
    .join(" ");
  const up = data[data.length - 1] >= data[0];
  return (
    <svg viewBox="0 0 100 28" className="w-full h-7" preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={up ? "#1b7f4b" : "#c0392b"} strokeWidth="1.6" />
    </svg>
  );
}

function StockCard({ s }: { s: Stock }) {
  const [open, setOpen] = useState(false);
  const [thesis, setThesis] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !thesis && !loading) {
      setLoading(true);
      try {
        const r = await fetch(`/api/thesis?ticker=${s.ticker}`);
        const j = await r.json();
        setThesis(j.thesis || "No thesis available right now.");
      } catch {
        setThesis("Live thesis unavailable — check your connection or try again.");
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <div
      onClick={toggle}
      className="bg-white rounded-xl shadow-sm p-3 cursor-pointer hover:shadow-md transition border-l-4"
      style={{ borderLeftColor: scoreColor(s.score) }}
    >
      <div className="flex items-center justify-between">
        <div>
          <span className="font-bold text-alpha">{s.ticker}</span>
          <span className="ml-1 text-xs text-slate-400">{s.cycle === "bull" ? "▲" : "▼"}</span>
        </div>
        <span className="text-lg font-bold" style={{ color: scoreColor(s.score) }}>{s.score}</span>
      </div>
      <div className="text-xs text-slate-500 truncate">{s.company}</div>
      {s.domain && <div className="text-[10px] text-purple-500 truncate">{s.domain}</div>}
      <Sparkline data={s.spark} />
      <div className="mt-1 flex items-center justify-between text-xs">
        <span className="font-medium">{s.price != null ? `$${s.price}` : "—"}</span>
        <span className={(s["day_%"] ?? 0) >= 0 ? "text-alpha font-semibold" : "text-red-600 font-semibold"}>
          {s["day_%"] != null ? `${s["day_%"] >= 0 ? "+" : ""}${Number(s["day_%"]).toFixed(1)}%` : ""}
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between text-xs">
        <span className="text-slate-500">{s.action}</span>
        <span className="font-semibold" style={{ color: ["A", "B"].includes(s.quality_grade) ? "#1b7f4b" : "#64748b" }}>
          {s.quality_grade}{s.rsi != null ? ` · RSI ${Math.round(s.rsi)}` : ""}
        </span>
      </div>
      {open && (
        <div className="mt-2 pt-2 border-t border-slate-100 text-xs text-slate-600 leading-relaxed" onClick={(e) => e.stopPropagation()}>
          {loading ? (
            <span className="text-slate-400">Fetching live thesis…</span>
          ) : (
            <><span className="font-semibold text-ink">📝 Live thesis: </span>{thesis}</>
          )}
        </div>
      )}
      {!open && <div className="mt-1 text-[10px] text-slate-300">tap for live thesis</div>}
    </div>
  );
}

interface Perf {
  generated?: string;
  picks: { date: string; ticker: string; score?: number; action?: string;
           entry: number; price: number; "return_%": number; days: number }[];
  summary: { picks: number; win_rate: number; "avg_return_%": number;
             best: any; worst: any } | null;
}

export default function Dashboard() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [perf, setPerf] = useState<Perf | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/dashboard.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("no dashboard data yet"))))
      .then(setDash)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    fetch("/performance.json")
      .then((r) => (r.ok ? r.json() : null))
      .then(setPerf)
      .catch(() => setPerf(null));
  }, []);

  if (loading) return <Loading label="Loading dashboard…" />;
  if (error || !dash) return <ErrorBox error={error || "no data"} />;

  const all = Object.values(dash.domains).flat();
  const bullish = all.filter((s) => s.above_ema200 || s.score >= 60).length;
  const avg = all.length ? all.reduce((a, s) => a + s.score, 0) / all.length : 0;
  const regime = avg >= 60 ? "Risk-on" : avg >= 48 ? "Neutral" : "Risk-off";
  const movers = [...all].filter((s) => s["day_%"] != null).sort((a, b) => (b["day_%"] ?? 0) - (a["day_%"] ?? 0));
  const gainers = movers.filter((s) => (s["day_%"] ?? 0) > 0);
  const topGainers = gainers.slice(0, 10);
  const losers = movers.slice(-3).reverse();
  const buckets = [0, 20, 40, 50, 60, 70, 80].map((b, i, arr) => {
    const hi = arr[i + 1] ?? 101;
    return { label: `${b}-${hi === 101 ? 100 : hi}`, count: all.filter((s) => s.score >= b && s.score < hi).length };
  });
  // The identifying system: the highest-conviction names across ALL domains,
  // ranked by AI score (tie-broken by day strength). This is the "what looks
  // best right now" board, independent of category.
  const topPicks = [...all].sort((a, b) => b.score - a.score || (b["day_%"] ?? 0) - (a["day_%"] ?? 0)).slice(0, 8);

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-ink">Dashboard — {dash.count} stocks across domains</h1>
        <span className="text-xs text-slate-400">as of {dash.as_of}</span>
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <Tile label="Tracked" value={String(dash.count)} />
        <Tile label="Bullish" value={String(bullish)} accent="text-alpha" />
        <Tile label="Avg Score" value={avg.toFixed(1)} />
        <Tile label="Market" value={regime}
              accent={regime === "Risk-on" ? "text-alpha" : regime === "Risk-off" ? "text-red-600" : "text-amber-600"} />
      </div>

      {/* Top Picks — cross-domain highest-conviction names by AI score */}
      <Section
        title="🏆 AlphaHunter Top Picks"
        subtitle={topPicks.length ? `${topPicks[0].ticker} leads at score ${topPicks[0].score}` : ""}
        badge={`best ${topPicks.length}`}
        badgeColor="#7c3aed"
        defaultOpen
      >
        <div className="text-xs text-slate-400 mb-3">
          Highest AI-scored names across every domain right now — the system's best identifications, ranked by conviction.
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {topPicks.map((s, i) => (
            <div key={s.ticker} className="relative">
              <span className="absolute -top-2 -left-2 z-10 bg-purple-600 text-white text-xs font-bold rounded-full w-6 h-6 flex items-center justify-center shadow">
                {i + 1}
              </span>
              <StockCard s={s} />
            </div>
          ))}
        </div>
      </Section>

      {/* Track record — how past picks actually performed (accountability) */}
      {perf?.summary && (
        <Section
          title="📈 Track Record"
          subtitle={`since picks aged ≥2 days · updated ${perf.generated ?? ""}`}
          badge={`${(perf.summary.win_rate * 100).toFixed(0)}% winners · avg ${perf.summary["avg_return_%"] >= 0 ? "+" : ""}${perf.summary["avg_return_%"]}%`}
          badgeColor={perf.summary["avg_return_%"] >= 0 ? "#1b7f4b" : "#c0392b"}
          defaultOpen={false}
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <Tile label="Picks judged" value={String(perf.summary.picks)} />
            <Tile label="Win rate" value={`${(perf.summary.win_rate * 100).toFixed(0)}%`}
                  accent={perf.summary.win_rate >= 0.5 ? "text-alpha" : "text-red-600"} />
            <Tile label="Avg return" value={`${perf.summary["avg_return_%"] >= 0 ? "+" : ""}${perf.summary["avg_return_%"]}%`}
                  accent={perf.summary["avg_return_%"] >= 0 ? "text-alpha" : "text-red-600"} />
            <Tile label="Best pick" value={`${perf.summary.best?.ticker} +${perf.summary.best?.["return_%"]}%`} accent="text-alpha" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-400 text-left">
                <tr>{["Picked", "Ticker", "Action", "Entry", "Now", "Return", "Held"].map((h) => (
                  <th key={h} className="px-2 py-1 whitespace-nowrap">{h}</th>))}
                </tr>
              </thead>
              <tbody>
                {perf.picks.slice(0, 15).map((p, i) => (
                  <tr key={`${p.date}-${p.ticker}-${i}`} className="border-t">
                    <td className="px-2 py-1 text-slate-400 whitespace-nowrap">{p.date}</td>
                    <td className="px-2 py-1 font-semibold text-alpha">{p.ticker}</td>
                    <td className="px-2 py-1">{p.action ?? "—"}</td>
                    <td className="px-2 py-1">${p.entry}</td>
                    <td className="px-2 py-1">${p.price}</td>
                    <td className={`px-2 py-1 font-semibold ${p["return_%"] >= 0 ? "text-alpha" : "text-red-600"}`}>
                      {p["return_%"] >= 0 ? "+" : ""}{p["return_%"]}%
                    </td>
                    <td className="px-2 py-1 text-slate-400">{p.days}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Top Gainers — a collapsible section like the domains, open by default */}
      <Section
        title="🚀 Top Gainers"
        subtitle={`${topGainers.length ? topGainers[0].ticker + " leads +" + Number(topGainers[0]["day_%"]).toFixed(1) + "% today" : ""}`}
        badge={`${gainers.length} up`}
        badgeColor="#1b7f4b"
        defaultOpen
      >
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {topGainers.map((s) => <StockCard key={s.ticker} s={s} />)}
        </div>
        {losers.length > 0 && (
          <div className="mt-3 text-xs text-slate-400">
            Today's laggards: {losers.map((s) => `${s.ticker} ${Number(s["day_%"]).toFixed(1)}%`).join(" · ")}
          </div>
        )}
      </Section>

      {/* Domain sections — each a click-to-expand dropdown */}
      {Object.entries(dash.domains).map(([domain, stocks]) => {
        if (!stocks.length) return null;
        const domAvg = stocks.reduce((a, s) => a + s.score, 0) / stocks.length;
        const leader = stocks[0];
        return (
          <Section
            key={domain}
            title={domain}
            subtitle={`leader ${leader.ticker} (${leader.score})`}
            badge={`avg ${domAvg.toFixed(0)}`}
            badgeColor={scoreColor(domAvg)}
            defaultOpen={false}
          >
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {stocks.map((s) => <StockCard key={s.ticker} s={s} />)}
            </div>
          </Section>
        );
      })}

      <div className="bg-white rounded-xl shadow-sm p-4 mt-2">
        <div className="font-semibold text-ink mb-2">Score distribution</div>
        <Plot
          data={[{ type: "bar", x: buckets.map((b) => b.label), y: buckets.map((b) => b.count), marker: { color: "#1b7f4b" } }]}
          layout={{ autosize: true, height: 280, margin: { l: 40, r: 10, t: 10, b: 40 },
                    xaxis: { title: { text: "AI score" } }, yaxis: { title: { text: "count" } } }}
          useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }}
        />
      </div>
    </div>
  );
}

function Tile({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${accent ?? "text-ink"}`}>{value}</div>
    </div>
  );
}

// Collapsible category section — click the header to expand/collapse.
function Section({
  title, subtitle, badge, badgeColor, defaultOpen, children,
}: {
  title: string; subtitle?: string; badge?: string; badgeColor?: string;
  defaultOpen?: boolean; children: ReactNode;
}) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div className="mb-3 bg-white rounded-xl shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition text-left"
      >
        <span className={`text-slate-400 transition-transform ${open ? "rotate-90" : ""}`}>▶</span>
        <span className="font-semibold text-ink">{title}</span>
        {badge && (
          <span className="text-xs px-2 py-0.5 rounded-full font-semibold"
                style={{ backgroundColor: `${badgeColor ?? "#64748b"}18`, color: badgeColor ?? "#64748b" }}>
            {badge}
          </span>
        )}
        {subtitle && <span className="text-xs text-slate-400 hidden sm:inline">{subtitle}</span>}
        <span className="ml-auto text-xs text-slate-400">{open ? "hide" : "show"}</span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}
