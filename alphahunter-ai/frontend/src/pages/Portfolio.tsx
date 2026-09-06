import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { PortfolioResponse } from "../lib/types";
import { ErrorBox } from "../components/Loading";
import { buildPlan, checkExit, tradingDaysBetween, ACTION_LABEL,
         type ExitAction } from "../lib/exitRules";

const STORAGE_KEY = "alphahunter.portfolio";
// The 4th field (buy date) is optional and drives the time-stop. Without it a
// position can still hit its target or stop, it just never goes "stale".
const SAMPLE = `AAPL, 10, 150, 2026-08-20
MSFT, 5, 320, 2026-08-25
NVDA, 8, 95
PLTR, 12, 90`;

export default function Portfolio() {
  const [text, setText] = useState(SAMPLE);
  const [data, setData] = useState<PortfolioResponse | null>(null);
  const [live, setLive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState<string>("");
  // ticker -> buy date, kept from the textarea so the time-stop can be applied
  // to the API's response (which does not echo the date back).
  const [buyDates, setBuyDates] = useState<Record<string, string>>({});
  const [atrs, setAtrs] = useState<Record<string, number>>({});

  // Load saved holdings on first mount.
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const obj = JSON.parse(saved);
        if (obj.text) setText(obj.text);
        if (obj.savedAt) setSavedAt(obj.savedAt);
      } catch {
        /* ignore */
      }
    }
  }, []);

  function parse() {
    return text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => {
        const [ticker, qty, cost, date] = l.split(/[,\t]/).map((s) => s.trim());
        return {
          ticker: ticker.toUpperCase(), quantity: Number(qty), cost_basis: Number(cost),
          buy_date: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : undefined,
        };
      })
      .filter((p) => p.ticker && p.quantity > 0);
  }

  function save() {
    const when = new Date().toLocaleString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ text, savedAt: when }));
    setSavedAt(when);
  }

  async function analyze() {
    setLoading(true);
    setError("");
    try {
      const holdings = parse();
      setBuyDates(Object.fromEntries(
        holdings.filter((h) => h.buy_date).map((h) => [h.ticker, h.buy_date as string])));
      const { data, live } = await api.importPortfolio(holdings);
      setData(data);
      setLive(live);

      // ATR per holding, so exit levels scale to each stock rather than
      // applying one flat percentage to everything. Best-effort: without it
      // the plan falls back to fixed percentages.
      try {
        const r = await fetch("/api/quote", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tickers: holdings.map((h) => h.ticker) }),
        });
        if (r.ok) {
          const j = await r.json();
          const next: Record<string, number> = {};
          for (const [t, q] of Object.entries<any>(j.quotes || {})) {
            if (q?.atr) next[t] = q.atr;
          }
          setAtrs(next);
        }
      } catch { /* exits still work on fixed percentages */ }
      // Auto-save on every successful analyze so holdings persist.
      save();
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold tracking-tight text-ink">Portfolio Analyzer</h1>
        {data && (
          <span
            className={`text-xs px-2 py-1 rounded ${
              live ? "bg-gain-soft text-gain" : "bg-warn-soft text-warn"
            }`}
          >
            {live ? "● Live prices" : "● Snapshot prices"}
          </span>
        )}
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="panel p-4">
          <div className="text-sm text-ink-secondary mb-2">
            Holdings — <code>TICKER, qty, cost basis</code> per line.{" "}
            Add a <code>buy date</code> (<code>YYYY-MM-DD</code>) as a 4th field
            and the position also gets a time stop.
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            className="w-full border rounded p-2 font-mono text-sm"
          />
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={analyze}
              disabled={loading}
              className="bg-brand text-white px-4 py-2 rounded font-medium disabled:opacity-50"
            >
              {loading ? "Analyzing…" : "Analyze (live)"}
            </button>
            <button
              onClick={save}
              className="border border-line-strong text-ink px-3 py-2 rounded font-medium hover:bg-surface-sunken"
            >
              Save
            </button>
          </div>
          {savedAt && (
            <div className="mt-2 text-xs text-ink-muted">
              Saved on this device · {savedAt}
            </div>
          )}
        </div>

        <div className="md:col-span-2">
          {error && <ErrorBox error={error} />}
          {data && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                <Stat label="Market Value" value={`$${data.summary.market_value.toLocaleString()}`} />
                <Stat
                  label="Gain / Loss"
                  value={`$${data.summary.gain_loss.toLocaleString()} (${data.summary["gain_loss_%"]}%)`}
                  accent={data.summary.gain_loss >= 0 ? "text-brand" : "text-loss"}
                />
                <Stat label="Positions" value={String(data.summary.positions)} />
              </div>
              <div className="panel overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-ink-muted text-left bg-surface-sunken">
                    <tr>
                      {["Ticker", "Price", "Value", "G/L %", "Exit signal", "Score", "Recommendation"].map((h) => (
                        <th key={h} className="px-3 py-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.positions.map((p) => (
                      <tr key={p.ticker} className="border-t">
                        <td className="px-3 py-2 font-semibold text-brand">{p.ticker}</td>
                        <td className="px-3 py-2">{p.price != null ? `$${p.price}` : "—"}</td>
                        <td className="px-3 py-2">
                          {p.market_value != null ? `$${p.market_value.toLocaleString()}` : "—"}
                        </td>
                        <td
                          className={`px-3 py-2 ${
                            (p["gain_loss_%"] ?? 0) >= 0 ? "text-brand" : "text-loss"
                          }`}
                        >
                          {p["gain_loss_%"] != null ? `${p["gain_loss_%"]}%` : "—"}
                        </td>
                        <td className="px-3 py-2 align-top">
                          <ExitCell row={p} buyDate={buyDates[p.ticker]} atr={atrs[p.ticker]} />
                        </td>
                        <td className="px-3 py-2">{p.overall_score ?? "—"}</td>
                        <td className="px-3 py-2">
                          <div className="font-medium">{p.recommendation ?? p.error}</div>
                          {p.reason && (
                            <div className="text-xs text-ink-muted max-w-md">{p.reason}</div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-2 text-xs text-ink-muted">
                {live
                  ? "Live prices + an on-the-go technical Buy/Hold/Sell (trend, RSI, momentum, 52-week position) for every holding. Full AlphaHunter score shown when the ticker is in the latest scan."
                  : "Live quotes unavailable — showing snapshot prices. Recommendation shown for scanned tickers."}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const EXIT_TONE: Record<ExitAction, string> = {
  take_profit: "bg-gain-soft text-gain border-gain/30",
  sell: "bg-loss-soft text-loss border-loss/30",
  close_stale: "bg-warn-soft text-warn border-warn/30",
  hold: "bg-surface-sunken text-ink-secondary border-line",
};

// Turns "I own this at $X" into "sell it / hold it, and here is why". The
// product could always say Buy and never Sell; this is the other half.
function ExitCell({ row, buyDate, atr }: { row: any; buyDate?: string; atr?: number }) {
  const entry = row.cost_basis ?? row.entry;
  const price = row.price;
  if (!entry || price == null) return <span className="text-ink-muted">—</span>;

  const plan = buildPlan(entry, { atr });
  const daysHeld = buyDate ? tradingDaysBetween(buyDate) : 0;
  const out = checkExit(plan, price, { daysHeld });

  return (
    <div className="min-w-[13rem]">
      <span className={`inline-block rounded border px-2 py-0.5 text-2xs font-bold tracking-wide ${EXIT_TONE[out.action]}`}>
        {ACTION_LABEL[out.action]}
      </span>
      <div className="mt-1 text-xs text-ink-secondary">{out.reason}</div>
      {!buyDate && (
        <div className="mt-0.5 text-2xs text-ink-muted">
          add a buy date (4th field) to enable the time stop
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="panel p-3">
      <div className="text-xs uppercase tracking-wide text-ink-muted">{label}</div>
      <div className={`text-lg font-bold ${accent ?? "text-ink"}`}>{value}</div>
    </div>
  );
}
