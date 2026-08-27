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
