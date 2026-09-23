// api/ta.js builds the Analysis page's trade plan independently of both the
// scan and the frontend port. It now calls exitLevels(), which is tested here
// against the same fixture Python and exitRules.ts are.
import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/parity.json";
// @ts-expect-error — plain ESM JS outside the frontend project, no types.
import { exitLevels, money } from "../../../../api/_indicators.js";

describe("api/_indicators.exitLevels matches backend build_plan()", () => {
  for (const c of fixture.plans) {
    it(`price ${c.price}, atr ${c.atr ?? "none"}`, () => {
      const lv = exitLevels(c.price, c.atr);
      expect(lv.target).toBe(c.target);
      expect(lv.stop).toBe(c.stop);
      expect(lv.target_pct).toBe(c.target_pct);
      expect(lv.stop_pct).toBe(c.stop_pct);
    });
  }
});

describe("money", () => {
  it("rounds an exact half away from zero, in both directions", () => {
    expect(money(11.625)).toBe(11.63);
    expect(money(-3.695)).toBe(-3.7);
  });
});
