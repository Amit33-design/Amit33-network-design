import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import Plot from "react-plotly.js";
import { ErrorBox } from "../components/Loading";
import { getWatchlist, removeFromWatchlist, onWatchlistChange } from "../lib/watchlist";
import { StatTile, Badge, Delta, SkeletonPanel, EmptyState } from "../components/ui";
import { chartColors, plotTheme, onThemeChange, getTheme } from "../lib/theme";

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

const scoreColor = (s: number) => {
  const c = chartColors();
  return s >= 65 ? c.gain : s >= 50 ? "#d9a441" : c.loss;
};
const scoreTone = (s: number): "gain" | "warn" | "loss" =>
  s >= 65 ? "gain" : s >= 50 ? "warn" : "loss";

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
      <polyline points={pts} fill="none" stroke={up ? chartColors().gain : chartColors().loss} strokeWidth="1.6" />
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
      className="panel p-3 cursor-pointer hover:shadow-raised transition-shadow border-l-[3px]"
      style={{ borderLeftColor: scoreColor(s.score) }}
    >
      <div className="flex items-center justify-between">
        <div>
          {/* Ticker opens the full Analysis chart for that symbol; the rest of
              the card still taps to the inline live thesis. */}
          <Link
            to={`/analysis?ticker=${s.ticker}`}
            onClick={(e) => e.stopPropagation()}
            className="font-semibold text-brand hover:underline"
            title={`Open the Analysis chart for ${s.ticker}`}
          >
            {s.ticker}
          </Link>
          <span className="ml-1 text-2xs text-ink-muted">{s.cycle === "bull" ? "▲" : "▼"}</span>
        </div>
        <span className="text-lg font-semibold num" style={{ color: scoreColor(s.score) }}>{s.score}</span>
      </div>
      <div className="text-xs text-ink-secondary truncate">{s.company}</div>
      {s.domain && <div className="text-2xs text-ink-muted truncate">{s.domain}</div>}
      <Sparkline data={s.spark} />
      <div className="mt-1 flex items-center justify-between text-xs">
        <span className="font-medium num">{s.price != null ? `$${s.price}` : "—"}</span>
        <Delta value={s["day_%"]} digits={1} />
      </div>
      <div className="mt-1 flex items-center justify-between text-xs">
        <span className="text-ink-secondary">{s.action}</span>
        <Badge tone={["A", "B"].includes(s.quality_grade) ? "gain" : "neutral"}>
          {s.quality_grade}{s.rsi != null ? ` · RSI ${Math.round(s.rsi)}` : ""}
        </Badge>
      </div>
      {open && (
        <div className="mt-2 pt-2 border-t border-line text-xs text-ink-secondary leading-relaxed" onClick={(e) => e.stopPropagation()}>
          {loading ? (
            <span className="text-ink-muted">Fetching live thesis…</span>
          ) : (
            <><span className="font-semibold text-ink">📝 Live thesis: </span>{thesis}</>
          )}
        </div>
      )}
      {!open && (
        <div className="mt-1 flex items-center justify-between text-[10px]">
          <span className="text-ink-muted">Tap for live thesis</span>
          <Link
            to={`/analysis?ticker=${s.ticker}`}
            onClick={(e) => e.stopPropagation()}
            className="text-brand hover:underline font-medium"
          >
            Chart →
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
      <div className="label-eyebrow mb-1">{title}</div>
      <table className="w-full text-sm num">
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-t border-line first:border-0">
              <td className="py-1 pr-2 font-medium">{r.key}</td>
              <td className="py-1 pr-2 text-ink-muted text-xs">{r.picks}</td>
              <td className="py-1 pr-2">{(r.win_rate * 100).toFixed(0)}%</td>
              <td className={`py-1 pr-2 text-right ${
                r["avg_return_%"] >= 0 ? "text-gain" : "text-loss"}`}>
                {r["avg_return_%"] >= 0 ? "+" : ""}{r["avg_return_%"]}%
              </td>
              {r["avg_alpha_%"] != null && (
                <td className={`py-1 text-right font-semibold ${
                  r["avg_alpha_%"] >= 0 ? "text-gain" : "text-loss"}`}
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


interface WatchRow {
  ticker: string;
  name?: string;
  price?: number;
  day_change_pct?: number;
  score?: number;
  verdict?: string;
  error?: boolean;
}

// Personal watchlist — starred tickers with live quotes/verdicts pulled from
// /api/thesis. Entirely client-side so it works on the static deploy.
function WatchlistSection() {
  const [tickers, setTickers] = useState<string[]>(getWatchlist);
  const [rows, setRows] = useState<WatchRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => onWatchlistChange(() => setTickers(getWatchlist())), []);

  useEffect(() => {
    if (!tickers.length) { setRows([]); return; }
    let cancelled = false;
    setLoading(true);
    Promise.all(
      tickers.map(async (t): Promise<WatchRow> => {
        try {
          const r = await fetch(`/api/thesis?ticker=${encodeURIComponent(t)}`);
          if (!r.ok) throw new Error("no data");
          const j = await r.json();
          return { ticker: t, name: j.name, price: j.price,
                   day_change_pct: j.day_change_pct, score: j.score, verdict: j.verdict };
        } catch {
          return { ticker: t, error: true };
        }
      })
    ).then((res) => { if (!cancelled) setRows(res); })
     .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tickers.join(",")]);

  const up = rows.filter((r) => (r.day_change_pct ?? 0) > 0).length;

  return (
    <Section
      title="⭐ My Watchlist"
      subtitle={tickers.length ? `${up} of ${rows.length} up today` : ""}
      badge={tickers.length ? `${tickers.length}` : "empty"}
      badgeColor="#b7791f"
      defaultOpen={tickers.length > 0}
    >
      {!tickers.length ? (
        <EmptyState
          icon="☆"
          title="No saved tickers yet"
          hint={<>Search any symbol in the header, then tap the ☆ beside its name on the
                Analysis page to track it here.</>}
        />
      ) : (
        <>
          {loading && <div className="text-2xs text-ink-muted mb-2">Refreshing live quotes…</div>}
          <div className="overflow-x-auto thin-scroll -mx-4">
            <table className="table-data">
              <thead>
                <tr>{["Ticker", "Price", "Today", "Score", "Verdict", ""].map((h) => (
                  <th key={h}>{h}</th>))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.ticker}>
                    <td>
                      <Link to={`/analysis?ticker=${r.ticker}`} className="font-semibold text-brand hover:underline">
                        {r.ticker}
                      </Link>
                      {r.name && <span className="ml-2 text-xs text-ink-muted hidden sm:inline">{r.name}</span>}
                    </td>
                    <td className="num">{r.price != null ? `$${r.price}` : "—"}</td>
                    <td><Delta value={r.day_change_pct} /></td>
                    <td>
                      {r.score != null
                        ? <Badge tone={scoreTone(r.score)}>{r.score}</Badge>
                        : <span className="text-ink-muted">—</span>}
                    </td>
                    <td className="text-ink-secondary">{r.error ? "No data" : r.verdict ?? "—"}</td>
                    <td className="text-right">
                      <button onClick={() => removeFromWatchlist(r.ticker)}
                              title={`Remove ${r.ticker}`} aria-label={`Remove ${r.ticker}`}
                              className="text-ink-muted hover:text-loss transition-colors">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Section>
  );
}

export default function Dashboard() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [perf, setPerf] = useState<Perf | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState(getTheme);

  useEffect(() => onThemeChange(() => setTheme(getTheme())), []);

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

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonPanel key={i} rows={1} />)}
        </div>
        <SkeletonPanel rows={5} />
      </div>
    );
  }
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
      <div className="flex items-end justify-between mb-5 flex-wrap gap-3">
        <div>
          <div className="label-eyebrow">Market overview</div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Dashboard</h1>
        </div>
        <div className="text-xs text-ink-muted num">
          {dash.count} instruments · as of {dash.as_of}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <StatTile label="Instruments tracked" value={dash.count} />
        <StatTile label="Bullish" value={bullish} tone="gain"
                  sub={`${Math.round((bullish / Math.max(all.length, 1)) * 100)}% of universe`} />
        <StatTile label="Average score" value={avg.toFixed(1)} sub="0–100 composite" />
        <StatTile label="Market regime" value={regime}
                  tone={regime === "Risk-on" ? "gain" : regime === "Risk-off" ? "loss" : "warn"} />
      </div>

      <WatchlistSection />

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
              <span className="absolute -top-2 -left-2 z-10 bg-series-3 text-white text-xs font-bold rounded-full w-6 h-6 flex items-center justify-center shadow">
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
            <StatTile label="Picks judged" value={perf.summary.picks} />
            <StatTile label="Win rate" value={`${(perf.summary.win_rate * 100).toFixed(0)}%`}
                      tone={perf.summary.win_rate >= 0.5 ? "gain" : "loss"} />
            <StatTile label="Avg return" value={`${perf.summary["avg_return_%"] >= 0 ? "+" : ""}${perf.summary["avg_return_%"]}%`}
                      tone={perf.summary["avg_return_%"] >= 0 ? "gain" : "loss"} />
            {perf.summary["avg_alpha_%"] != null ? (
              <StatTile label={`Alpha vs ${perf.summary.benchmark ?? "SPY"}`}
                        value={`${perf.summary["avg_alpha_%"] >= 0 ? "+" : ""}${perf.summary["avg_alpha_%"]}%`}
                        sub="excess return, same window"
                        tone={perf.summary["avg_alpha_%"] >= 0 ? "gain" : "loss"} />
            ) : (
              <StatTile label="Best pick" value={`${perf.summary.best?.ticker}`}
                        sub={`+${perf.summary.best?.["return_%"]}%`} tone="gain" />
            )}
          </div>
          {perf.summary["avg_alpha_%"] != null && perf.summary["avg_alpha_%"] < 0 && (
            <div className="mb-4 rounded-lg bg-warn-soft border border-warn/30 p-3 text-sm text-ink">
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
          data={[{ type: "bar", x: buckets.map((b) => b.label), y: buckets.map((b) => b.count), marker: { color: chartColors(theme).series[0] } }]}
          layout={{ autosize: true, height: 260, margin: { l: 44, r: 12, t: 8, b: 40 },
                    ...plotTheme(theme),
                    xaxis: { ...plotTheme(theme).xaxis, title: { text: "Composite score" } },
                    yaxis: { ...plotTheme(theme).yaxis, title: { text: "Instruments" } } } as any}
          useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }}
        />
      </div>
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
    <section className="mb-3 panel overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-sunken/60 transition-colors text-left"
      >
        <span className={`text-ink-muted text-xs transition-transform duration-150 ${open ? "rotate-90" : ""}`}>▶</span>
        <span className="text-sm font-semibold text-ink">{title}</span>
        {badge && (
          <span className="rounded-full border px-2 py-0.5 text-2xs font-medium num"
                style={{ backgroundColor: `${badgeColor ?? "#8a938d"}14`,
                         color: badgeColor ?? "#5b6660",
                         borderColor: `${badgeColor ?? "#8a938d"}33` }}>
            {badge}
          </span>
        )}
        {subtitle && <span className="text-xs text-ink-muted hidden sm:inline truncate">{subtitle}</span>}
        <span className="ml-auto text-2xs text-ink-muted">{open ? "Hide" : "Show"}</span>
      </button>
      {open && <div className="px-4 pb-4 pt-1 border-t border-line">{children}</div>}
    </section>
  );
}
