import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface PeerRow {
  ticker: string; name?: string; price?: number; day_change_pct?: number | null;
  ret_1m?: number | null; ret_6m?: number | null; rsi?: number | null;
  from_52w_high?: number | null; trend?: string;
}
interface PeersResp {
  ticker: string;
  subject: PeerRow | null;
  peers: PeerRow[];
  standing?: { rank: number; of: number; vs_peer_median_pp: number; verdict: string } | null;
  note?: string;
}

const pct = (x?: number | null) =>
  x == null ? "—" : `${x >= 0 ? "+" : ""}${x}%`;
const tone = (x?: number | null) =>
  x == null ? "text-ink-muted" : x >= 0 ? "text-brand" : "text-loss";

// Sector peers — a name down 20% means something very different when its whole
// group is down 20% than when the group is flat.
export default function PeerComparison({ ticker }: { ticker: string }) {
  const [data, setData] = useState<PeersResp | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;
    setLoading(true);
    setData(null);
    fetch(`/api/peers?ticker=${encodeURIComponent(ticker)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (!cancelled) setData(j); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ticker]);

  if (loading) {
    return (
      <div className="panel p-4 text-sm text-ink-muted">
        Loading sector peers…
      </div>
    );
  }
  if (!data || (!data.peers?.length && !data.note)) return null;

  const rows = [data.subject, ...(data.peers || [])].filter(Boolean) as PeerRow[];

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-3 flex-wrap mb-2">
        <div className="font-semibold text-ink">🏳️ Sector peers</div>
        {data.standing && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
            data.standing.verdict === "lagging its peers"
              ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
            #{data.standing.rank} of {data.standing.of} on 6-month return ·{" "}
            {data.standing.verdict}
          </span>
        )}
      </div>

      {data.note ? (
        <div className="text-sm text-ink-secondary">{data.note}</div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-ink-muted text-left">
                <tr>{["", "Price", "Today", "1M", "6M", "RSI", "From 52w high", "Trend"].map((h) => (
                  <th key={h} className="px-2 py-1 font-normal whitespace-nowrap">{h}</th>))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const isSubject = r.ticker === data.ticker;
                  return (
                    <tr key={r.ticker} className={`border-t ${isSubject ? "bg-amber-50/60" : ""}`}>
                      <td className="px-2 py-1.5 whitespace-nowrap">
                        <Link to={`/analysis?ticker=${r.ticker}`}
                              className={`font-bold hover:underline ${isSubject ? "text-ink" : "text-brand"}`}>
                          {r.ticker}
                        </Link>
                        {isSubject && <span className="ml-1 text-[10px] text-ink-muted">(this stock)</span>}
                      </td>
                      <td className="px-2 py-1.5">{r.price != null ? `$${r.price}` : "—"}</td>
                      <td className={`px-2 py-1.5 ${tone(r.day_change_pct)}`}>{pct(r.day_change_pct)}</td>
                      <td className={`px-2 py-1.5 ${tone(r.ret_1m)}`}>{pct(r.ret_1m)}</td>
                      <td className={`px-2 py-1.5 font-semibold ${tone(r.ret_6m)}`}>{pct(r.ret_6m)}</td>
                      <td className="px-2 py-1.5">{r.rsi ?? "—"}</td>
                      <td className="px-2 py-1.5 text-ink-secondary">{pct(r.from_52w_high)}</td>
                      <td className={`px-2 py-1.5 ${r.trend === "up" ? "text-brand" : "text-loss"}`}>
                        {r.trend === "up" ? "▲ up" : r.trend === "down" ? "▼ down" : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {data.standing && (
            <div className="mt-2 text-xs text-ink-secondary">
              6-month return is{" "}
              <b className={tone(data.standing.vs_peer_median_pp)}>
                {pct(data.standing.vs_peer_median_pp)}
              </b>{" "}
              vs the peer median — a name falling with its whole group is a sector story;
              one falling alone is a company story.
            </div>
          )}
        </>
      )}
    </div>
  );
}
