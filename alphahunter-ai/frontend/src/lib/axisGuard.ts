// Axis sanity guard for the Analysis charts (QA 2026-09-29, P0-1).
//
// Wheel-zoom over the price chart trapped page scroll and, after a few
// events, left the axes at dates around the year 2000 and a y-range down to
// -1e18 on a normal stock. Wheel zoom is now off, but drag/zoom and the range
// buttons still emit relayout events, so every proposed range goes through
// here: anything outside what the loaded data can justify is reset.
export type Bounds = { x: [string, string]; price: [number, number]; volume: [number, number] };
export type View = { x: [string, string]; price: [number, number] };

const DAY = 86_400_000;
const ms = (d: string) => new Date(d.length <= 10 ? d + "T00:00:00Z" : d.replace(" ", "T") + (d.includes("Z") ? "" : "Z")).getTime();
const iso = (t: number) => new Date(t).toISOString().slice(0, 10);

/** Pure: sanitize a proposed x/y window against the loaded data. */
export function sanitizeView(proposed: Partial<View>, b: Bounds): View {
  const x0 = ms(b.x[0]), x1 = ms(b.x[1]);
  let x: [string, string] = b.x;
  if (proposed.x) {
    const p0 = ms(String(proposed.x[0])), p1 = ms(String(proposed.x[1]));
    const ok = Number.isFinite(p0) && Number.isFinite(p1) && p1 > p0
      && p0 >= x0 - 5 * DAY && p1 <= x1 + 5 * DAY
      && (p1 - p0) <= 1.5 * Math.max(x1 - x0, DAY);
    if (ok) x = [iso(p0), iso(p1)];
  }
  // The data's own price range (bounds already carry 2% headroom).
  const lo = b.price[0] / 0.98, hi = b.price[1] / 1.02;
  let price: [number, number] = b.price;
  if (proposed.price) {
    const [y0, y1] = proposed.price.map(Number);
    const span = hi - lo || hi * 0.1;
    const ok = Number.isFinite(y0) && Number.isFinite(y1) && y1 > y0 && y0 > 0
      && y0 >= lo - 0.2 * span && y1 <= hi + 0.2 * span;
    if (ok) price = [y0, y1];
  }
  return { x, price };
}

/** Pull the proposed ranges out of a Plotly relayout event. Pure. */
export function rangesFromRelayout(ev: Record<string, any>): Partial<View> & { reset?: boolean } {
  if (!ev) return {};
  if (ev["xaxis.autorange"] || ev["yaxis.autorange"]) return { reset: true };
  const out: Partial<View> = {};
  const xr = ev["xaxis.range"] ?? (ev["xaxis.range[0]"] != null ? [ev["xaxis.range[0]"], ev["xaxis.range[1]"]] : null);
  if (xr) out.x = [String(xr[0]), String(xr[1])];
  const yr = ev["yaxis.range"] ?? (ev["yaxis.range[0]"] != null ? [ev["yaxis.range[0]"], ev["yaxis.range[1]"]] : null);
  if (yr) out.price = [Number(yr[0]), Number(yr[1])];
  return out;
}
