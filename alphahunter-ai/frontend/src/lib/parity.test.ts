// TypeScript must reproduce the fixture Python generates and also asserts.
// Drift on either side fails a suite instead of reaching a user.
import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/parity.json";
import { buildPlan, checkExit } from "./exitRules";
import { dailyOrder } from "./pairTrading";

describe("exit plan parity with backend/exit_rules.py", () => {
  for (const c of fixture.plans) {
    it(`price ${c.price}, atr ${c.atr ?? "none"}`, () => {
      const p = buildPlan(c.price, { atr: c.atr });
      expect(p.target).toBeCloseTo(c.target, 2);
      expect(p.stop).toBeCloseTo(c.stop, 2);
      expect(p.targetPct).toBeCloseTo(c.target_pct, 2);
      expect(p.stopPct).toBeCloseTo(c.stop_pct, 2);
    });
  }
});

describe("exit decision parity", () => {
  for (const c of fixture.exits) {
    it(`entry ${c.entry} -> ${c.price} on day ${c.days_held}`, () => {
      const out = checkExit(buildPlan(c.entry), c.price,
                            { daysHeld: c.days_held, peakPrice: c.peak });
      expect(out.action).toBe(c.action);
    });
  }
});

describe("pair rebalancing order parity with backend/pair_signals.py", () => {
  for (const c of fixture.orders) {
    it(`${c.pa}/${c.pb} holding ${c.sa}/${c.sb} target ${c.target_a}`, () => {
      const o = dailyOrder("A", "B", c.pa, c.pb, c.sa, c.sb, { targetA: c.target_a });
      expect(o.action).toBe(c.action);
      if (c.sell) {
        expect(o.sell?.ticker).toBe(c.sell.ticker);
        expect(o.sell?.shares).toBe(c.sell.shares);
      } else {
        expect(o.sell).toBeUndefined();
      }
      if (c.buy) {
        expect(o.buy?.ticker).toBe(c.buy.ticker);
        expect(o.buy?.shares).toBe(c.buy.shares);
      }
    });
  }
});
