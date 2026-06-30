import { useEffect, useState } from "react";
import Plot from "react-plotly.js";
import { api } from "../lib/api";
import type { Recommendation } from "../lib/types";
import { ErrorBox, Loading } from "../components/Loading";

function Card({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${accent ?? "text-ink"}`}>{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const [rows, setRows] = useState<Recommendation[]>([]);
  const [market, setMarket] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.marketTop(100), api.morning().catch(() => null)])
      .then(([top, report]) => {
        setRows(top.results);
        setMarket(report?.market ?? null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const high = rows.filter((r) => r.confidence === "High").length;
  const avg = rows.length ? rows.reduce((s, r) => s + r.score, 0) / rows.length : 0;
  const buckets = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90].map((b) => ({
    label: `${b}-${b + 10}`,
    count: rows.filter((r) => r.score >= b && r.score < b + 10).length,
  }));

  return (
    <div>
      <h1 className="text-xl font-bold text-ink mb-4">Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card label="Setups Found" value={String(rows.length)} />
        <Card label="High Conviction" value={String(high)} accent="text-alpha" />
        <Card label="Avg AI Score" value={avg.toFixed(1)} />
        <Card
          label="Market Regime"
          value={market?.regime ?? "n/a"}
          accent={
            market?.risk_level === "low"
              ? "text-alpha"
              : market?.risk_level === "high"
              ? "text-red-600"
              : "text-amber-600"
          }
        />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-4">
          <div className="font-semibold text-ink mb-2">Score Distribution</div>
          <Plot
            data={[
              {
                type: "bar",
                x: buckets.map((b) => b.label),
                y: buckets.map((b) => b.count),
                marker: { color: "#1b7f4b" },
              },
            ]}
            layout={{
              autosize: true,
              height: 320,
              margin: { l: 40, r: 10, t: 10, b: 40 },
              xaxis: { title: { text: "AI score" } },
              yaxis: { title: { text: "count" } },
            }}
            useResizeHandler
            style={{ width: "100%" }}
            config={{ displayModeBar: false }}
          />
        </div>

        <div className="bg-white rounded-xl shadow-sm p-4">
          <div className="font-semibold text-ink mb-2">Top 10 by Score</div>
          <table className="w-full text-sm">
            <thead className="text-slate-400 text-left">
              <tr>
                <th className="py-1">Ticker</th>
                <th>Score</th>
                <th>Action</th>
                <th>Conf.</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 10).map((r) => (
                <tr key={r.ticker} className="border-t">
                  <td className="py-1 font-semibold text-alpha">{r.ticker}</td>
                  <td>{r.score.toFixed(1)}</td>
                  <td>{r.action}</td>
                  <td>{r.confidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
