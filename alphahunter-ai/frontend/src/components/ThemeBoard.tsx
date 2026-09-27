// Where money is flowing: each investment theme measured on its own stocks
// (backend/theme_pulse.py → themes.json). Equal-weight baskets, so a theme is
// judged on its members rather than on the one mega-cap that dominates its ETF,
// and breadth says whether a move is broad or carried by a couple of names.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "./ui";

export type ThemeRow = {
  key: string; name: string; etf: string; growth: string; members: string[];
  basket: null | {
    n: number; ret_1m: number; ret_3m: number; vs_spy_3m: number | null;
    breadth_50d: number; tone: number;
    leaders: { ticker: string; ret_1m: number }[];
    laggards: { ticker: string; ret_1m: number }[];
  };
};
export type ThemesFile = { generated: string | null; spy_3m: number | null; themes: ThemeRow[] };

let cache: Promise<ThemesFile | null> | null = null;
export function useThemes(): ThemesFile | null {
  const [d, setD] = useState<ThemesFile | null>(null);
  useEffect(() => {
    cache ??= fetch("/themes.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    cache.then(setD);
  }, []);
  return d;
}

/** Themes with a basket, strongest vs the S&P first. Pure. */
export function rankThemes(f: ThemesFile | null): ThemeRow[] {
  return (f?.themes ?? [])
    .filter((t) => t.basket && t.basket.vs_spy_3m != null)
    .sort((a, b) => (b.basket!.vs_spy_3m ?? 0) - (a.basket!.vs_spy_3m ?? 0));
}

const pct = (x: number) => `${x >= 0 ? "+" : ""}${x.toFixed(1)}%`;

export default function ThemeBoard({ data }: { data: ThemesFile | null }) {
  const [open, setOpen] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const ranked = rankThemes(data);
  // The ends are the information: where money is going and where it is
  // leaving. The middle is "roughly in line" and stays one click away.
  const EDGE = 6;
  const rows = showAll || ranked.length <= EDGE * 2 + 2
    ? ranked : [...ranked.slice(0, EDGE), ...ranked.slice(-EDGE)];
  if (!data) return <div className="text-xs text-ink-muted">Loading themes…</div>;
  if (!ranked.length) {
    return <div className="text-xs text-ink-muted">
      Theme baskets are built by the morning dashboard job; none have been measured yet.
    </div>;
  }
  const max = Math.max(...ranked.map((r) => Math.abs(r.basket!.vs_spy_3m ?? 0)), 5);

  return (
    <div>
      <div className="text-xs text-ink-muted mb-2">
        Each theme as an equal-weight basket of its own stocks, 3-month return vs the S&P 500
        {data.spy_3m != null ? ` (${pct(data.spy_3m)})` : ""}. Breadth = share of members above
        their 50-day. Tap a theme for its leaders and laggards.
      </div>
      <div className="divide-y divide-line">
        {rows.map((t) => {
          const b = t.basket!;
          const vs = b.vs_spy_3m ?? 0;
          const w = `${Math.min(100, (Math.abs(vs) / max) * 100) / 2}%`;
          const gap = !showAll && rows.length < ranked.length && t === rows[EDGE];
          return (
            <div key={t.key} className={`py-1.5 ${gap ? "border-t-2 border-dashed" : ""}`}>
              <button className="w-full text-left" onClick={() => setOpen(open === t.key ? null : t.key)}>
                <div className="flex items-center gap-2 text-xs">
                  <span className="w-44 sm:w-60 truncate text-ink font-medium" title={t.name}>{t.name}</span>
                  {/* Diverging bar around a centre line: right = beating the S&P. */}
                  <div className="relative flex-1 h-3 rounded bg-surface-sunken min-w-[60px]">
                    <div className="absolute top-0 bottom-0 left-1/2 w-px bg-line" />
                    <div className={`absolute top-0.5 bottom-0.5 rounded-sm ${vs >= 0 ? "bg-gain" : "bg-loss"}`}
                         style={vs >= 0 ? { left: "50%", width: w } : { right: "50%", width: w }} />
                  </div>
                  <span className={`w-14 text-right num ${vs >= 0 ? "text-gain" : "text-loss"}`}
                        title="3-month return vs the S&P 500, percentage points">
                    {vs >= 0 ? "+" : ""}{vs.toFixed(1)}pp
                  </span>
                  <span className="w-12 text-right num text-ink-muted hidden sm:inline"
                        title="Share of members above their 50-day average">
                    {Math.round(b.breadth_50d * 100)}%
                  </span>
                </div>
              </button>
              {open === t.key && (
                <div className="mt-1.5 pl-1 text-2xs text-ink-secondary space-y-1">
                  <div className="flex flex-wrap gap-1 items-center">
                    <Badge>{t.growth}</Badge>
                    <span>{b.n} stocks · 1m {pct(b.ret_1m)} · 3m {pct(b.ret_3m)} · {Math.round(b.breadth_50d * 100)}% above 50-day · ETF {t.etf}</span>
                  </div>
                  <div>
                    <span className="text-gain font-semibold">Leading this month: </span>
                    {b.leaders.map((l, i) => (
                      <span key={l.ticker}>{i > 0 && ", "}
                        <Link to={`/analysis?ticker=${l.ticker}`} className="text-brand hover:underline">{l.ticker}</Link> {pct(l.ret_1m)}
                      </span>
                    ))}
                  </div>
                  <div>
                    <span className="text-loss font-semibold">Lagging: </span>
                    {b.laggards.map((l, i) => (
                      <span key={l.ticker}>{i > 0 && ", "}
                        <Link to={`/analysis?ticker=${l.ticker}`} className="text-brand hover:underline">{l.ticker}</Link> {pct(l.ret_1m)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {ranked.length > rows.length || showAll ? (
        <button onClick={() => setShowAll(!showAll)} className="mt-2 text-xs text-brand hover:underline">
          {showAll ? "Show strongest and weakest only" : `Show all ${ranked.length} themes`}
        </button>
      ) : null}
      {data.generated && (
        <div className="mt-2 text-2xs text-ink-muted">
          Measured {data.generated.slice(0, 10)}. Past relative strength, not a forecast — themes
          rotate, and a leading group can reverse quickly.
        </div>
      )}
    </div>
  );
}
