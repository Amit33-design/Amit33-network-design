import { useEffect, useState } from "react";
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
}
interface Dash {
  as_of: string;
  count: number;
  domains: Record<string, Stock[]>;
}

function Card({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${accent ?? "text-ink"}`}>{value}</div>
    </div>
  );
}

function StockCard({ s }: { s: Stock }) {
  const scoreColor = s.score >= 65 ? "#1b7f4b" : s.score >= 50 ? "#b7791f" : "#c0392b";
  return (
    <div className="bg-white rounded-xl shadow-sm p-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-bold text-alpha">{s.ticker}</span>
          <span className="ml-1 text-xs text-slate-400">{s.cycle === "bull" ? "▲" : "▼"}</span>
        </div>
        <span className="text-lg font-bold" style={{ color: scoreColor }}>{s.score}</span>
      </div>
      <div className="text-xs text-slate-500 truncate">{s.company}</div>
      <div className="mt-1 flex items-center justify-between text-xs">
        <span>{s.price != null ? `$${s.price}` : "—"}</span>
        <span className={(s["day_%"] ?? 0) >= 0 ? "text-alpha" : "text-red-600"}>
          {s["day_%"] != null ? `${s["day_%"] >= 0 ? "+" : ""}${s["day_%"]}%` : ""}
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between text-xs">
        <span className="text-slate-500">{s.action}</span>
        <span className="font-semibold" style={{ color: ["A", "B"].includes(s.quality_grade) ? "#1b7f4b" : "#64748b" }}>
          {s.quality_grade} · RSI {s.rsi ?? "—"}
        </span>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/dashboard.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("no dashboard data yet"))))
      .then(setDash)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading label="Loading dashboard…" />;
  if (error || !dash) return <ErrorBox error={error || "no data"} />;

  const all = Object.values(dash.domains).flat();
  const bullish = all.filter((s) => s.above_ema200 || s.score >= 60).length;
  const avg = all.length ? all.reduce((a, s) => a + s.score, 0) / all.length : 0;
  const regime = avg >= 60 ? "Risk-on" : avg >= 48 ? "Neutral" : "Risk-off";
  const buckets = [0, 20, 40, 50, 60, 70, 80].map((b, i, arr) => {
    const hi = arr[i + 1] ?? 101;
    return { label: `${b}-${hi === 101 ? 100 : hi}`, count: all.filter((s) => s.score >= b && s.score < hi).length };
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-ink">Dashboard — {dash.count} stocks across domains</h1>
        <span className="text-xs text-slate-400">as of {dash.as_of}</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card label="Tracked" value={String(dash.count)} />
        <Card label="Bullish" value={String(bullish)} accent="text-alpha" />
        <Card label="Avg Score" value={avg.toFixed(1)} />
        <Card label="Market" value={regime}
              accent={regime === "Risk-on" ? "text-alpha" : regime === "Risk-off" ? "text-red-600" : "text-amber-600"} />
      </div>

      {Object.entries(dash.domains).map(([domain, stocks]) => (
        stocks.length > 0 && (
          <div key={domain} className="mb-6">
            <div className="font-semibold text-ink mb-2">{domain}</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {stocks.map((s) => <StockCard key={s.ticker} s={s} />)}
            </div>
          </div>
        )
      ))}

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
