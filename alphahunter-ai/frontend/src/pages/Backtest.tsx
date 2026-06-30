import { useState } from "react";
import { api } from "../lib/api";
import { ErrorBox } from "../components/Loading";

export default function Backtest() {
  const [ticker, setTicker] = useState("AAPL");
  const [hold, setHold] = useState(10);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setLoading(true);
    setError("");
    try {
      setResult(await api.backtest(ticker.toUpperCase(), hold));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  const metrics: [string, string][] = result
    ? [
        ["Trades", String(result.trades)],
        ["Win Rate", `${(result.win_rate * 100).toFixed(0)}%`],
        ["Avg Return", `${result["avg_return_%"]}%`],
        ["Median Return", `${result["median_return_%"]}%`],
        ["Max Drawdown", `${result["max_drawdown_%"]}%`],
        ["Sharpe", String(result.sharpe)],
        ["Sortino", String(result.sortino)],
        ["Profit Factor", String(result.profit_factor)],
        ["Avg Hold (days)", String(result.avg_hold_days)],
      ]
    : [];

  return (
    <div>
      <h1 className="text-xl font-bold text-ink mb-4">Backtest — Oversold Setup</h1>
      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap items-end gap-3 mb-6">
        <label className="text-sm">
          <div className="text-slate-400 mb-1">Ticker</div>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="border rounded px-3 py-2 w-32 font-mono uppercase"
          />
        </label>
        <label className="text-sm">
          <div className="text-slate-400 mb-1">Hold (days)</div>
          <input
            type="number"
            value={hold}
            min={1}
            max={120}
            onChange={(e) => setHold(Number(e.target.value))}
            className="border rounded px-3 py-2 w-28"
          />
        </label>
        <button
          onClick={run}
          disabled={loading}
          className="bg-alpha text-white px-4 py-2 rounded font-medium disabled:opacity-50"
        >
          {loading ? "Running…" : "Run Backtest"}
        </button>
      </div>

      {error && <ErrorBox error={error} />}
      {result && !result.error && (
        <div className="grid grid-cols-3 md:grid-cols-3 gap-3">
          {metrics.map(([k, v]) => (
            <div key={k} className="bg-white rounded-xl shadow-sm p-4">
              <div className="text-xs uppercase tracking-wide text-slate-400">{k}</div>
              <div className="text-xl font-bold text-ink mt-1">{v}</div>
            </div>
          ))}
        </div>
      )}
      {result?.error && <div className="text-slate-500">No data for {ticker}.</div>}
    </div>
  );
}
