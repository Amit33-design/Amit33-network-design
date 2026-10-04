import { describe, expect, it } from "vitest";
import { earningsRisk, sessionsUntil } from "./earnings";

const fri = new Date("2026-10-02T12:00:00");      // a Friday

describe("earnings risk", () => {
  it("counts weekday sessions, skipping the weekend", () => {
    expect(sessionsUntil("2026-10-05", fri)).toBe(1);   // Monday
    expect(sessionsUntil("2026-10-09", fri)).toBe(5);
    expect(sessionsUntil("2026-10-02", fri)).toBe(0);   // today
  });
  it("flags a report inside the holding window, not one after it", () => {
    expect(earningsRisk({ next: "2026-10-09", last: null }, 10, fri)!.insideWindow).toBe(true);
    expect(earningsRisk({ next: "2026-10-30", last: null }, 10, fri)!.insideWindow).toBe(false);
  });
  it("ignores missing and already-passed dates", () => {
    expect(earningsRisk({ next: null, last: null }, 10, fri)).toBeNull();
    expect(earningsRisk({ next: "2026-09-20", last: null }, 10, fri)).toBeNull();
    expect(earningsRisk(undefined, 10, fri)).toBeNull();
  });
});
