// Regression tests for the 2026-09-29 QA brief against api/ta.js.
import { describe, expect, it } from "vitest";
// @ts-expect-error — plain ESM JS outside the frontend project, no types.
import { analyze, crossText, trimChart, volumeTrend } from "../../../../api/ta.js";

function bars(n: number, f: (i: number) => number, start = "2024-01-01") {
  const dates: string[] = [], c: number[] = [];
  const d = new Date(start + "T00:00:00Z");
  while (dates.length < n) {
    if (d.getUTCDay() % 6 !== 0) { c.push(f(dates.length)); dates.push(d.toISOString().slice(0, 10)); }
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return { dates, o: c, h: c.map((x) => x * 1.01), l: c.map((x) => x * 0.99), c, v: c.map((_, i) => 1e6 + (i % 7) * 1e5) };
}
const run = (b: ReturnType<typeof bars>) => analyze(b.dates, b.o, b.h, b.l, b.c, b.v, 25000, 1);
const allText = (out: any) => JSON.stringify([out.verdict_reason, out.trend, out.timing, out.signals, out.cycle]);

describe("P0-2 — one moving-average convention, crosses that match the numbers", () => {
  it("QA case: EMA50 43.27 above EMA200 43.23 never reads as a death cross", () => {
    const t = crossText(43.27, 43.23, { type: "death", date: "2026-05-01", ago: 40 });
    expect(t).not.toMatch(/death/i);
    expect(t).toBe("EMA50 above EMA200 (no recent cross)");
    expect(crossText(43.27, 43.23, { type: "golden", date: "2026-09-01", ago: 20 }))
      .toBe("EMA50 above EMA200 (golden cross on 2026-09-01)");
    expect(crossText(40, 43, null)).toBe("EMA50 below EMA200 (no recent cross)");
  });
  it("no copy on the page names an SMA", () => {
    const out = run(bars(520, (i) => 50 + 10 * Math.sin(i / 40) + i * 0.02));
    expect(allText(out)).not.toMatch(/SMA|200-day SMA/);
  });
  it("every cross label agrees with the sign of EMA50 − EMA200 today", () => {
    const out = run(bars(520, (i) => 60 - i * 0.05 + 6 * Math.sin(i / 25)));
    const above = out.indicators.ema50 > out.indicators.ema200;
    const txt = out.trend.factors.map((f: any) => f.s).join(" | ");
    if (above) expect(txt).not.toMatch(/death cross/i);
    else expect(txt).not.toMatch(/golden cross/i);
  });
});

describe("P1-3 — the cycle's current state never contradicts price vs EMA200", () => {
  it("a long rally that rolls over below EMA200 is a transition, not a bullish cycle", () => {
    // Up for ~400 bars (EMA50 well above EMA200), then a sharp drop under EMA200.
    const b = bars(520, (i) => (i < 440 ? 40 + i * 0.1 : 84 - (i - 440) * 0.45));
    const out = run(b);
    expect(out.price).toBeLessThan(out.indicators.ema200);
    expect(out.cycle.state).not.toBe("bull");
    expect(JSON.stringify(out.trend.factors)).not.toMatch(/Bullish cycle/);
  });
});

describe("P1-6 — each return uses its own lookback", () => {
  it("6M and 1Y differ on a series with 2 years of history, and trimming the chart changes nothing", () => {
    const b = bars(520, (i) => 100 * Math.exp(0.0008 * i) * (1 + 0.05 * Math.sin(i / 30)));
    const out = run(b);
    expect(out.indicators.ret_6m).not.toBeCloseTo(out.indicators.ret_1y, 3);
    const before = JSON.stringify(out.indicators);
    const chart = trimChart(out.chart, "6mo", new Date(b.dates[b.dates.length - 1] + "T12:00:00Z"));
    expect(chart.dates.length).toBeLessThan(out.chart.dates.length);
    expect(chart.close.length).toBe(chart.dates.length);
    expect(JSON.stringify(out.indicators)).toBe(before);
  });
});

describe("P1-5 — volume trend", () => {
  it("reads expanding and fading interest, without NaN on thin names", () => {
    const c = Array.from({ length: 60 }, (_, i) => 10 + (i % 2 ? 0.1 : -0.1));
    const quiet = Array.from({ length: 60 }, (_, i) => (i >= 55 ? 3e5 : 1e6));
    const busy = Array.from({ length: 60 }, (_, i) => (i >= 55 ? 2e6 : 1e6));
    expect(volumeTrend(c, quiet).read).toMatch(/fading/);
    expect(volumeTrend(c, busy).read).toMatch(/picking up/);
    const thin = volumeTrend(c.slice(0, 10), quiet.slice(0, 10));
    expect(thin.avg_50d).toBeNull();
    expect(thin.ratio_5_50).toBeNull();
    expect(Object.values(thin).some((x) => typeof x === "number" && Number.isNaN(x))).toBe(false);
  });
});
