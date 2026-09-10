import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Plot from "react-plotly.js";
import { ErrorBox } from "../components/Loading";
import { getWatchlist, onWatchlistChange, removeFromWatchlist,
         getAlerts, setAlert, alertState, type Alert } from "../lib/watchlist";
import { StatTile, Badge, Delta, SkeletonPanel, EmptyState, Section } from "../components/ui";
import BacktestPanel, { useBacktest } from "../components/BacktestPanel";
import GrowthLeaders, { useGrowth } from "../components/GrowthLeaders";
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
  /** Read from the market itself — SPY structure, breadth and realized
   *  volatility — with an explicit multiplier on position size. */
  market_regime?: {
    regime: "risk-on" | "neutral" | "risk-off" | "unknown";
    score: number;
    position_scale: number;
    factors: string[];
    detail?: Record<string, any>;
  } | null;
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
// Per-ticker target / stop editor. Levels are device-local and evaluated
// against the price the row already fetched, so setting one costs no request.
function AlertCell({ ticker, price, alert }: {
  ticker: string; price?: number | null; alert: Alert;
}) {
  const [editing, setEditing] = useState(false);
  const [target, setTarget] = useState(alert.target != null ? String(alert.target) : "");
  const [stop, setStop] = useState(alert.stop != null ? String(alert.stop) : "");
  const state = alertState(price, alert);

  function commit() {
    setAlert(ticker, { target: parseFloat(target), stop: parseFloat(stop) });
    setEditing(false);
  }

  if (!editing) {
    const has = alert.target != null || alert.stop != null;
    return (
      <button
        onClick={() => setEditing(true)}
        className="text-xs text-left hover:underline"
        title={`Set a target / stop alert for ${ticker}`}
      >
        {state === "target" && <Badge tone="gain">🔔 target hit</Badge>}
        {state === "stop" && <Badge tone="loss">🔔 stop hit</Badge>}
        {!state && has && (
          <span className="num text-ink-secondary">
            {alert.target != null ? `▲$${alert.target}` : ""}
            {alert.target != null && alert.stop != null ? " · " : ""}
            {alert.stop != null ? `▼$${alert.stop}` : ""}
          </span>
        )}
        {!state && !has && <span className="text-ink-muted">+ alert</span>}
      </button>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <input type="number" step="0.01" value={target} placeholder="target"
             onChange={(e) => setTarget(e.target.value)}
             onKeyDown={(e) => e.key === "Enter" && commit()}
             className="w-20 px-1 py-0.5 text-xs num" aria-label={`${ticker} target`} />
      <input type="number" step="0.01" value={stop} placeholder="stop"
             onChange={(e) => setStop(e.target.value)}
             onKeyDown={(e) => e.key === "Enter" && commit()}
             className="w-20 px-1 py-0.5 text-xs num" aria-label={`${ticker} stop`} />
      <button onClick={commit} className="text-xs text-brand hover:underline">save</button>
    </div>
  );
}

// /api/thesis. Entirely client-side so it works on the static deploy.
function WatchlistSection() {
  const [tickers, setTickers] = useState<string[]>(getWatchlist);
  const [rows, setRows] = useState<WatchRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [alerts, setAlerts] = useState<Record<string, Alert>>(getAlerts);

  useEffect(() => onWatchlistChange(() => {
    setTickers(getWatchlist());
    setAlerts(getAlerts());
  }), []);

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
  // Anything that crossed a level goes in the section header, so a triggered
  // alert is visible without expanding the section.
  const triggered = rows
    .map((r) => ({ t: r.ticker, s: alertState(r.price, alerts[r.ticker] ?? {}) }))
    .filter((x) => x.s);

  return (
    <Section
      title="⭐ My Watchlist"
      subtitle={triggered.length
        ? `🔔 ${triggered.map((x) => `${x.t} ${x.s === "target" ? "hit target" : "hit stop"}`).join(" · ")}`
        : tickers.length ? `${up} of ${rows.length} up today` : ""}
      badge={triggered.length ? `${triggered.length} alert${triggered.length > 1 ? "s" : ""}`
                              : tickers.length ? `${tickers.length}` : "empty"}
      badgeColor={triggered.length ? "#e2574c" : "#b7791f"}
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
                <tr>{["Ticker", "Price", "Today", "Score", "Verdict", "Alert", ""].map((h) => (
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
                    <td>
                      <AlertCell ticker={r.ticker} price={r.price}
                                 alert={alerts[r.ticker] ?? {}} />
                    </td>
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState(getTheme);
  const backtest = useBacktest();
  const growth = useGrowth();

  useEffect(() => onThemeChange(() => setTheme(getTheme())), []);

  useEffect(() => {
    fetch("/dashboard.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("no dashboard data yet"))))
      .then(setDash)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
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
  // Prefer the real market read (SPY structure + breadth + realized vol).
  // The old fallback averaged our OWN scores, which measured how bullish this
  // product was rather than what the market was doing — kept only so the tile
  // still renders against a dashboard.json written before the regime existed.
  const mr = dash.market_regime;
  const regime = mr
    ? mr.regime === "risk-on" ? "Risk-on" : mr.regime === "risk-off" ? "Risk-off" : "Neutral"
    : avg >= 60 ? "Risk-on" : avg >= 48 ? "Neutral" : "Risk-off";
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
                  sub={mr
                    ? `${mr.score}/100 · size at ${Math.round(mr.position_scale * 100)}% of normal`
                    : undefined}
                  tone={regime === "Risk-on" ? "gain" : regime === "Risk-off" ? "loss" : "warn"} />
      </div>

      {mr?.factors?.length ? (
        <div className="mb-3 panel px-4 py-2 text-xs text-ink-secondary">
          <span className="label-eyebrow">Why this regime</span>{" "}
          {mr.factors.join(" · ")}
          {mr.position_scale < 1 && (
            <span className="text-warn">
              {" "}Positions sized to {Math.round(mr.position_scale * 100)}% of normal
              while the tape looks like this.
            </span>
          )}
        </div>
      ) : null}

      <WatchlistSection />

      {/* Top Picks — cross-domain highest-conviction names by AI score */}
      <Section
        title="🏆 AlphaHunter Top Picks"
        subtitle={topPicks.length ? `${topPicks[0].ticker} leads at score ${topPicks[0].score}` : ""}
        badge={`best ${topPicks.length}`}
        badgeColor="#7c3aed"
        defaultOpen
      >
        <div className="text-xs text-ink-muted mb-3">
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

      {/* Strategy backtest — the equity curve of actually trading the picks */}
      {/* Growth leaders — the "what should I buy" half, as opposed to the
          "what fell" half every other screen here answers. */}
      {growth && (
        <Section
          title="🌱 Growth Leaders"
          subtitle="growing businesses whose stock is already working"
          badge={`${growth.results.length}`}
          badgeColor="#31a05c"
          defaultOpen
        >
          <GrowthLeaders feed={growth} />
        </Section>
      )}

      {backtest && (
        <Section
          title="🧪 Strategy Backtest"
          subtitle={`top ${backtest.params?.top_n ?? 5} bought each scan day, held ${backtest.params?.hold_days ?? 10} trading days, vs ${backtest.params?.benchmark ?? "SPY"}`}
          badge={backtest["alpha_%"] != null
            ? `alpha ${backtest["alpha_%"] >= 0 ? "+" : ""}${backtest["alpha_%"]}pp`
            : undefined}
          badgeColor={(backtest["alpha_%"] ?? 0) >= 0 ? "#31a05c" : "#e2574c"}
        >
          <BacktestPanel bt={backtest} />
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
          <div className="mt-3 text-xs text-ink-muted">
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


