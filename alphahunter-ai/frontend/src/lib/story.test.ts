// The investment story (api/_story.js, api/_themes.js) and the Wikipedia
// guard in api/profile.js — pure logic, no network.
import { describe, expect, it } from "vitest";
// @ts-expect-error — plain ESM JS outside the frontend project, no types.
import { resolveTheme, THEMES, themesAsJson } from "../../../../api/_themes.js";
import themesDef from "../../../backend/themes_def.json";
// @ts-expect-error — plain ESM JS outside the frontend project, no types.
import { buildStory } from "../../../../api/_story.js";
// @ts-expect-error — plain ESM JS outside the frontend project, no types.
import { coreName, trimSummary, wikiMatches } from "../../../../api/profile.js";
import { capBucket, typeLabel } from "./story";

// A series that grows by `pct` % in total over `n` bars.
const series = (n: number, pct: number, start = 100) =>
  Array.from({ length: n }, (_, i) => start * (1 + (pct / 100) * (i / (n - 1))));

describe("resolveTheme", () => {
  it("different businesses get different themes", () => {
    expect(resolveTheme("NVDA", "Technology", "Semiconductors").key).toBe("ai_compute");
    expect(resolveTheme("XOM", "Energy", "Oil & Gas Integrated").key).toBe("oil_gas");
    expect(resolveTheme("VST", "Utilities", "Utilities - Independent Power Producers").key).toBe("ai_power");
    expect(resolveTheme("DUK", "Utilities", "Utilities - Regulated Electric").key).toBe("utilities");
    expect(resolveTheme("TXN", "Technology", "Semiconductors").key).toBe("semis");
    expect(resolveTheme("KEY", "Financial Services", "Banks - Regional").key).toBe("banks");
    expect(resolveTheme("MRNA", "Healthcare", "Biotechnology").key).toBe("biotech");
  });
  it("an explicit ticker beats its industry", () => {
    // LLY's industry is drug manufacturing, but the investment case is GLP-1.
    expect(resolveTheme("LLY", "Healthcare", "Drug Manufacturers - General").key).toBe("glp1");
  });
  it("normalises Yahoo's em-dash industry names", () => {
    expect(resolveTheme("ZZZ", "Technology", "Software—Infrastructure").key).toBe("software");
  });
  it("falls back to the sector ETF, then to nothing", () => {
    const t = resolveTheme("ZZZ", "Technology", "Something New");
    expect(t.etf).toBe("XLK");
    expect(t.matched).toBe("sector");
    expect(resolveTheme("ZZZ", null, null)).toBeNull();
  });
  it("every theme has an ETF, a growth type and balanced drivers/risks", () => {
    for (const th of THEMES) {
      expect(th.etf, th.key).toMatch(/^[A-Z]{2,5}$/);
      expect(["secular", "cyclical", "defensive", "speculative"]).toContain(th.growth);
      expect(th.drivers.length, th.key).toBeGreaterThan(0);
      expect(th.risks.length, th.key).toBeGreaterThan(0);
    }
  });
});

describe("theme definitions shared with Python", () => {
  it("backend/themes_def.json matches api/_themes.js (run `npm run themes:export`)", () => {
    expect(themesDef).toEqual(themesAsJson());
  });
});

describe("buildStory", () => {
  const spy = series(260, 10);                 // market +10% over a year
  const base = {
    ticker: "NVDA", price: 100, indicators: { atr: 3, ret_6m: 45, dist_52w_high: -5 },
    classification: { name: "NVIDIA", sector: "Technology", industry: "Semiconductors" },
    theme: resolveTheme("NVDA", "Technology", "Semiconductors"),
    spyCloses: spy, vix: 16,
  };

  it("group leading + stock leading + Buy: story and setup agree", () => {
    const s = buildStory({ ...base, recommendation: "Buy",
      closes: series(130, 120), etfCloses: series(130, 25) });
    expect(s.pulse.group_tone).toBe(1);
    expect(s.pulse.stock_tone).toBe(1);
    expect(s.bottom_line).toMatch(/Story and setup agree/);
    expect(s.type.style).toBe("Secular-growth leader");
  });

  it("strong group but the stock lags it: flagged as company-specific", () => {
    const s = buildStory({ ...base, recommendation: "Hold",
      closes: series(130, -10), etfCloses: series(130, 25) });
    expect(s.pulse.stock_tone).toBe(-1);
    expect(s.pulse.reads.map((r: { text: string }) => r.text).join(" ")).toMatch(/company-specific/);
  });

  it("an out-of-favour group turns a Buy into 'a trade, not a hold'", () => {
    const s = buildStory({ ...base, recommendation: "Buy",
      theme: resolveTheme("XOM", "Energy", "Oil & Gas Integrated"),
      closes: series(130, -12), etfCloses: series(130, -15) });
    expect(s.pulse.group_tone).toBe(-1);
    expect(s.bottom_line).toMatch(/trade, not a long-term hold/);
  });

  it("speculative themes always carry the sizing warning", () => {
    const s = buildStory({ ...base, recommendation: "Buy",
      theme: resolveTheme("IONQ", "Technology", "Computer Hardware"),
      closes: series(130, 40), etfCloses: series(130, 25) });
    expect(s.type.style).toMatch(/Speculative/);
    expect(s.bottom_line).toMatch(/size it small/);
  });

  it("uses the theme's own basket over its ETF when CI has built one", () => {
    // ETF says the group is down; the theme's actual members are up and broad.
    const s = buildStory({ ...base, recommendation: "Hold",
      theme: resolveTheme("VST", "Utilities", "Utilities - Independent Power Producers"),
      closes: series(130, 30), etfCloses: series(130, -15),
      basket: { n: 10, ret_1m: 4, ret_3m: 18, vs_spy_3m: 12, breadth_50d: 0.8,
                leaders: [], laggards: [], as_of: "2026-09-26" } });
    expect(s.pulse.group_source).toBe("basket");
    expect(s.pulse.group_tone).toBe(1);
    expect(s.pulse.reads[0].text).toMatch(/10 stocks, equal-weight/);
    expect(s.pulse.reads[0].text).toMatch(/80% of them are above their 50-day/);
  });

  it("ignores a basket too thin to be a group", () => {
    const s = buildStory({ ...base, recommendation: "Hold", closes: series(130, 5),
      etfCloses: series(130, 25),
      basket: { n: 2, ret_1m: 1, ret_3m: -30, vs_spy_3m: -35, breadth_50d: 0 } });
    expect(s.pulse.group_source).toBe("etf");
  });

  it("reports the market backdrop and degrades without a group ETF", () => {
    const s = buildStory({ ...base, recommendation: "Hold", closes: series(130, 5),
      etfCloses: null, vix: 32 });
    expect(s.market.spy_above_200d).toBe(true);
    expect(s.market.text).toMatch(/panic/);
    expect(s.pulse.reads).toHaveLength(0);
  });
});

describe("Wikipedia summary guard", () => {
  it("strips corporate suffixes", () => {
    expect(coreName("NVIDIA Corporation")).toBe("nvidia");
    expect(coreName("Vistra Corp.")).toBe("vistra");
    expect(coreName("Alphabet Inc.")).toBe("alphabet");
  });
  it("accepts the company page and rejects a same-named non-company page", () => {
    expect(wikiMatches("Vistra Corp.", { title: "Vistra Corp", description: "American energy company",
      extract: "Vistra Corp. is an American energy company based in Irving, Texas." })).toBe(true);
    expect(wikiMatches("Apple Inc.", { title: "Apple", description: "Fruit of the apple tree",
      extract: "An apple is a round, edible fruit produced by an apple tree." })).toBe(false);
    expect(wikiMatches("Oracle Corporation", { title: "Oracle", description: "Person who offers prophecy",
      extract: "An oracle is a person or thing considered to provide insight." })).toBe(false);
  });
  it("trims to whole sentences", () => {
    const t = trimSummary("The company makes widgets for cars. ".repeat(10), 100);
    expect(t).toBe("The company makes widgets for cars. The company makes widgets for cars.");
    expect(trimSummary("Short.")).toBe("Short.");
  });
});

describe("cap bucket", () => {
  it("labels by size and prefixes the style", () => {
    expect(capBucket(5e12)).toBe("Mega-cap");
    expect(capBucket(50e9)).toBe("Large-cap");
    expect(capBucket(3e9)).toBe("Mid-cap");
    expect(capBucket(null)).toBeNull();
    expect(typeLabel("Cyclical", 3e9)).toBe("Mid-cap · Cyclical");
    expect(typeLabel("Cyclical", null)).toBe("Cyclical");
  });
});
