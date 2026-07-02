import { useState } from "react";
import Plot from "react-plotly.js";
import { api } from "../lib/api";
import { ErrorBox, Loading } from "../components/Loading";

const RANGES = ["6mo", "1y", "2y", "5y"];

export default function Analysis() {
  const [ticker, setTicker] = useState("AAPL");
  const [range, setRange] = useState("1y");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run(sym = ticker, rng = range) {
    setLoading(true);
    setError("");
    try {
      setData(await api.technicalAnalysis(sym.toUpperCase(), rng));
    } catch (e) {
      setError(String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  const ind = data?.indicators;
  const ch = data?.chart;
  const verdictColor = data?.score >= 70 ? "#1b7f4b" : data?.score >= 45 ? "#b7791f" : "#c0392b";

  // Cycle shading (bull=green, bear=red) as background rects across each phase.
  const cycleShapes = (data?.cycle?.phases || []).map((p: any) => ({
    type: "rect", xref: "x", yref: "paper", x0: p.start, x1: p.end, y0: 0, y1: 1,
    fillcolor: p.type === "bull" ? "rgba(27,127,75,0.06)" : "rgba(192,57,43,0.06)",
    line: { width: 0 }, layer: "below",
  }));
  // Support (green) / resistance (red) horizontal lines.
  const levelShapes = [
    ...(data?.levels?.support || []).map((y: number) => ({
      type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: y, y1: y,
      line: { color: "#1b7f4b", width: 1, dash: "dash" },
    })),
    ...(data?.levels?.resistance || []).map((y: number) => ({
      type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: y, y1: y,
      line: { color: "#c0392b", width: 1, dash: "dash" },
    })),
  ];

  // Signal markers plotted on the close price at their dates.
  const closeByDate: Record<string, number> = {};
  if (ch) ch.dates.forEach((d: string, i: number) => (closeByDate[d] = ch.close[i]));
  const bullSig = (data?.signals || []).filter((s: any) => s.type === "bull");
  const bearSig = (data?.signals || []).filter((s: any) => s.type === "bear");

  const cycleBadge = data?.cycle && (
    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
      data.cycle.current === "bull" ? "bg-emerald-50 text-emerald-700"
        : data.cycle.current === "bear" ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-600"
    }`}>
      {data.cycle.current === "bull" ? "▲ Bullish cycle" : data.cycle.current === "bear" ? "▼ Bearish cycle" : "Neutral"}
      {data.cycle.days_in_phase != null && ` · ${data.cycle.days_in_phase}d`}
    </span>
  );

  return (
    <div>
      <h1 className="text-xl font-bold text-ink mb-4">Technical Analysis — one ticker, real-time</h1>

      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap items-end gap-3 mb-6">
        <label className="text-sm">
          <div className="text-slate-400 mb-1">Ticker</div>
          <input value={ticker} onChange={(e) => setTicker(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && run()}
                 className="border rounded px-3 py-2 w-36 font-mono uppercase" placeholder="AAPL" />
        </label>
        <label className="text-sm">
          <div className="text-slate-400 mb-1">Range</div>
          <select value={range} onChange={(e) => { setRange(e.target.value); if (data) run(ticker, e.target.value); }}
                  className="border rounded px-3 py-2">
            {RANGES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        <button onClick={() => run()} disabled={loading}
                className="bg-alpha text-white px-5 py-2 rounded font-medium disabled:opacity-50">
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </div>

      {loading && <Loading label="Fetching real-time data…" />}
      {error && <ErrorBox error={error} />}

      {data && !loading && ch && (
        <div className="space-y-6">
          {/* Verdict header */}
          <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap items-center gap-4">
            <div>
              <div className="text-2xl font-bold text-ink">
                {data.ticker} <span className="text-base font-normal text-slate-500">{data.name}</span>
              </div>
              <div className="text-lg">
                ${Number(data.price).toFixed(2)}{" "}
                <span className={data.day_change_pct >= 0 ? "text-alpha" : "text-red-600"}>
                  {data.day_change_pct != null ? `${data.day_change_pct >= 0 ? "+" : ""}${data.day_change_pct.toFixed(2)}%` : ""}
                </span>
              </div>
            </div>
            <div className="sm:ml-auto flex items-center gap-4 flex-wrap">
              {cycleBadge}
              <div className="text-center">
                <div className="text-xs uppercase tracking-wide text-slate-400">Score</div>
                <div className="text-3xl font-bold" style={{ color: verdictColor }}>{data.score}</div>
              </div>
              <div className="text-center">
                <div className="text-xs uppercase tracking-wide text-slate-400">Signal</div>
                <div className="text-2xl font-bold" style={{ color: verdictColor }}>{data.recommendation}</div>
              </div>
            </div>
            {data.verdict_reason && (
              <div className="w-full mt-1 pt-2 border-t border-slate-100 text-sm text-slate-600">
                <span className="font-semibold text-ink">Why: </span>{data.verdict_reason}
              </div>
            )}
          </div>

          {/* Potential bottom */}
          {data.bottom && (
            <div className={`rounded-xl shadow-sm p-4 border ${
              data.bottom.likelihood === "high" ? "bg-emerald-50 border-emerald-200"
                : data.bottom.likelihood === "possible" ? "bg-amber-50 border-amber-200"
                : "bg-white border-slate-100"
            }`}>
              <div className="flex items-center gap-3 flex-wrap">
                <span className="font-bold text-ink">🔻 Potential bottom</span>
                <span className={`text-sm font-semibold px-2 py-0.5 rounded ${
                  data.bottom.likelihood === "high" ? "bg-emerald-100 text-emerald-800"
                    : data.bottom.likelihood === "possible" ? "bg-amber-100 text-amber-800"
                    : "bg-slate-100 text-slate-600"
                }`}>
                  {data.bottom.likelihood === "high" ? "HIGH likelihood"
                    : data.bottom.likelihood === "possible" ? "POSSIBLE"
                    : "LOW likelihood"} · {data.bottom.score}/100
                </span>
                {data.bottom.firing != null && (
                  <span className="text-xs text-slate-500">
                    {data.bottom.firing} of {data.bottom.total} reversal tells firing
                  </span>
                )}
              </div>
              {/* Full checklist: what's firing and what's missing */}
              {data.bottom.checks?.length ? (
                <ul className="mt-2 grid sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
                  {data.bottom.checks.map((ch: any, i: number) => (
                    <li key={i} className={`flex items-start gap-2 ${ch.ok ? "text-emerald-700" : "text-slate-400"}`}>
                      <span>{ch.ok ? "✓" : "✗"}</span>
                      <span>{ch.s}{ch.ok ? ` (+${ch.pts})` : ""}</span>
                    </li>
                  ))}
                </ul>
              ) : data.bottom.factors?.length > 0 ? (
                <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  {data.bottom.factors.map((f: any, i: number) => (
                    <li key={i} className="text-alpha">▲ {f.s}</li>
                  ))}
                </ul>
              ) : (
                <div className="mt-2 text-sm text-slate-500">No bottoming signals firing right now.</div>
              )}
              <div className="mt-2 text-xs text-slate-400">
                {data.bottom.explainer ??
                  "Score sums classic reversal tells (oversold RSI, RSI divergence, 52-week-low/support test, capitulation candle, 20-EMA reclaim). <35 low · 35-59 possible · ≥60 high."}
              </div>
            </div>
          )}

          {/* CSP-on-dip signal */}
          {data.csp_signal && (
            <div className={`rounded-xl shadow-sm p-4 border ${
              data.csp_signal.active
                ? "bg-emerald-50 border-emerald-200"
                : "bg-white border-slate-100"
            }`}>
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`font-bold ${data.csp_signal.active ? "text-emerald-700" : "text-slate-500"}`}>
                  {data.csp_signal.active
                    ? `💰 Cash-Secured Put opportunity (${data.csp_signal.strength})`
                    : "Cash-Secured Put signal: not today"}
                </span>
                {data.csp_signal.active && data.csp_signal.suggested_strike != null && (
                  <span className="text-sm font-semibold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded">
                    suggested strike ≈ ${data.csp_signal.suggested_strike}
                  </span>
                )}
                {data.dip_bounce?.dips >= 3 && (
                  <span className="text-xs text-slate-500">
                    history: {data.dip_bounce.dips} similar dips, {(data.dip_bounce.win_rate * 100).toFixed(0)}% bounced,
                    avg {data.dip_bounce.avg_return >= 0 ? "+" : ""}{data.dip_bounce.avg_return}% in 10d
                  </span>
                )}
              </div>
              <div className="mt-1 text-sm text-slate-600">{data.csp_signal.reason}</div>
            </div>
          )}

          {/* Candlestick + Bollinger + EMAs + S/R + cycle shading + signals */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <div className="font-semibold text-ink mb-2">Price · candlesticks, Bollinger Bands, moving averages, support/resistance</div>
            <Plot
              data={([
                { type: "candlestick", x: ch.dates, open: ch.open, high: ch.high, low: ch.low, close: ch.close,
                  name: "Price", increasing: { line: { color: "#1b7f4b" } }, decreasing: { line: { color: "#c0392b" } } },
                { x: ch.dates, y: ch.bb_upper, type: "scatter", mode: "lines", name: "BB upper",
                  line: { color: "#94a3b8", width: 1 } },
                { x: ch.dates, y: ch.bb_lower, type: "scatter", mode: "lines", name: "BB lower",
                  line: { color: "#94a3b8", width: 1 }, fill: "tonexty", fillcolor: "rgba(148,163,184,0.08)" },
                { x: ch.dates, y: ch.ema50, type: "scatter", mode: "lines", name: "EMA50", line: { color: "#b7791f", width: 1 } },
                { x: ch.dates, y: ch.ema200, type: "scatter", mode: "lines", name: "EMA200", line: { color: "#1f5fa6", width: 1.5 } },
                { x: bullSig.map((s: any) => s.date), y: bullSig.map((s: any) => closeByDate[s.date]),
                  type: "scatter", mode: "markers", name: "Bull signal",
                  marker: { symbol: "triangle-up", size: 11, color: "#1b7f4b" },
                  text: bullSig.map((s: any) => s.label), hoverinfo: "text+x" },
                { x: bearSig.map((s: any) => s.date), y: bearSig.map((s: any) => closeByDate[s.date]),
                  type: "scatter", mode: "markers", name: "Bear signal",
                  marker: { symbol: "triangle-down", size: 11, color: "#c0392b" },
                  text: bearSig.map((s: any) => s.label), hoverinfo: "text+x" },
              ]) as any}
              layout={{
                autosize: true, height: 460, margin: { l: 50, r: 10, t: 10, b: 30 },
                legend: { orientation: "h", y: 1.1 }, xaxis: { rangeslider: { visible: false } },
                yaxis: { title: { text: "Price" } }, shapes: [...cycleShapes, ...levelShapes],
              } as any}
              useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }}
            />
            <div className="text-xs text-slate-400 mt-1">
              Green/red shading marks bullish/bearish cycles (50-day vs 200-day trend). Dashed lines = support (green) / resistance (red). ▲▼ = crossover/breakout signals.
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Volume */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <div className="font-semibold text-ink mb-2">Volume</div>
              <Plot
                data={[{ type: "bar", x: ch.dates, y: ch.volume, name: "Volume",
                         marker: { color: ch.close.map((c: number, i: number) => (i > 0 && c >= ch.close[i - 1] ? "#1b7f4b" : "#c0392b")) } }]}
                layout={{ autosize: true, height: 220, margin: { l: 50, r: 10, t: 10, b: 30 }, yaxis: { title: { text: "Vol" } } }}
                useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }}
              />
            </div>
            {/* MACD */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <div className="font-semibold text-ink mb-2">MACD (12, 26, 9)</div>
              <Plot
                data={[
                  { type: "bar", x: ch.dates, y: ch.macd_hist, name: "Hist",
                    marker: { color: ch.macd_hist.map((h: number) => (h >= 0 ? "#1b7f4b" : "#c0392b")) } },
                  { x: ch.dates, y: ch.macd, type: "scatter", mode: "lines", name: "MACD", line: { color: "#0b3d2e" } },
                  { x: ch.dates, y: ch.macd_signal, type: "scatter", mode: "lines", name: "Signal", line: { color: "#b7791f" } },
                ]}
                layout={{ autosize: true, height: 220, margin: { l: 50, r: 10, t: 10, b: 30 }, legend: { orientation: "h", y: 1.2 } }}
                useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }}
              />
            </div>
          </div>

          {/* RSI */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <div className="font-semibold text-ink mb-2">RSI (14)</div>
            <Plot
              data={[{ x: ch.dates, y: ch.rsi, type: "scatter", mode: "lines", name: "RSI", line: { color: "#1b7f4b" } }]}
              layout={{
                autosize: true, height: 200, margin: { l: 50, r: 10, t: 10, b: 30 }, yaxis: { range: [0, 100] },
                shapes: [30, 70].map((y) => ({ type: "line", x0: ch.dates[0], x1: ch.dates[ch.dates.length - 1], y0: y, y1: y,
                  line: { color: y === 70 ? "#c0392b" : "#1b7f4b", width: 1, dash: "dot" } })),
              }}
              useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }}
            />
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Indicators */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <div className="font-semibold text-ink mb-3">Indicators</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <Row k="RSI (14)" v={ind.rsi} />
                <Row k="MACD hist" v={ind.macd_hist} />
                <Row k="EMA 50" v={fmt(ind.ema50)} />
                <Row k="EMA 200" v={fmt(ind.ema200)} />
                <Row k="ATR (14)" v={ind.atr} />
                <Row k="1M" v={pct(ind.ret_1m)} />
                <Row k="3M" v={pct(ind.ret_3m)} />
                <Row k="6M" v={pct(ind.ret_6m)} />
                <Row k="1Y" v={pct(ind.ret_1y)} />
                <Row k="vs 52w hi" v={pct(ind.dist_52w_high)} />
                <Row k="vs 52w lo" v={pct(ind.dist_52w_low)} />
                <Row k="Avg vol" v={ind.avg_volume?.toLocaleString()} />
              </div>
            </div>
            {/* Levels */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <div className="font-semibold text-ink mb-3">Support &amp; Resistance</div>
              <div className="text-sm">
                <div className="text-red-600 font-medium mb-1">Resistance</div>
                {(data.levels?.resistance || []).length
                  ? data.levels.resistance.map((r: number) => <div key={r} className="pl-2">${r}</div>)
                  : <div className="pl-2 text-slate-400">— none above price —</div>}
                <div className="text-alpha font-medium mt-3 mb-1">Support</div>
                {(data.levels?.support || []).length
                  ? data.levels.support.map((s: number) => <div key={s} className="pl-2">${s}</div>)
                  : <div className="pl-2 text-slate-400">— none below price —</div>}
              </div>
            </div>
            {/* Signals + factors */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <div className="font-semibold text-ink mb-3">Recent signals</div>
              <ul className="space-y-1.5 text-sm">
                {(data.signals || []).length ? data.signals.map((s: any, i: number) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className={s.type === "bull" ? "text-alpha" : "text-red-600"}>{s.type === "bull" ? "▲" : "▼"}</span>
                    <span><span className="text-slate-400">{s.date}</span> — {s.label}</span>
                  </li>
                )) : <li className="text-slate-400">No crossovers in the last 90 days.</li>}
              </ul>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-4">
            <div className="font-semibold text-ink mb-3">Why this signal</div>
            <ul className="grid md:grid-cols-2 gap-x-8 gap-y-2 text-sm">
              {data.factors.map((f: any, i: number) => (
                <li key={i} className="flex items-start gap-2">
                  <span className={f.t === "bull" ? "text-alpha" : f.t === "bear" ? "text-red-600" : "text-slate-400"}>
                    {f.t === "bull" ? "▲" : f.t === "bear" ? "▼" : "•"}
                  </span>
                  <span>{f.s}</span>
                </li>
              ))}
            </ul>
            <div className="mt-4 text-xs text-slate-400">Real-time technical read (price action only). Not financial advice.</div>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: any }) {
  return (
    <>
      <div className="text-slate-500">{k}</div>
      <div className="text-right font-medium">{v ?? "—"}</div>
    </>
  );
}
const fmt = (x: any) => (x == null ? "—" : `$${Number(x).toFixed(2)}`);
const pct = (x: any) => (x == null ? "—" : `${x >= 0 ? "+" : ""}${Number(x).toFixed(1)}%`);
