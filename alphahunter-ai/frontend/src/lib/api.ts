// Thin fetch wrapper. All calls go through /api, which Vite proxies to the
// FastAPI backend (see vite.config.ts).
import type { PortfolioResponse, ScanResponse } from "./types";

const BASE = "/api";

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

export const api = {
  marketTop: (limit = 50) => get<ScanResponse>(`/market/top?limit=${limit}`),
  oversold: (limit = 50) => get<ScanResponse>(`/market/oversold?limit=${limit}`),
  breakouts: (limit = 50) => get<ScanResponse>(`/market/breakouts?limit=${limit}`),
  coveredCalls: (limit = 25) => get<ScanResponse>(`/options/coveredcalls?limit=${limit}`),
  csp: (limit = 25) => get<ScanResponse>(`/options/csp?limit=${limit}`),
  morning: () => get<any>(`/report/morning`),
  backtest: (ticker: string, hold = 10) =>
    get<any>(`/backtest/${encodeURIComponent(ticker)}?hold_days=${hold}`),
  importPortfolio: (positions: { ticker: string; quantity: number; cost_basis: number }[]) =>
    post<PortfolioResponse>(`/portfolio/import`, { positions }),
  ask: (query: string) => post<any>(`/ai/ask`, { query }),
};
