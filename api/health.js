// Vercel serverless function: GET /api/health
//
// An uptime check needs something cheap and honest. This reports whether the
// functions are running AND whether the upstream price feed is answering,
// separately — "our code is up but the data provider is down" is a different
// incident from "the site is down", and one status field cannot say both.
const PROBE =
  "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1d&interval=1d";

export default async function handler(_req, res) {
  const started = Date.now();
  let upstream = "unknown";
  try {
    const r = await fetch(PROBE, {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)" },
      signal: AbortSignal.timeout(4000),
    });
    upstream = r.ok ? "ok" : `degraded (${r.status})`;
  } catch {
    upstream = "unreachable";
  }
  res.setHeader("Cache-Control", "no-store");
  return res.status(200).json({
    status: "ok",                       // the functions themselves
    upstream,                           // the price feed behind them
    latency_ms: Date.now() - started,
    time: new Date().toISOString(),
  });
}
