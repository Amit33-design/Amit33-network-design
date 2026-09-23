// The frontend's own pure logic — previously checked only by hand.
import { describe, expect, it } from "vitest";
import { tradingDaysSince } from "../components/FreshnessBanner";
import { MIN_DATES, MIN_TRADES, statusFor } from "./evidence";

describe("tradingDaysSince", () => {
  // An earlier version subtracted one "so today counts as zero" — it already
  // did — which made yesterday's scan read as today's.
  const now = new Date("2026-09-23T14:00:00");
  it.each([
    ["2026-09-23", 0], ["2026-09-22", 1], ["2026-09-18", 3], ["2026-09-14", 7],
  ])("%s is %i trading days before 23 Sep", (d, want) => {
    expect(tradingDaysSince(d as string, now)).toBe(want);
  });
  it("skips the weekend", () => {
    // Fri -> Mon is one trading day, not three.
    expect(tradingDaysSince("2026-09-18", new Date("2026-09-21T14:00:00"))).toBe(1);
  });
  it("treats a malformed date as current rather than crashing", () => {
    expect(tradingDaysSince("not-a-date", now)).toBe(0);
  });
});

describe("statusFor — evidence per screen", () => {
  it("calls anything under the minimum sample unproven, whatever it returned", () => {
    const s = statusFor({ trades: MIN_TRADES - 1, win_rate: 1, "avg_return_%": 40,
                          "avg_alpha_%": 38, beat_spy_rate: 1 });
    expect(s.label).toBe("Unproven");
    expect(s.detail).toMatch(/noise/);
  });
  it("needs positive alpha AND a majority beating SPY to say 'Beating SPY'", () => {
    expect(statusFor({ trades: 40, win_rate: 0.6, "avg_return_%": 3,
                       "avg_alpha_%": 1.2, beat_spy_rate: 0.6 }).label).toBe("Beating SPY");
    // Positive average carried by a few big winners, most trades behind SPY.
    expect(statusFor({ trades: 40, win_rate: 0.45, "avg_return_%": 2,
                       "avg_alpha_%": 0.8, beat_spy_rate: 0.4 }).label).toBe("Mixed");
  });
  it("says trailing when alpha is not positive", () => {
    expect(statusFor({ trades: 40, win_rate: 0.5, "avg_return_%": 1,
                       "avg_alpha_%": -0.5, beat_spy_rate: 0.45 }).label).toBe("Trailing SPY");
  });
  it("many trades from a few dates are one market window, not proof", () => {
    const s = statusFor({ trades: 36, dates: 3, win_rate: 0.14, "avg_return_%": -4.7,
                          "avg_alpha_%": -6.3, beat_spy_rate: 0.11 });
    expect(s.label).toBe("Unproven");
    expect(s.detail).toContain("3 scan dates");
    expect(statusFor({ trades: 36, dates: MIN_DATES, win_rate: 0.14, "avg_return_%": -4.7,
                       "avg_alpha_%": -6.3, beat_spy_rate: 0.11 }).label).toBe("Trailing SPY");
  });
  it("a positive average is Mixed until it holds across dates", () => {
    const rec = { trades: 2183, dates: 58, win_rate: 0.45, "avg_return_%": 1.45,
                  "avg_alpha_%": 1.18, beat_spy_rate: 0.44 };
    expect(statusFor({ ...rec, alpha_t_by_date: 1.1 }).label).toBe("Mixed");
    expect(statusFor({ ...rec, alpha_t_by_date: 1.1 }).detail).toContain("luck");
    expect(statusFor({ ...rec, alpha_t_by_date: 2.4 }).label).toBe("Beating SPY");
  });
  it("handles no record at all", () => {
    expect(statusFor(null).label).toBe("Unproven");
    expect(statusFor({ trades: 0, win_rate: 0, "avg_return_%": 0 }).label).toBe("Unproven");
  });
});
