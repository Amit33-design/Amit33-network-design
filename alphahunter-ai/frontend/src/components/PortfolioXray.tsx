// What the holdings add up to: money by theme, how concentrated it really
// is, and which positions sit in a group the market is leaving.
import { Link } from "react-router-dom";
import { useThemes } from "./ThemeBoard";
import { CONCENTRATED_SHARE, xray, type Holding } from "../lib/xray";

const pc = (x: number) => `${Math.round(x * 100)}%`;
const pp = (x: number | null) => (x == null ? "" : `${x >= 0 ? "+" : ""}${x.toFixed(0)}pp`);

export default function PortfolioXray({ holdings, byCost = false }: { holdings: Holding[]; byCost?: boolean }) {
  const themes = useThemes();
  const x = xray(holdings, themes);
  if (!x || !themes) return null;
  return (
    <div className="panel p-4 mt-4 space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="font-semibold text-ink">🔬 Portfolio X-ray</span>
        <span className="text-xs text-ink-secondary">
          {holdings.length} positions ≈ <b className="text-ink">{x.effective_positions}</b> equal-sized bets ·
          spread over ≈ <b className="text-ink">{x.effective_themes}</b> independent themes
        </span>
      </div>

      {x.concentrated && (
        <div className="text-xs rounded-panel border border-warn/30 bg-warn-soft text-warn px-3 py-2">
          <b>{pc(x.top_theme_share)} of the money is in {x.exposures[0].name}.</b> Above {pc(CONCENTRATED_SHARE)},
          one theme's bad month is the portfolio's bad month — these positions tend to move together.
        </div>
      )}

      <div className="space-y-1.5">
        {x.exposures.map((e) => (
          <div key={e.key} className="flex items-center gap-2 text-xs">
            <span className="w-40 sm:w-56 truncate text-ink" title={e.tickers.join(", ")}>{e.name}</span>
            <div className="flex-1 h-2.5 rounded bg-surface-sunken min-w-[60px]">
              <div className={`h-full rounded ${e.key === "unclassified" ? "bg-line-strong" : "bg-brand"}`}
                   style={{ width: pc(e.share) }} />
            </div>
            <span className="w-10 text-right num text-ink">{pc(e.share)}</span>
            <span className={`w-14 text-right num ${e.vs_spy_3m == null ? "text-ink-muted"
              : e.vs_spy_3m >= 5 ? "text-gain" : e.vs_spy_3m <= -5 ? "text-loss" : "text-ink-secondary"}`}
                  title="Theme basket's 3-month return vs the S&P 500">
              {e.vs_spy_3m == null ? "—" : pp(e.vs_spy_3m)}
            </span>
          </div>
        ))}
      </div>

      {x.headwinds.length > 0 && (
        <div className="text-xs text-ink-secondary">
          <span className="text-loss font-semibold">Group headwind: </span>
          {x.headwinds.map((h, i) => (
            <span key={h.ticker}>{i > 0 && ", "}
              <Link to={`/analysis?ticker=${h.ticker}`} className="text-brand hover:underline">{h.ticker}</Link>
              {" "}({h.theme} {pp(h.vs_spy_3m)}, {pc(h.share)} of the money)
            </span>
          ))}
          {" "}— its group is trailing the S&P by 10+ points over 3 months. Not a sell signal by itself;
          a reason to check the thesis is still yours, not the market's.
        </div>
      )}

      <div className="text-2xs text-ink-muted">
        {byCost && "Weighted by cost basis where no live price was available. "}
        Themes and their 3-month spread vs the S&P come from the daily theme baskets
        {themes.generated ? ` (${themes.generated.slice(0, 10)})` : ""}. Unclassified = not in any basket yet.
      </div>
    </div>
  );
}
