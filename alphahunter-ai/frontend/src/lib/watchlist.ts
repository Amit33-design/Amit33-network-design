// Personal watchlist — device-local (localStorage), no backend required so it
// works on the static deploy. Kept tiny and dependency-free; components
// subscribe via the `watchlist-changed` event so every view stays in sync.
const KEY = "alphahunter.watchlist";
const EVENT = "watchlist-changed";

export function getWatchlist(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter((t) => typeof t === "string") : [];
  } catch {
    return [];
  }
}

function save(list: string[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* private mode / quota — the UI still works for this session */
  }
  window.dispatchEvent(new Event(EVENT));
}

export function isWatched(ticker: string): boolean {
  return getWatchlist().includes(ticker.toUpperCase());
}

export function addToWatchlist(ticker: string) {
  const t = ticker.toUpperCase().trim();
  if (!t) return;
  const list = getWatchlist();
  if (!list.includes(t)) save([...list, t]);
}

export function removeFromWatchlist(ticker: string) {
  save(getWatchlist().filter((t) => t !== ticker.toUpperCase()));
}

export function toggleWatchlist(ticker: string): boolean {
  const watched = isWatched(ticker);
  watched ? removeFromWatchlist(ticker) : addToWatchlist(ticker);
  return !watched;
}

/** Subscribe to changes (same tab via custom event, other tabs via storage). */
export function onWatchlistChange(fn: () => void): () => void {
  window.addEventListener(EVENT, fn);
  window.addEventListener("storage", fn);
  return () => {
    window.removeEventListener(EVENT, fn);
    window.removeEventListener("storage", fn);
  };
}

// ---------------------------------------------------------------------------
// Price alerts — a target and/or stop per watched ticker.
//
// Also device-local, so alerts work on the static deploy with no account and
// no backend. They are evaluated against whatever price the UI already has, so
// there is no polling and no extra request: a "trigger" means the last price
// the app saw crossed the level, not a guaranteed real-time fill.
// ---------------------------------------------------------------------------
const ALERT_KEY = "alphahunter.alerts";

export type Alert = { target?: number; stop?: number };
export type AlertState = "target" | "stop" | null;

export function getAlerts(): Record<string, Alert> {
  try {
    const raw = localStorage.getItem(ALERT_KEY);
    const obj = raw ? JSON.parse(raw) : {};
    return obj && typeof obj === "object" && !Array.isArray(obj) ? obj : {};
  } catch {
    return {};
  }
}

export function getAlert(ticker: string): Alert {
  return getAlerts()[ticker.toUpperCase()] ?? {};
}

/** Set (or with both fields empty, clear) the alert for one ticker. */
export function setAlert(ticker: string, alert: Alert) {
  const t = ticker.toUpperCase().trim();
  if (!t) return;
  const all = getAlerts();
  const clean: Alert = {};
  if (Number.isFinite(alert.target) && (alert.target as number) > 0) clean.target = alert.target;
  if (Number.isFinite(alert.stop) && (alert.stop as number) > 0) clean.stop = alert.stop;
  if (clean.target == null && clean.stop == null) delete all[t];
  else all[t] = clean;
  try {
    localStorage.setItem(ALERT_KEY, JSON.stringify(all));
  } catch {
    /* private mode / quota */
  }
  window.dispatchEvent(new Event(EVENT));
}

export function clearAlert(ticker: string) {
  setAlert(ticker, {});
}

/**
 * Which level, if any, the current price has crossed.
 *
 * The stop is checked first on purpose: if a gap takes the price through both
 * levels, the risk side is the one a trader needs to see.
 */
export function alertState(price: number | null | undefined, alert: Alert): AlertState {
  if (price == null || !Number.isFinite(price)) return null;
  if (alert.stop != null && price <= alert.stop) return "stop";
  if (alert.target != null && price >= alert.target) return "target";
  return null;
}
