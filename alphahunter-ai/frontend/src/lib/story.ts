// Types + small pure helpers for the investment story returned by
// /api/ta and /api/thesis?story=1 (built in api/_story.js).

export type StoryRead = { tone: number; text: string };
export type Story = {
  business: { name?: string; sector?: string | null; industry?: string | null } | null;
  type: { style: string; growth: string | null; traits: string[] };
  theme: {
    key: string; name: string; etf: string; matched: "ticker" | "industry" | "sector";
    own?: { industry: string | null; sector: string | null } | null;
    scope: string | null; drivers: string[]; risks: string[];
  } | null;
  pulse: {
    stock_1m: number | null; stock_3m: number | null; group_1m: number | null;
    group_3m: number | null; spy_1m: number | null; spy_3m: number | null;
    group_tone: number; stock_tone: number; reads: StoryRead[];
    group_source?: "basket" | "etf" | null;
    basket?: {
      n: number; breadth_50d: number; as_of: string | null;
      leaders: { ticker: string; ret_1m: number }[];
      laggards: { ticker: string; ret_1m: number }[];
    } | null;
  };
  market: { spy_above_200d: boolean; spy_1m: number | null; vix: number | null; text: string } | null;
  bottom_line: string;
};

/** Size class from market cap — the one part of "what kind of stock" the
 *  server cannot know (the cap comes from the profile). */
export function capBucket(cap?: number | null): string | null {
  if (!cap || cap <= 0) return null;
  if (cap >= 200e9) return "Mega-cap";
  if (cap >= 10e9) return "Large-cap";
  if (cap >= 2e9) return "Mid-cap";
  if (cap >= 300e6) return "Small-cap";
  return "Micro-cap";
}

/** "Mega-cap · Secular-growth leader" — cap first when known. */
export function typeLabel(style: string, cap?: number | null): string {
  const b = capBucket(cap);
  return b ? `${b} · ${style}` : style;
}

export const GROWTH_LABEL: Record<string, string> = {
  secular: "Secular growth — demand rides a long-running shift",
  cyclical: "Cyclical — earnings follow the economy or a commodity",
  defensive: "Defensive — steady demand, rate-sensitive",
  speculative: "Speculative — early or binary; outcomes are wide",
};
