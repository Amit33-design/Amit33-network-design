// The walk-forward test of the Analysis verdict (api/_verdict_eval.js).
import { describe, expect, it } from "vitest";
// @ts-expect-error — plain ESM JS outside the frontend project, no types.
import { walk, summarise } from "../../../../api/_verdict_eval.js";

function series(n: number, drift: number, seed = 1) {
  let x = seed;
  const rnd = () => { x = (x * 16807) % 2147483647; return x / 2147483647 - 0.5; };
  const dates: string[] = [], c: number[] = [];
  let p = 100;
  const d = new Date("2024-01-01T00:00:00Z");
  while (dates.length < n) {
    if (d.getUTCDay() % 6 !== 0) { dates.push(d.toISOString().slice(0, 10)); p *= 1 + drift + rnd() * 0.03; c.push(p); }
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return { dates, o: c, h: c.map((v) => v * 1.01), l: c.map((v) => v * 0.99), c, v: c.map(() => 1e6) };
}

describe("walk-forward verdict evaluation", () => {
  it("never lets a later bar change an earlier verdict (no look-ahead)", () => {
    const s = series(400, 0.001), spy = series(400, 0.0004, 7);
    const a = walk(s, spy);
    const crashed = { ...s, c: s.c.map((v, i) => (i > 330 ? v * 0.3 : v)) };
    const b = walk(crashed, spy);
    const early = (rows: any[]) => rows.filter((r) => r.date < s.dates[300]).map((r) => [r.date, r.verdict, r.score]);
    expect(early(b)).toEqual(early(a));
    expect(a.length).toBeGreaterThan(5);
  });

  it("a steady uptrend reads Buy/Accumulate, a steady downtrend Reduce/Sell", () => {
    const spy = series(400, 0.0003, 7);
    const up = walk(series(400, 0.004, 3), spy).map((r: any) => r.verdict);
    const down = walk(series(400, -0.004, 5), spy).map((r: any) => r.verdict);
    expect(up.filter((v: string) => ["Buy", "Accumulate", "Wait"].includes(v)).length).toBeGreaterThan(up.length / 2);
    expect(down.filter((v: string) => ["Reduce", "Sell"].includes(v)).length).toBeGreaterThan(down.length / 2);
  });

  it("summarises per verdict across dates, with Buy minus Sell", () => {
    const rows = [
      { date: "d1", verdict: "Buy", score: 80, "fwd_%": 5, "spy_%": 1 },
      { date: "d2", verdict: "Buy", score: 75, "fwd_%": 3, "spy_%": 1 },
      { date: "d3", verdict: "Buy", score: 70, "fwd_%": 4, "spy_%": 1 },
      { date: "d1", verdict: "Sell", score: 20, "fwd_%": -2, "spy_%": 1 },
    ];
    const s = summarise(rows);
    expect(s.by_verdict.Buy.cases).toBe(3);
    expect(s.by_verdict.Buy.dates).toBe(3);
    expect(s.by_verdict.Buy["avg_alpha_%"]).toBe(3);
    expect(s.buy_minus_sell_pp).toBe(6);
  });
});

import { readVerdict } from "../components/VerdictEvidence";

describe("readVerdict — saying what a verdict's record means", () => {
  const s = (a: number, t: number | null, n = 500) => ({ cases: n, dates: 40, "avg_alpha_%": a, beat_spy_rate: 0.55, alpha_t_by_date: t });
  it("only claims an edge when it holds across dates", () => {
    expect(readVerdict(s(1.2, 2.4))!.text).toMatch(/^has worked/);
    expect(readVerdict(s(1.2, 1.1))!.text).toMatch(/^has shown no measurable edge/);
    expect(readVerdict(s(-1.5, -2.6))!.text).toMatch(/^has lagged/);
  });
  it("stays silent on a thin sample", () => {
    expect(readVerdict(s(3, 3, 12))).toBeNull();
    expect(readVerdict(undefined)).toBeNull();
  });
});

// @ts-expect-error — plain ESM JS outside the frontend project, no types.
import { overlapFactor } from "../../../../api/_verdict_eval.js";

describe("overlap correction", () => {
  it("deflates t by sqrt(horizon/step) when outcome windows overlap", () => {
    expect(overlapFactor(20, 10)).toBeCloseTo(Math.SQRT2);
    expect(overlapFactor(60, 10)).toBeCloseTo(Math.sqrt(6));
    expect(overlapFactor(5, 10)).toBe(1);
  });
});
