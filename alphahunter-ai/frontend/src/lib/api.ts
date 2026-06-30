// Thin fetch wrapper. Live calls go through /api, which Vite proxies to the
// FastAPI backend (see vite.config.ts).
//
// STATIC-DEPLOY FALLBACK: when no backend is reachable (e.g. the site is served
// statically on Vercel with no API connected), market/options reads fall back
// to a precomputed snapshot bundled at /snapshot.json, so the deployed site
// still shows real data. `isSnapshot()` lets the UI show a banner in that mode.
import type { PortfolioResponse, Recommendation, ScanResponse } from "./types";

const BASE = "/api";

let snapshotMode = false;
export const isSnapshot = () => snapshotMode;

// Metadata about the bundled snapshot, so the UI can show its date and whether
// it came from a real scan (the daily workflow sets live:true) vs the seed.
export interface SnapshotMeta {
  date: string;
  live: boolean;
}
let snapshotMeta: SnapshotMeta = { date: "2026-06-25", live: false };
export const snapshotInfo = () => snapshotMeta;

let snapshotCache: Recommendation[] | null = null;
async function loadSnapshot(): Promise<Recommendation[]> {
  if (snapshotCache) return snapshotCache;
  const res = await fetch("/snapshot.json");
  if (!res.ok) throw new Error("no snapshot available");
  const data = await res.json();
  snapshotMeta = { date: data.date ?? "unknown", live: data.live === true };
  snapshotCache = data.results as Recommendation[];
  return snapshotCache;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// Try the live backend; on any failure, fall back to the bundled snapshot
// (optionally filtered) and flip snapshotMode so the UI can flag it.
async function scanWithFallback(
  path: string,
  filter?: (r: Recommendation) => boolean
): Promise<ScanResponse> {
  try {
    const live = await get<ScanResponse>(path);
    snapshotMode = false;
    return live;
  } catch {
    const all = await loadSnapshot();
    snapshotMode = true;
    const results = filter ? all.filter(filter) : all;
    return { count: results.length, results };
  }
}

// Client-side portfolio analysis against the snapshot, used when no backend is
// reachable. Tickers present in the latest scan get a real price/score/rec;
// others are flagged so the user knows to run a live scan for full coverage.
async function portfolioFromSnapshot(
  positions: { ticker: string; quantity: number; cost_basis: number }[]
): Promise<PortfolioResponse> {
  const all = await loadSnapshot();
  snapshotMode = true;
  const byTicker = new Map(all.map((r) => [r.ticker.toUpperCase(), r]));
  let mv = 0;
  let cost = 0;
  const rows = positions.map((p) => {
    const rec = byTicker.get(p.ticker.toUpperCase());
    if (!rec || rec.metrics?.price == null) {
      return { ticker: p.ticker.toUpperCase(), error: "not in latest scan" };
    }
    const price = Number(rec.metrics.price);
    const value = price * p.quantity;
    const basis = p.cost_basis * p.quantity;
    mv += value;
    cost += basis;
    const gl = value - basis;
    return {
      ticker: p.ticker.toUpperCase(),
      quantity: p.quantity,
      cost_basis: p.cost_basis,
      price,
      market_value: Math.round(value * 100) / 100,
      gain_loss: Math.round(gl * 100) / 100,
      "gain_loss_%": basis ? Math.round((gl / basis) * 1000) / 10 : 0,
      scores: rec.subscores,
      overall_score: rec.score,
      recommendation:
        rec.score >= 70 ? "Buy More" : rec.score >= 55 ? "Hold" : rec.score >= 40 ? "Reduce" : "Sell",
      covered_call: rec.covered_call,
      cash_secured_put: rec.cash_secured_put,
    };
  });
  const gl = mv - cost;
  return {
    summary: {
      market_value: Math.round(mv * 100) / 100,
      cost_basis: Math.round(cost * 100) / 100,
      gain_loss: Math.round(gl * 100) / 100,
      "gain_loss_%": cost ? Math.round((gl / cost) * 1000) / 10 : 0,
      positions: rows.filter((r) => !("error" in r)).length,
    },
    positions: rows,
  };
}

// Ask the Vercel serverless function to trigger the GitHub Actions scan.
// Returns {triggered:true} on success, or {configured:false, actionsUrl} when
// the deploy has no GITHUB_DISPATCH_TOKEN set (so the UI can link out instead).
export async function runScan(): Promise<{
  triggered?: boolean;
  configured?: boolean;
  actionsUrl?: string;
  error?: string;
}> {
  try {
    const res = await fetch("/api/run-scan", { method: "POST" });
    return await res.json();
  } catch (e) {
    return {
      configured: false,
      actionsUrl:
        "https://github.com/Amit33-design/Amit33-network-design/actions/workflows/alphahunter-scan.yml",
      error: String(e),
    };
  }
}

export const api = {
  marketTop: (limit = 50) => scanWithFallback(`/market/top?limit=${limit}`),
  oversold: (limit = 50) =>
    scanWithFallback(`/market/oversold?limit=${limit}`,
      (r) => (r.metrics?.rsi ?? 100) < 35 || (r.metrics?.["month_%"] ?? 0) <= -30),
  breakouts: (limit = 50) =>
    scanWithFallback(`/market/breakouts?limit=${limit}`, (r) => r.metrics?.above_ema200 === true),
  coveredCalls: (limit = 25) =>
    scanWithFallback(`/options/coveredcalls?limit=${limit}`, (r) => !!r.covered_call),
  csp: (limit = 25) =>
    scanWithFallback(`/options/csp?limit=${limit}`, (r) => !!r.cash_secured_put),
  morning: () => get<any>(`/report/morning`),
  backtest: (ticker: string, hold = 10) =>
    get<any>(`/backtest/${encodeURIComponent(ticker)}?hold_days=${hold}`),
  importPortfolio: async (
    positions: { ticker: string; quantity: number; cost_basis: number }[]
  ): Promise<PortfolioResponse> => {
    try {
      const live = await post<PortfolioResponse>(`/portfolio/import`, { positions });
      snapshotMode = false;
      return live;
    } catch {
      return portfolioFromSnapshot(positions);
    }
  },
  ask: (query: string) => post<any>(`/ai/ask`, { query }),
};
