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

let snapshotCache: Recommendation[] | null = null;
async function loadSnapshot(): Promise<Recommendation[]> {
  if (snapshotCache) return snapshotCache;
  const res = await fetch("/snapshot.json");
  if (!res.ok) throw new Error("no snapshot available");
  const data = await res.json();
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
  importPortfolio: (positions: { ticker: string; quantity: number; cost_basis: number }[]) =>
    post<PortfolioResponse>(`/portfolio/import`, { positions }),
  ask: (query: string) => post<any>(`/ai/ask`, { query }),
};
