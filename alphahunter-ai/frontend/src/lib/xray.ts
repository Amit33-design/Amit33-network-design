// Portfolio X-ray: what a list of holdings adds up to. Each position was
// judged on its own; nothing said "62% of this money is one theme, and that
// theme is lagging the market". Themes come from themes.json (the same
// equal-weight baskets the Dashboard and the thesis use). Pure; tested.
import type { ThemeRow, ThemesFile } from "../components/ThemeBoard";

export type Holding = { ticker: string; value: number };
export type Exposure = {
  key: string; name: string; value: number; share: number; tickers: string[];
  vs_spy_3m: number | null; breadth_50d: number | null; tone: number | null;
};
export type Xray = {
  total: number;
  exposures: Exposure[];          // largest first; "unclassified" last
  effective_positions: number;    // 1 / Σw² over holdings
  effective_themes: number;       // 1 / Σw² over themes (unclassified counted as one)
  top_theme_share: number;
  concentrated: boolean;
  headwinds: { ticker: string; theme: string; vs_spy_3m: number; share: number }[];
};

export const CONCENTRATED_SHARE = 0.4;   // one theme above 40% of the money
export const HEADWIND_PP = -10;          // theme trailing SPY by 10pp+ over 3 months

/** ticker -> theme row, from the basket member lists. */
export function themeIndex(f: ThemesFile | null): Map<string, ThemeRow> {
  const idx = new Map<string, ThemeRow>();
  for (const t of f?.themes ?? []) for (const m of t.members) if (!idx.has(m)) idx.set(m, t);
  return idx;
}

const herfindahl = (ws: number[]) => {
  const s = ws.reduce((a, w) => a + w * w, 0);
  return s > 0 ? Math.round((1 / s) * 10) / 10 : 0;
};

export function xray(holdings: Holding[], themes: ThemesFile | null): Xray | null {
  const hs = holdings.filter((h) => h.value > 0);
  const total = hs.reduce((a, h) => a + h.value, 0);
  if (!total) return null;
  const idx = themeIndex(themes);
  const groups = new Map<string, Exposure>();
  for (const h of hs) {
    const t = idx.get(h.ticker.toUpperCase());
    const key = t?.key ?? "unclassified";
    const g = groups.get(key) ?? {
      key, name: t?.name ?? "Unclassified", value: 0, share: 0, tickers: [],
      vs_spy_3m: t?.basket?.vs_spy_3m ?? null, breadth_50d: t?.basket?.breadth_50d ?? null,
      tone: t?.basket?.tone ?? null,
    };
    g.value += h.value;
    g.tickers.push(h.ticker.toUpperCase());
    groups.set(key, g);
  }
  const exposures = [...groups.values()]
    .map((g) => ({ ...g, share: g.value / total }))
    .sort((a, b) => (a.key === "unclassified" ? 1 : b.key === "unclassified" ? -1 : b.value - a.value));
  const classified = exposures.filter((e) => e.key !== "unclassified");
  const top = classified[0]?.share ?? 0;
  const headwinds = hs.flatMap((h) => {
    const t = idx.get(h.ticker.toUpperCase());
    const vs = t?.basket?.vs_spy_3m;
    return t && vs != null && vs <= HEADWIND_PP
      ? [{ ticker: h.ticker.toUpperCase(), theme: t.name, vs_spy_3m: vs, share: h.value / total }]
      : [];
  }).sort((a, b) => b.share - a.share);
  return {
    total,
    exposures,
    effective_positions: herfindahl(hs.map((h) => h.value / total)),
    effective_themes: herfindahl(exposures.map((e) => e.share)),
    top_theme_share: top,
    concentrated: top > CONCENTRATED_SHARE,
    headwinds,
  };
}
