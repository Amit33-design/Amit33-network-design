import { useState } from "react";
import { api } from "../lib/api";
import type { PortfolioResponse } from "../lib/types";
import { ErrorBox } from "../components/Loading";

const SAMPLE = `AAPL, 10, 150
MSFT, 5, 320
NVDA, 8, 95`;

export default function Portfolio() {
  const [text, setText] = useState(SAMPLE);
  const [data, setData] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function parse() {
    return text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => {
        const [ticker, qty, cost] = l.split(/[,\t]/).map((s) => s.trim());
        return { ticker: ticker.toUpperCase(), quantity: Number(qty), cost_basis: Number(cost) };
      })
      .filter((p) => p.ticker && p.quantity > 0);
  }

  async function analyze() {
    setLoading(true);
    setError("");
    try {
      setData(await api.importPortfolio(parse()));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-ink mb-4">Portfolio Analyzer</h1>
      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-4">
          <div className="text-sm text-slate-500 mb-2">
            Paste holdings — <code>TICKER, qty, cost basis</code> per line:
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            className="w-full border rounded p-2 font-mono text-sm"
          />
          <button
            onClick={analyze}
            disabled={loading}
            className="mt-3 bg-alpha text-white px-4 py-2 rounded font-medium disabled:opacity-50"
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </div>

        <div className="md:col-span-2">
          {error && <ErrorBox error={error} />}
          {data && (
            <>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <Stat label="Market Value" value={`$${data.summary.market_value.toLocaleString()}`} />
                <Stat
                  label="Gain / Loss"
                  value={`$${data.summary.gain_loss.toLocaleString()} (${data.summary["gain_loss_%"]}%)`}
                  accent={data.summary.gain_loss >= 0 ? "text-alpha" : "text-red-600"}
                />
                <Stat label="Positions" value={String(data.summary.positions)} />
              </div>
              <div className="bg-white rounded-xl shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-slate-400 text-left bg-slate-50">
                    <tr>
                      {["Ticker", "Price", "Value", "G/L %", "Score", "Recommendation"].map((h) => (
                        <th key={h} className="px-3 py-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.positions.map((p) => (
                      <tr key={p.ticker} className="border-t">
                        <td className="px-3 py-2 font-semibold text-alpha">{p.ticker}</td>
                        <td className="px-3 py-2">{p.price != null ? `$${p.price}` : "—"}</td>
                        <td className="px-3 py-2">
                          {p.market_value != null ? `$${p.market_value.toLocaleString()}` : "—"}
                        </td>
                        <td
                          className={`px-3 py-2 ${
                            (p["gain_loss_%"] ?? 0) >= 0 ? "text-alpha" : "text-red-600"
                          }`}
                        >
                          {p["gain_loss_%"] != null ? `${p["gain_loss_%"]}%` : "—"}
                        </td>
                        <td className="px-3 py-2">{p.overall_score ?? "—"}</td>
                        <td className="px-3 py-2 font-medium">{p.recommendation ?? p.error}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`text-lg font-bold ${accent ?? "text-ink"}`}>{value}</div>
    </div>
  );
}
