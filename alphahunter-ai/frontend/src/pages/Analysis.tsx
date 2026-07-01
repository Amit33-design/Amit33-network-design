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
  const verdictColor =
    data?.score >= 70 ? "#1b7f4b" : data?.score >= 45 ? "#b7791f" : "#c0392b";

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-ink">Technical Analysis — one ticker, real-time</h1>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap items-end gap-3 mb-6">
        <label className="text-sm">
          <div className="text-slate-400 mb-1">Ticker</div>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            className="border rounded px-3 py-2 w-36 font-mono uppercase"
            placeholder="AAPL"
          />
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

      {data && !loading && (
        <div className="space-y-6">
          {/* Verdict header */}
          <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap items-center gap-6">
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
            <div className="ml-auto text-center">
              <div className="text-xs uppercase tracking-wide text-slate-400">Technical Score</div>
              <div className="text-3xl font-bold" style={{ color: verdictColor }}>{data.score}</div>
            </div>
            <div className="text-center">
              <div className="text-xs uppercase tracking-wide text-slate-400">Signal</div>
              <div className="text-2xl font-bold px-4 py-1 rounded" style={{ color: verdictColor }}>
                {data.recommendation}
              </div>
            </div>
          </div>

          {/* Price chart with EMA overlays */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <div className="font-semibold text-ink mb-2">Price &amp; moving averages</div>
            <Plot
              data={[
                { x: data.chart.dates, y: data.chart.close, type: "scatter", mode: "lines",
                  name: "Close", line: { color: "#0b3d2e", width: 2 } },
                { x: data.chart.dates, y: data.chart.ema20, type: "scatter", mode: "lines",
                  name: "EMA20", line: { color: "#1f5fa6", width: 1 } },
                { x: data.chart.dates, y: data.chart.ema50, type: "scatter", mode: "lines",
                  name: "EMA50", line: { color: "#b7791f", width: 1 } },
                { x: data.chart.dates, y: data.chart.ema200, type: "scatter", mode: "lines",
                  name: "EMA200", line: { color: "#c0392b", width: 1.5 } },
              ]}
              layout={{
                autosize: true, height: 380, margin: { l: 45, r: 10, t: 10, b: 40 },
                legend: { orientation: "h", y: 1.12 }, xaxis: { title: { text: "" } },
                yaxis: { title: { text: "Price" } },
              }}
              useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }}
            />
          </div>

          {/* RSI subplot */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <div className="font-semibold text-ink mb-2">RSI (14)</div>
            <Plot
              data={[{ x: data.chart.dates, y: data.chart.rsi, type: "scatter", mode: "lines",
                       name: "RSI", line: { color: "#1b7f4b" } }]}
              layout={{
                autosize: true, height: 200, margin: { l: 45, r: 10, t: 10, b: 30 },
                yaxis: { range: [0, 100], title: { text: "RSI" } },
                shapes: [
                  { type: "line", x0: data.chart.dates[0], x1: data.chart.dates[data.chart.dates.length - 1],
                    y0: 70, y1: 70, line: { color: "#c0392b", width: 1, dash: "dot" } },
                  { type: "line", x0: data.chart.dates[0], x1: data.chart.dates[data.chart.dates.length - 1],
                    y0: 30, y1: 30, line: { color: "#1b7f4b", width: 1, dash: "dot" } },
                ],
              }}
              useResizeHandler style={{ width: "100%" }} config={{ displayModeBar: false }}
            />
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Indicator panel */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <div className="font-semibold text-ink mb-3">Indicators</div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <Row k="RSI (14)" v={ind.rsi} />
                <Row k="MACD hist" v={ind.macd_hist} />
                <Row k="EMA 20" v={fmt(ind.ema20)} />
                <Row k="EMA 50" v={fmt(ind.ema50)} />
                <Row k="EMA 200" v={fmt(ind.ema200)} />
                <Row k="ATR (14)" v={ind.atr} />
                <Row k="1M return" v={pct(ind.ret_1m)} />
                <Row k="3M return" v={pct(ind.ret_3m)} />
                <Row k="6M return" v={pct(ind.ret_6m)} />
                <Row k="1Y return" v={pct(ind.ret_1y)} />
                <Row k="vs 52w high" v={pct(ind.dist_52w_high)} />
                <Row k="vs 52w low" v={pct(ind.dist_52w_low)} />
                <Row k="52w high" v={fmt(ind.high_52w)} />
                <Row k="52w low" v={fmt(ind.low_52w)} />
                <Row k="Avg vol (20d)" v={ind.avg_volume?.toLocaleString()} />
              </div>
            </div>

            {/* Factors */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <div className="font-semibold text-ink mb-3">Why this signal</div>
              <ul className="space-y-2 text-sm">
                {data.factors.map((f: any, i: number) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className={
                      f.t === "bull" ? "text-alpha" : f.t === "bear" ? "text-red-600" : "text-slate-400"
                    }>
                      {f.t === "bull" ? "▲" : f.t === "bear" ? "▼" : "•"}
                    </span>
                    <span>{f.s}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 text-xs text-slate-400">
                Real-time technical read (price action only). Not financial advice.
              </div>
            </div>
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
