import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
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
          {/* Ticker opens the full Analysis chart for that symbol; the rest of
              the card still taps to the inline live thesis. */}
          <Link
            to={`/analysis?ticker=${s.ticker}`}
            onClick={(e) => e.stopPropagation()}
            className="font-bold text-alpha hover:underline"
            title={`Open the Analysis chart for ${s.ticker}`}
          >
            {s.ticker}
          </Link>
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
      {!open && (
        <div className="mt-1 flex items-center justify-between text-[10px]">
          <span className="text-slate-300">tap for live thesis</span>
          <Link
            to={`/analysis?ticker=${s.ticker}`}
            onClick={(e) => e.stopPropagation()}
            className="text-alpha hover:underline font-medium"
          >
            📈 chart
          </Link>
        </div>
      )}
    </div>
  );
}

interface Perf {
  generated?: string;
  picks: { date: string; ticker: string; score?: number; action?: string;
           entry: number; price: number; "return_%": number; days: number }[];
  summary: { picks: number; win_rate: number; "avg_return_%": number;
             best: any; worst: any; "avg_alpha_%"?: number;
             beat_benchmark_rate?: number; benchmark?: string } | null;
  segments?: Record<string, { key: string; picks: number; win_rate: number;
                              "avg_return_%": number }[]>;
}

const SEGMENT_LABELS: Record<string, string> = {
  quality_grade: "By quality grade",
  grade_x_score: "By grade × score band",
  setup: "By setup type",
  confidence: "By confidence",
  score_band: "By score band",
};

// Which cohorts actually made money — the feedback loop on our own signals.
function SegmentTable({ title, rows }: { title: string; rows: any[] }) {
  if (!rows?.length) return null;
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">{title}</div>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-t first:border-0">
              <td className="py-1 pr-2 font-medium">{r.key}</td>
              <td className="py-1 pr-2 text-slate-400 text-xs">{r.picks}</td>
              <td className="py-1 pr-2">{(r.win_rate * 100).toFixed(0)}%</td>
              <td className={`py-1 pr-2 text-right ${
                r["avg_return_%"] >= 0 ? "text-alpha" : "text-red-600"}`}>
                {r["avg_return_%"] >= 0 ? "+" : ""}{r["avg_return_%"]}%
              </td>
              {r["avg_alpha_%"] != null && (
                <td className={`py-1 text-right font-semibold ${
                  r["avg_alpha_%"] >= 0 ? "text-alpha" : "text-red-600"}`}
                    title="Average alpha vs SPY over the same holding window">
                  {r["avg_alpha_%"] >= 0 ? "+" : ""}{r["avg_alpha_%"]}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
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
          badge={perf.summary["avg_alpha_%"] != null
            ? `${((perf.summary.beat_benchmark_rate ?? 0) * 100).toFixed(0)}% beat ${perf.summary.benchmark ?? "SPY"} · alpha ${perf.summary["avg_alpha_%"] >= 0 ? "+" : ""}${perf.summary["avg_alpha_%"]}%`
            : `${(perf.summary.win_rate * 100).toFixed(0)}% winners · avg ${perf.summary["avg_return_%"] >= 0 ? "+" : ""}${perf.summary["avg_return_%"]}%`}
          badgeColor={(perf.summary["avg_alpha_%"] ?? perf.summary["avg_return_%"]) >= 0 ? "#1b7f4b" : "#c0392b"}
          defaultOpen={false}
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <Tile label="Picks judged" value={String(perf.summary.picks)} />
            <Tile label="Win rate" value={`${(perf.summary.win_rate * 100).toFixed(0)}%`}
                  accent={perf.summary.win_rate >= 0.5 ? "text-alpha" : "text-red-600"} />
            <Tile label="Avg return" value={`${perf.summary["avg_return_%"] >= 0 ? "+" : ""}${perf.summary["avg_return_%"]}%`}
                  accent={perf.summary["avg_return_%"] >= 0 ? "text-alpha" : "text-red-600"} />
            {perf.summary["avg_alpha_%"] != null ? (
              <Tile label={`vs ${perf.summary.benchmark ?? "SPY"}`}
                    value={`${perf.summary["avg_alpha_%"] >= 0 ? "+" : ""}${perf.summary["avg_alpha_%"]}%`}
                    accent={perf.summary["avg_alpha_%"] >= 0 ? "text-alpha" : "text-red-600"} />
            ) : (
              <Tile label="Best pick" value={`${perf.summary.best?.ticker} +${perf.summary.best?.["return_%"]}%`} accent="text-alpha" />
            )}
          </div>
          {perf.summary["avg_alpha_%"] != null && perf.summary["avg_alpha_%"] < 0 && (
            <div className="mb-4 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">
              <b>Read this before acting.</b> Across all {perf.summary.picks} judged picks the
              average result is <b>{perf.summary["avg_alpha_%"]}% vs {perf.summary.benchmark ?? "SPY"}</b>,
              and only {((perf.summary.beat_benchmark_rate ?? 0) * 100).toFixed(0)}% beat the index —
              so the board as a whole has <b>not</b> outperformed simply holding the market.
              The cohort table below shows where the edge actually is (the highest score band).
            </div>
          )}
          {perf.segments && Object.values(perf.segments).some((r) => r?.length) && (
            <div className="mb-4">
              <div className="text-sm font-semibold text-ink mb-2">
                What's actually working
                <span className="ml-2 text-xs font-normal text-slate-400">
                  picks · win rate · avg return · alpha vs SPY (groups under 3 picks hidden)
                </span>
              </div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-4">
                {Object.entries(perf.segments).map(([k, rows]) => (
                  <SegmentTable key={k} title={SEGMENT_LABELS[k] ?? k} rows={rows} />
                ))}
              </div>
            </div>
          )}
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
