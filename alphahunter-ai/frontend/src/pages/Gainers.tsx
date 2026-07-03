import { useEffect, useMemo, useState } from "react";
import { api, isSnapshot } from "../lib/api";
import type { Recommendation } from "../lib/types";
import { ErrorBox, Loading } from "../components/Loading";
import SnapshotBanner from "../components/SnapshotBanner";

// Top Gainers — the "where's the most realistic upside" leaderboard. Ranks the
// latest scan by expected_gain_% (analyst upside tempered by confidence and
// quality), NOT raw target upside, so junk with fantasy targets doesn't lead.
export default function Gainers() {
  const [rows, setRows] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [qualityOnly, setQualityOnly] = useState(false);
  const [snap, setSnap] = useState(false);

  useEffect(() => {
    api
      .marketTop(200)
      .then((r) => {
        setRows(r.results);
        setSnap(isSnapshot());
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const ranked = useMemo(() => {
    let list = rows.filter((r) => r["expected_gain_%"] != null);
    if (qualityOnly) list = list.filter((r) => ["A", "B"].includes(r.quality_grade ?? ""));
    return [...list].sort((a, b) => (b["expected_gain_%"] ?? 0) - (a["expected_gain_%"] ?? 0));
  }, [rows, qualityOnly]);

  if (loading) return <Loading label="Ranking by expected gain…" />;
  if (error) return <ErrorBox error={error} />;

  const podium = ranked.slice(0, 3);
  const rest = ranked.slice(3);

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-ink">Top Gainers — ranked by expected gain</h1>
        <label className="flex items-center gap-2 text-sm bg-white rounded-lg px-3 py-1.5 shadow-sm cursor-pointer">
          <input type="checkbox" checked={qualityOnly} onChange={(e) => setQualityOnly(e.target.checked)} />
          Quality A/B only
        </label>
      </div>
      {snap && <SnapshotBanner />}

      <div className="text-xs text-slate-400 mb-4">
        Expected gain = analyst upside tempered by confidence and quality — a realistic estimate, not the raw target.
      </div>

      {/* Podium */}
      {podium.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          {podium.map((r, i) => (
            <div key={r.ticker}
                 className={`rounded-xl shadow-sm p-4 border-t-4 bg-white ${
                   i === 0 ? "border-amber-400" : i === 1 ? "border-slate-300" : "border-orange-300"}`}>
              <div className="flex items-center justify-between">
                <span className="text-2xl">{i === 0 ? "🥇" : i === 1 ? "🥈" : "🥉"}</span>
                <span className="text-2xl font-bold text-alpha">+{r["expected_gain_%"]}%</span>
              </div>
              <div className="mt-1 font-bold text-ink text-lg">{r.ticker}</div>
              <div className="text-xs text-slate-500 truncate">{r.company}</div>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span>Quality <b>{r.quality_grade}</b> · {r.confidence}</span>
                <span className="text-slate-500">score {r.score}</span>
              </div>
              {r.hist_trades ? (
                <div className="mt-1 text-xs text-slate-400">
                  bounced {(Number(r.hist_win_rate) * 100).toFixed(0)}% of {r.hist_trades} past setups
                </div>
              ) : null}
              {r.csp_signal?.active && (
                <div className="mt-1 text-xs font-semibold text-emerald-700">💰 CSP {r.csp_signal.strength}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Rest of leaderboard */}
      <div className="bg-white rounded-xl shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-slate-400 text-left bg-slate-50">
            <tr>
              {["#", "Ticker", "Exp. Gain", "Analyst Upside", "Quality", "Score", "Conf.", "Hist Win%", "Flags"].map((h) => (
                <th key={h} className="px-3 py-2 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rest.map((r, i) => (
              <tr key={r.ticker} className="border-t">
                <td className="px-3 py-2 text-slate-400">{i + 4}</td>
                <td className="px-3 py-2">
                  <span className="font-semibold text-alpha">{r.ticker}</span>
                  <span className="ml-2 text-xs text-slate-400 hidden md:inline">{r.company}</span>
                </td>
                <td className="px-3 py-2 font-bold text-alpha">+{r["expected_gain_%"]}%</td>
                <td className="px-3 py-2">{r["analyst_upside_%"] != null ? `+${r["analyst_upside_%"]}%` : "—"}</td>
                <td className="px-3 py-2 font-semibold"
                    style={{ color: ["A", "B"].includes(r.quality_grade ?? "") ? "#1b7f4b" : "#64748b" }}>
                  {r.quality_grade}
                </td>
                <td className="px-3 py-2">{r.score}</td>
                <td className="px-3 py-2">{r.confidence}</td>
                <td className="px-3 py-2">
                  {r.hist_trades ? `${(Number(r.hist_win_rate) * 100).toFixed(0)}%` : "—"}
                </td>
                <td className="px-3 py-2 text-xs">
                  {(r.risk_flags || []).some((f) => f.level === "warn")
                    ? <span className="text-red-600">⚠ {(r.risk_flags || []).filter((f) => f.level === "warn").length}</span>
                    : <span className="text-slate-300">—</span>}
                  {r.csp_signal?.active && <span className="ml-1 text-emerald-700">💰</span>}
                </td>
              </tr>
            ))}
            {ranked.length === 0 && (
              <tr><td colSpan={9} className="px-3 py-6 text-center text-slate-400">
                No names with an expected-gain estimate{qualityOnly ? " at quality A/B" : ""} in the latest scan.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
