import { describe, expect, it } from "vitest";
import { rangesFromRelayout, sanitizeView, type Bounds } from "./axisGuard";

const b: Bounds = { x: ["2025-10-01", "2026-09-29"], price: [40 * 0.98, 60 * 1.02], volume: [0, 1e7] };

describe("axis sanity guard (QA P0-1)", () => {
  it("rejects the year-2000 / -1e18 corruption QA saw", () => {
    const v = sanitizeView({ x: ["2000-01-01", "2000-03-01"], price: [-1e18, 1e18] }, b);
    expect(v).toEqual({ x: b.x, price: b.price });
  });
  it("keeps a sensible zoom inside the data", () => {
    const v = sanitizeView({ x: ["2026-06-01", "2026-09-29"], price: [42, 58] }, b);
    expect(v.x).toEqual(["2026-06-01", "2026-09-29"]);
    expect(v.price).toEqual([42, 58]);
  });
  it("resets a window far wider than the loaded range, and a y-range at or below zero", () => {
    expect(sanitizeView({ x: ["2018-01-01", "2026-09-29"] }, b).x).toEqual(b.x);
    expect(sanitizeView({ price: [0, 58] }, b).price).toEqual(b.price);
    expect(sanitizeView({ price: [30, 90] }, b).price).toEqual(b.price);    // > 20% beyond the data
  });
  it("reads Plotly relayout shapes, including autorange as a reset", () => {
    expect(rangesFromRelayout({ "xaxis.range[0]": "2026-01-01", "xaxis.range[1]": "2026-03-01" }).x)
      .toEqual(["2026-01-01", "2026-03-01"]);
    expect(rangesFromRelayout({ "yaxis.range": [41, 59] }).price).toEqual([41, 59]);
    expect(rangesFromRelayout({ "xaxis.autorange": true }).reset).toBe(true);
  });
});
