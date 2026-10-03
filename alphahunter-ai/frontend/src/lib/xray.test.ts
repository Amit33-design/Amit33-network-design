import { describe, expect, it } from "vitest";
import { xray, themeIndex } from "./xray";
import type { ThemesFile } from "../components/ThemeBoard";

const basket = (vs: number) => ({ n: 10, ret_1m: 0, ret_3m: vs + 5, vs_spy_3m: vs, breadth_50d: 0.5,
  tone: vs >= 5 ? 1 : vs <= -5 ? -1 : 0, leaders: [], laggards: [] });
const themes: ThemesFile = {
  generated: "2026-10-01", spy_3m: 5,
  themes: [
    { key: "ai_compute", name: "AI compute", etf: "SMH", growth: "secular", members: ["NVDA", "AMD", "AVGO"], basket: basket(8) },
    { key: "ai_power", name: "Power for AI", etf: "XLU", growth: "secular", members: ["VST", "CEG"], basket: basket(-19) },
    { key: "staples", name: "Staples", etf: "XLP", growth: "defensive", members: ["KO"], basket: null },
  ],
};

describe("portfolio xray", () => {
  it("groups money by theme, largest first, unclassified last", () => {
    const x = xray([
      { ticker: "nvda", value: 5000 }, { ticker: "AMD", value: 2000 },
      { ticker: "VST", value: 2000 }, { ticker: "ZZZZ", value: 1000 },
    ], themes)!;
    expect(x.exposures.map((e) => e.key)).toEqual(["ai_compute", "ai_power", "unclassified"]);
    expect(x.exposures[0].share).toBeCloseTo(0.7);
    expect(x.concentrated).toBe(true);
    expect(x.effective_positions).toBeCloseTo(1 / (0.25 + 0.04 + 0.04 + 0.01), 0);
  });
  it("flags holdings whose group trails the market badly", () => {
    const x = xray([{ ticker: "VST", value: 3000 }, { ticker: "NVDA", value: 3000 }, { ticker: "KO", value: 4000 }], themes)!;
    expect(x.headwinds).toEqual([{ ticker: "VST", theme: "Power for AI", vs_spy_3m: -19, share: 0.3 }]);
    expect(x.concentrated).toBe(false);   // 40% exactly is not above the line
  });
  it("needs money to say anything", () => {
    expect(xray([], themes)).toBeNull();
    expect(themeIndex(null).size).toBe(0);
  });
});
