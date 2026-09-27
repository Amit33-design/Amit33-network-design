import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ErrorBox } from "../components/Loading";
import { getWatchlist, onWatchlistChange, removeFromWatchlist,
         getAlerts, setAlert, alertState, type Alert } from "../lib/watchlist";
import { Badge, Delta, SkeletonPanel, EmptyState, Section } from "../components/ui";
import GrowthLeaders, { useGrowth } from "../components/GrowthLeaders";
import { STALE_AFTER, useScanFreshness } from "../components/FreshnessBanner";
import EvidenceBadge from "../components/EvidenceBadge";
import TodayPlan from "../components/TodayPlan";
import { useJudged } from "../lib/evidence";
import Moonshots, { useMoonshots } from "../components/Moonshots";
import { chartColors } from "../lib/theme";
import type { Story } from "../lib/story";
import ThemeBoard, { rankThemes, useThemes } from "../components/ThemeBoard";

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
  quality?: Quality | null;
  entry_timing?: {
    action: "buy_zone" | "wait";
    entry_target?: number | null;
    reason?: string;
  } | null;
}
interface ConcentrationRead {
  count: number;
  effective_bets: number;
  top_sector?: string | null;
  top_sector_share: number;
  by_sector?: { sector: string; count: number; share: number }[];
  concentrated: boolean;
  note: string;
}

interface Quality {
  data_quality?: "ok" | "stale" | "unusable";
  display_close?: number | null;
  display_date?: string | null;
  flags?: { date: string; kind: string; detail?: string }[];
}

interface Dash {
  as_of: string;
  count: number;
  domains: Record<string, Stock[]>;
  /** Read from the market itself — SPY structure, breadth and realized
   *  volatility — with an explicit multiplier on position size. */
  /** How many independent bets the board really is. */
  concentration?: {
    top_picks?: ConcentrationRead;
    whole_board?: ConcentrationRead;
  } | null;
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

/** "Data delayed" badge for a row whose latest bar was quarantined. */
function QualityBadge({ q }: { q?: Quality | null }) {
  if (!q || q.data_quality === "ok" || !q.data_quality) return null;
  const stale = q.data_quality === "stale";
  return (
    <span
      className={`ml-1 align-middle text-2xs px-1.5 py-0.5 rounded border ${
        stale ? "border-warn/40 bg-warn-soft text-warn"
              : "border-loss/40 bg-loss-soft text-loss"}`}
      title={stale
        ? `Today's bar failed validation (${q.flags?.[0]?.detail ?? "out of range"}). Showing the last good close${q.display_date ? ` from ${q.display_date}` : ""}.`
        : "Not enough usable price history to validate this series."}
    >
      {stale ? "data delayed" : "unverified"}
    </span>
  );
}

function StockCard({ s }: { s: Stock }) {
  const [open, setOpen] = useState(false);
  const [thesis, setThesis] = useState<string | null>(null);
  const [story, setStory] = useState<Story | null>(null);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !thesis && !loading) {
      setLoading(true);
      try {
        const r = await fetch(`/api/thesis?ticker=${s.ticker}&story=1`);
        const j = await r.json();
        setThesis(j.thesis || "No thesis available right now.");
        setStory(j.story ?? null);
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
        <span className="font-medium num">
          {s.price != null ? `$${s.price}` : "—"}
          <QualityBadge q={s.quality} />
          {s.entry_timing?.action === "wait" && (
            <span className="ml-1 align-middle text-2xs px-1 py-0.5 rounded border border-warn/40 bg-warn-soft text-warn"
                  title={s.entry_timing.reason}>
              wait ≈${s.entry_timing.entry_target}
            </span>
          )}
        </span>
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
            <>
              {story?.theme && (
                <div className="mb-1 flex flex-wrap items-center gap-1">
                  <Badge tone="brand">{story.theme.name}</Badge>
                  <Badge>{story.type.style}</Badge>
                </div>
              )}
              {story?.theme?.scope && <div className="mb-1 text-ink">{story.theme.scope}</div>}
              {story?.pulse.reads.map((r) => (
                <div key={r.text} className={r.tone > 0 ? "text-gain" : r.tone < 0 ? "text-loss" : ""}>
                  {r.tone > 0 ? "▲" : r.tone < 0 ? "▼" : "•"} <span className="text-ink-secondary">{r.text}</span>
                </div>
              ))}
              {story && <div className="mt-1 text-ink"><b>Bottom line: </b>{story.bottom_line}</div>}
              <div className="mt-1"><span className="font-semibold text-ink">Chart: </span>{thesis}</div>
            </>
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

  // Nothing saved: no section. The ☆ on the Analysis page is how you add one,
  // and an empty panel on every visit is the kind of clutter this page lost.
  if (!tickers.length) return null;

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

type TabKey = "picks" | "growth" | "moonshots" | "themes" | "movers" | "sectors";
const TAB_STORE = "alphahunter.dashTab";

/** The regime, what it means for position size, whether the data is fresh,
 *  and where money is going — one strip instead of four tiles and two
 *  banners. The old tiles (instruments tracked, "bullish", average score)
 *  measured this product's own scores, not the market. */
function MarketStrip({ mr, asOf, onThemes }: {
  mr: Dash["market_regime"]; asOf: string; onThemes: () => void;
}) {
  const themes = rankThemes(useThemes());
  const { date: scanDate, age } = useScanFreshness();
  const regime = mr?.regime === "risk-on" ? "Risk-on" : mr?.regime === "risk-off" ? "Risk-off"
    : mr ? "Neutral" : null;
  const tone = regime === "Risk-on" ? "text-gain" : regime === "Risk-off" ? "text-loss" : "text-warn";
  const stale = age != null && age > STALE_AFTER;
  const top = themes[0], bottom = themes[themes.length - 1];
  const pp = (x?: number | null) => `${(x ?? 0) >= 0 ? "+" : ""}${(x ?? 0).toFixed(0)}pp`;

  return (
    <div className="panel px-4 py-3 mb-3">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {regime && (
          <div className="flex items-baseline gap-2">
            <span className="label-eyebrow">Market</span>
            <span className={`text-lg font-semibold ${tone}`}>{regime}</span>
            <span className="text-xs text-ink-muted num">{mr!.score}/100</span>
          </div>
        )}
        {mr && (
          <div className="text-xs text-ink-secondary">
            Size positions at{" "}
            <b className={mr.position_scale < 1 ? "text-warn" : "text-ink"}>
              {Math.round(mr.position_scale * 100)}%
            </b>{" "}of normal
          </div>
        )}
        {top && bottom && top !== bottom && (
          <button onClick={onThemes} className="text-xs text-ink-secondary hover:underline text-left"
                  title="Themes measured on their own stocks, 3-month return vs the S&P 500">
            Money into <b className="text-gain">{top.name}</b> {pp(top.basket?.vs_spy_3m)}
            {" · "}out of <b className="text-loss">{bottom.name}</b> {pp(bottom.basket?.vs_spy_3m)}
          </button>
        )}
        <div className={`ml-auto text-2xs num ${stale ? "text-loss font-semibold" : "text-ink-muted"}`}>
          {stale
            ? `⚠ Scan data is ${age} trading days old — check live quotes before acting`
            : `Scan ${scanDate ?? "—"} · watchlist ${asOf}`}
        </div>
      </div>
      {mr?.factors?.length ? (
        <div className="mt-1.5 text-2xs text-ink-muted">{mr.factors.join(" · ")}</div>
      ) : null}
    </div>
  );
}

function TabButton({ active, onClick, children, count }: {
  active: boolean; onClick: () => void; children: React.ReactNode; count?: number | string;
}) {
  return (
    <button onClick={onClick} role="tab" aria-selected={active}
            className={`px-3 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              active ? "border-brand text-ink" : "border-transparent text-ink-muted hover:text-ink"}`}>
      {children}
      {count != null && <span className="ml-1.5 text-2xs text-ink-muted num">{count}</span>}
    </button>
  );
}

export default function Dashboard() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const growth = useGrowth();
  const moonshots = useMoonshots();
  const judged = useJudged();
  const themes = useThemes();
  const [params, setParams] = useSearchParams();
  const [tab, setTabState] = useState<TabKey>(() => {
    const q = params.get("tab") as TabKey | null;
    if (q) return q;
    try { return (localStorage.getItem(TAB_STORE) as TabKey) || "picks"; } catch { return "picks"; }
  });
  const [sector, setSector] = useState<string | null>(null);
  const setTab = (t: TabKey) => {
    setTabState(t);
    try { localStorage.setItem(TAB_STORE, t); } catch { /* private mode */ }
    const next = new URLSearchParams(params); next.set("tab", t); setParams(next, { replace: true });
  };

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
        <SkeletonPanel rows={1} />
        <SkeletonPanel rows={5} />
      </div>
    );
  }
  if (error || !dash) return <ErrorBox error={error || "no data"} />;

  const all = Object.values(dash.domains).flat();
  const mr = dash.market_regime;
  const movers = [...all].filter((s) => s["day_%"] != null).sort((a, b) => (b["day_%"] ?? 0) - (a["day_%"] ?? 0));
  const gainers = movers.filter((s) => (s["day_%"] ?? 0) > 0);
  const topGainers = gainers.slice(0, 10);
  const losers = movers.slice(-5).reverse().filter((s) => (s["day_%"] ?? 0) < 0);
  const topPicks = [...all].sort((a, b) => b.score - a.score || (b["day_%"] ?? 0) - (a["day_%"] ?? 0)).slice(0, 8);
  const domains = Object.entries(dash.domains).filter(([, v]) => v.length);
  const activeSector = sector ?? domains[0]?.[0] ?? null;
  const themeCount = rankThemes(themes).length;

  return (
    <div>
      <div className="flex items-end justify-between mb-3 flex-wrap gap-2">
        <div>
          <div className="label-eyebrow">Market overview</div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Dashboard</h1>
        </div>
      </div>

      <MarketStrip mr={mr} asOf={dash.as_of} onThemes={() => setTab("themes")} />

      {/* Decide -> size -> act -> exit. First, because it is the only list
          here backed by out-of-sample evidence. */}
      <Section
        title="📋 Today's plan"
        subtitle="the one rule with out-of-sample evidence, applied to today's scan"
        defaultOpen
      >
        <TodayPlan positionScale={mr?.position_scale ?? 1} regime={mr?.regime} />
      </Section>

      <WatchlistSection />

      {/* Everything else is one panel with tabs. It used to be ten stacked
          sections, three of them open by default with 8-10 cards each. */}
      <section className="panel overflow-hidden">
        <div role="tablist" className="flex overflow-x-auto no-scrollbar border-b border-line px-2">
          <TabButton active={tab === "picks"} onClick={() => setTab("picks")} count={topPicks.length}>🏆 Top Picks</TabButton>
          {growth && <TabButton active={tab === "growth"} onClick={() => setTab("growth")} count={growth.results.length}>🌱 Growth</TabButton>}
          {moonshots && <TabButton active={tab === "moonshots"} onClick={() => setTab("moonshots")} count={moonshots.results.length}>🎲 Moonshots</TabButton>}
          <TabButton active={tab === "themes"} onClick={() => setTab("themes")} count={themeCount || undefined}>🧭 Themes</TabButton>
          <TabButton active={tab === "movers"} onClick={() => setTab("movers")} count={gainers.length}>🚀 Movers</TabButton>
          <TabButton active={tab === "sectors"} onClick={() => setTab("sectors")} count={domains.length}>🗂 Sectors</TabButton>
        </div>

        <div className="p-4">
          {tab === "picks" && (
            <>
              <TabIntro evidence={<EvidenceBadge status={{
                label: "Unproven", tone: "neutral",
                detail: "Ranked by the composite score. On 894 held-out samples its rank-IC was -0.053, "
                  + "inside the ±0.067 noise floor — it has not been shown to rank future returns.",
              }} />}>
                Highest composite scores across the watchlist. A ranking, not a proven edge.
              </TabIntro>
              {dash.concentration?.top_picks && (
                <div className={`mb-3 text-xs rounded-panel border px-3 py-2 ${
                  dash.concentration.top_picks.concentrated
                    ? "border-warn/30 bg-warn-soft text-warn"
                    : "border-line bg-surface-sunken text-ink-secondary"}`}>
                  <b>{dash.concentration.top_picks.effective_bets} effective bets</b>{" "}
                  from {dash.concentration.top_picks.count} picks · {dash.concentration.top_picks.note}
                </div>
              )}
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
            </>
          )}

          {tab === "growth" && growth && (
            <>
              <TabIntro evidence={<EvidenceBadge rec={judged?.by_screen?.growth} />}>
                Growing businesses whose stock is already working.
              </TabIntro>
              <GrowthLeaders feed={growth} />
            </>
          )}

          {tab === "moonshots" && moonshots && (
            <>
              <TabIntro evidence={<EvidenceBadge rec={judged?.by_screen?.moonshot} />}>
                Volatile and beaten down — historically 19% doubled vs a 4.8% base rate. Size small.
              </TabIntro>
              <Moonshots feed={moonshots} />
            </>
          )}

          {tab === "themes" && <ThemeBoard data={themes} />}

          {tab === "movers" && (
            <>
              <TabIntro>Biggest moves today across the watchlist. A move is news, not a signal.</TabIntro>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {topGainers.map((s) => <StockCard key={s.ticker} s={s} />)}
              </div>
              {losers.length > 0 && (
                <div className="mt-3 text-xs text-ink-muted">
                  Biggest decliners: {losers.map((s, i) => (
                    <span key={s.ticker}>{i > 0 && " · "}
                      <Link to={`/analysis?ticker=${s.ticker}`} className="text-brand hover:underline">{s.ticker}</Link>{" "}
                      {Number(s["day_%"]).toFixed(1)}%
                    </span>
                  ))}
                </div>
              )}
            </>
          )}

          {tab === "sectors" && activeSector && (
            <>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {domains.map(([d, stocks]) => {
                  const avg = stocks.reduce((a, s) => a + s.score, 0) / stocks.length;
                  return (
                    <button key={d} onClick={() => setSector(d)}
                            className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
                              d === activeSector ? "bg-brand text-white border-brand"
                                : "border-line text-ink-secondary hover:border-brand"}`}>
                      {d} <span className="opacity-70 num">{avg.toFixed(0)}</span>
                    </button>
                  );
                })}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {(dash.domains[activeSector] ?? []).map((s) => <StockCard key={s.ticker} s={s} />)}
              </div>
            </>
          )}
        </div>
      </section>

      <div className="mt-3 text-2xs text-ink-muted">
        Backtests, pair trading and the score distribution are on{" "}
        <Link to="/research" className="text-brand hover:underline">Research</Link>.
      </div>
    </div>
  );
}

function TabIntro({ children, evidence }: { children: React.ReactNode; evidence?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2 mb-3 text-xs text-ink-muted">
      {evidence}
      <span>{children}</span>
    </div>
  );
}
