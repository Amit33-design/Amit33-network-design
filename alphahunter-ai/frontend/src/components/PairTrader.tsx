// Pair trading: choose a pair, hold it at fixed weights, get a daily order.
//
// The candidate list comes from the committed pair study (volatility and
// correlation, not backtested profit — ranking on profit just picks whatever
// went up). Holdings are device-local; prices come from /api/quote.
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, StatTile } from "./ui";
import {
  dailyOrder, getPair, onPairChange, openPosition, savePair,
  type Order, type PairPick,
} from "../lib/pairTrading";

type Candidate = {
  pair: string; a: string; b: string;
  "vol_a_%": number; "vol_b_%": number;
  correlation: number; "expected_bonus_%": number;
  realistic?: { "cagr_%": number; "max_drawdown_%": number;
                beat_best_single_stock: boolean };
};
type Study = { pairs: Candidate[]; walk_forward?: any };

export function usePairStudy(): Study | null {
  const [d, setD] = useState<Study | null>(null);
  useEffect(() => {
    fetch("/pair_study.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => setD(j?.pairs?.length ? j : null))
      .catch(() => setD(null));
  }, []);
  return d;
}

const money = (v: number) => `$${Math.round(v).toLocaleString()}`;

export default function PairTrader({ study }: { study: Study }) {
  const [pick, setPick] = useState<PairPick | null>(getPair);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [capital, setCapital] = useState(25000);
  const [loading, setLoading] = useState(false);

  useEffect(() => onPairChange(() => setPick(getPair())), []);

  // Live prices for whichever pair is selected (or the top candidate, so the
  // "open a position" preview shows real numbers before you commit).
  const watch = pick ? [pick.a, pick.b] : [study.pairs[0]?.a, study.pairs[0]?.b];
  useEffect(() => {
    const tickers = watch.filter(Boolean) as string[];
    if (!tickers.length) return;
    setLoading(true);
    fetch("/api/quote", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        const next: Record<string, number> = {};
        for (const [t, q] of Object.entries<any>(j?.quotes || {})) {
          if (q?.price) next[t] = q.price;
        }
        setPrices(next);
      })
      .catch(() => setPrices({}))
      .finally(() => setLoading(false));
  }, [watch.join(",")]);

  const order: Order | null = useMemo(() => {
    if (!pick) return null;
    const pa = prices[pick.a], pb = prices[pick.b];
    if (!pa || !pb) return null;
    return dailyOrder(pick.a, pick.b, pa, pb, pick.sharesA, pick.sharesB,
                      { targetA: pick.targetA });
  }, [pick, prices]);

  function choose(c: Candidate) {
    const pa = prices[c.a], pb = prices[c.b];
    if (!pa || !pb) {
      savePair({ a: c.a, b: c.b, targetA: 0.5, sharesA: 0, sharesB: 0 });
      return;
    }
    const open = openPosition(c.a, c.b, pa, pb, capital);
    savePair({
      a: c.a, b: c.b, targetA: 0.5,
      sharesA: open.buy[0].shares, sharesB: open.buy[1].shares,
      openedAt: new Date().toISOString().slice(0, 10),
    });
  }

  function applyOrder() {
    if (!pick || !order || order.action !== "rebalance") return;
    const next = { ...pick };
    const sellA = order.sell!.ticker === pick.a;
    if (sellA) { next.sharesA -= order.sell!.shares; next.sharesB += order.buy!.shares; }
    else { next.sharesB -= order.sell!.shares; next.sharesA += order.buy!.shares; }
    savePair(next);
  }

  return (
    <div className="space-y-3">
      {/* The finding that governs how to read all of this. */}
      <div className="text-xs text-warn border border-warn/30 bg-warn-soft rounded-panel px-3 py-2">
        <b>Read this first.</b> Walk-forward tested, pair rebalancing did
        <b> not</b> beat simply holding the better of its two stocks. Picking pairs
        on past profit decayed 2.4× worse than picking on volatility and
        correlation. What this reliably gives you is a <b>smoother ride</b> than
        one volatile name — lower drawdown, not higher return. Size it as a risk
        tool, not an income engine.
      </div>

      {/* --- the book you hold ------------------------------------------- */}
      {pick && (
        <div className="panel p-3">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
            <div className="font-semibold text-ink text-sm">
              📘 Your pair: <Link to={`/analysis?ticker=${pick.a}`} className="text-brand hover:underline">{pick.a}</Link>
              {" / "}
              <Link to={`/analysis?ticker=${pick.b}`} className="text-brand hover:underline">{pick.b}</Link>
            </div>
            <button onClick={() => savePair(null)}
                    className="text-2xs text-ink-muted hover:text-loss">clear</button>
          </div>

          {!order ? (
            <div className="text-xs text-ink-muted">
              {loading ? "Fetching live prices…"
                : "Live prices unavailable — the daily order needs /api/quote."}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-2">
                <StatTile label="Book value" value={money(order.totalValue)} />
                <StatTile label={`${pick.a} weight`}
                          value={`${(order.weightA * 100).toFixed(1)}%`}
                          sub={`target ${(pick.targetA * 100).toFixed(0)}%`} />
                <StatTile label="Drift"
                          value={`${order.driftPp >= 0 ? "+" : ""}${order.driftPp.toFixed(1)}pp`}
                          tone={Math.abs(order.driftPp) > 3 ? "warn" : "gain"} />
                <StatTile label="Holdings"
                          value={`${pick.sharesA} / ${pick.sharesB}`}
                          sub="shares A / B" />
              </div>

              <div className={`rounded-panel border px-3 py-2 ${
                order.action === "rebalance"
                  ? "border-brand/40 bg-brand/10" : "border-line bg-surface-sunken"}`}>
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge tone={order.action === "rebalance" ? "brand" : "neutral"}>
                    {order.action === "rebalance" ? "TODAY: REBALANCE" : "TODAY: HOLD"}
                  </Badge>
                  {order.action === "rebalance" && (
                    <>
                      <span className="text-sm num">
                        <b className="text-loss">SELL {order.sell!.shares} {order.sell!.ticker}</b>
                        {" "}({money(order.sell!.value)}){"  →  "}
                        <b className="text-gain">BUY {order.buy!.shares} {order.buy!.ticker}</b>
                        {" "}({money(order.buy!.value)})
                      </span>
                      <button onClick={applyOrder}
                              className="ml-auto text-2xs border border-line-strong rounded px-2 py-0.5 hover:bg-surface-sunken">
                        mark as done
                      </button>
                    </>
                  )}
                </div>
                <div className="mt-1 text-xs text-ink-secondary">{order.reason}</div>
                {order.warnings.map((w) => (
                  <div key={w} className="mt-0.5 text-2xs text-warn">{w}</div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* --- candidates --------------------------------------------------- */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="label-eyebrow">Candidate pairs</span>
          <label className="text-2xs text-ink-muted flex items-center gap-1">
            capital
            <input type="number" min={1000} step={1000} value={capital}
                   onChange={(e) => setCapital(Math.max(0, +e.target.value))}
                   className="px-1 py-0.5 w-24 text-xs num" />
          </label>
        </div>
        <div className="overflow-x-auto thin-scroll">
          <table className="table-data">
            <thead>
              <tr>{["Pair", "Vol A / B", "Corr", "Harvest", "Backtest CAGR",
                    "Max DD", "Beat best leg?", ""].map((h) => <th key={h}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {study.pairs.slice(0, 10).map((c) => {
                const selected = pick?.a === c.a && pick?.b === c.b;
                return (
                  <tr key={c.pair} className={selected ? "bg-brand/10" : undefined}>
                    <td className="font-semibold text-brand">{c.pair}</td>
                    <td className="num">{c["vol_a_%"].toFixed(0)}% / {c["vol_b_%"].toFixed(0)}%</td>
                    <td className={`num ${c.correlation < 0.3 ? "text-gain" : "text-warn"}`}>
                      {c.correlation.toFixed(2)}
                    </td>
                    <td className="num">{c["expected_bonus_%"].toFixed(1)}%</td>
                    <td className={`num ${(c.realistic?.["cagr_%"] ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>
                      {c.realistic ? `${c.realistic["cagr_%"].toFixed(1)}%` : "—"}
                    </td>
                    <td className="num text-loss">
                      {c.realistic ? `${c.realistic["max_drawdown_%"].toFixed(0)}%` : "—"}
                    </td>
                    <td>
                      {c.realistic
                        ? <Badge tone={c.realistic.beat_best_single_stock ? "gain" : "loss"}>
                            {c.realistic.beat_best_single_stock ? "yes" : "no"}
                          </Badge>
                        : "—"}
                    </td>
                    <td className="text-right">
                      <button onClick={() => choose(c)}
                              className="text-2xs border border-line-strong rounded px-2 py-0.5 hover:bg-surface-sunken">
                        {selected ? "reselect" : "select"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-1 text-2xs text-ink-muted">
          Ranked by harvest (volatility × low correlation), not by backtest profit —
          ranking on profit just picks whichever two stocks went up. "Beat best leg"
          is the column that matters: <b>no</b> means you'd have done better owning
          one of them outright.
        </div>
      </div>
    </div>
  );
}
