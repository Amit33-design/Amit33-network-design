// Daily pair-rebalancing instructions, client side.
//
// SOURCE OF TRUTH: backend/pair_signals.py. This is a deliberate port so the
// page works on the static deploy with no backend. Same constants, same order
// of checks. Change one, change both.

export const DEFAULT_BAND = 0.03;        // 3pp of weight drift
export const DEFAULT_MIN_TRADE = 100;    // dollars

export type PairPick = {
  a: string; b: string;
  targetA: number;
  sharesA: number; sharesB: number;
  openedAt?: string;
};

export type Order = {
  action: "hold" | "rebalance";
  sell?: { ticker: string; shares: number; value: number };
  buy?: { ticker: string; shares: number; value: number };
  driftPp: number;
  weightA: number;
  totalValue: number;
  reason: string;
  warnings: string[];
};

export function openPosition(
  a: string, b: string, priceA: number, priceB: number,
  capital: number, targetA = 0.5,
) {
  const shA = Math.floor((capital * targetA) / priceA) || 0;
  const shB = Math.floor((capital * (1 - targetA)) / priceB) || 0;
  const invested = shA * priceA + shB * priceB;
  const warnings: string[] = [];
  if (shA === 0 || shB === 0) {
    warnings.push(
      `$${capital.toLocaleString()} isn't enough to hold both — one share each costs $${(priceA + priceB).toFixed(2)}`);
  }
  return {
    buy: [
      { ticker: a, shares: shA, value: +(shA * priceA).toFixed(2) },
      { ticker: b, shares: shB, value: +(shB * priceB).toFixed(2) },
    ],
    invested: +invested.toFixed(2),
    cashLeft: +(capital - invested).toFixed(2),
    warnings,
  };
}

export function dailyOrder(
  a: string, b: string,
  priceA: number, priceB: number,
  sharesA: number, sharesB: number,
  { targetA = 0.5, band = DEFAULT_BAND, minTrade = DEFAULT_MIN_TRADE } = {},
): Order {
  const valA = sharesA * priceA;
  const valB = sharesB * priceB;
  const total = valA + valB;
  if (total <= 0) {
    return { action: "hold", driftPp: 0, weightA: 0, totalValue: 0,
             reason: "no position to rebalance", warnings: [] };
  }

  const wA = valA / total;
  const drift = wA - targetA;
  const driftPp = drift * 100;
  const base: Order = { action: "hold", driftPp, weightA: wA, totalValue: total,
                        reason: "", warnings: [] };

  if (Math.abs(drift) <= band) {
    base.reason = `${a} is ${(wA * 100).toFixed(1)}% of the book against a ${(targetA * 100).toFixed(0)}% target — inside the ${(band * 100).toFixed(0)}pp band, nothing to do today`;
    return base;
  }

  let excess = valA - total * targetA;
  const sellIsA = excess > 0;
  if (!sellIsA) excess = -excess;
  const sellT = sellIsA ? a : b;
  const sellPx = sellIsA ? priceA : priceB;
  const buyT = sellIsA ? b : a;
  const buyPx = sellIsA ? priceB : priceA;
  const avail = sellIsA ? sharesA : sharesB;

  const sellSh = Math.min(Math.floor(excess / sellPx), avail);
  if (sellSh < 1) {
    base.reason = `${sellT} is ${Math.abs(driftPp).toFixed(1)}pp overweight but that's less than one share ($${sellPx.toFixed(2)}) — hold`;
    return base;
  }

  const sellVal = sellSh * sellPx;
  if (sellVal < minTrade) {
    base.reason = `rebalancing would only move $${sellVal.toFixed(2)}, below the $${minTrade} minimum — not worth the spread`;
    return base;
  }

  const buySh = Math.floor(sellVal / buyPx);
  if (buySh < 1) {
    base.reason = `$${sellVal.toFixed(2)} doesn't buy a single share of ${buyT} ($${buyPx.toFixed(2)}) — hold`;
    return base;
  }

  const buyVal = buySh * buyPx;
  const warnings: string[] = [];
  const leftover = sellVal - buyVal;
  if (leftover > buyPx * 0.5) {
    warnings.push(`$${leftover.toFixed(2)} left as cash — whole shares only`);
  }

  return {
    action: "rebalance",
    sell: { ticker: sellT, shares: sellSh, value: +sellVal.toFixed(2) },
    buy: { ticker: buyT, shares: buySh, value: +buyVal.toFixed(2) },
    driftPp, weightA: wA, totalValue: total,
    reason: `${sellT} has run to ${(Math.max(wA, 1 - wA) * 100).toFixed(1)}% of the book (${Math.abs(driftPp).toFixed(1)}pp over target) — sell ${sellSh} ${sellT} ($${sellVal.toFixed(2)}) and buy ${buySh} ${buyT}`,
    warnings,
  };
}

// ---- device-local storage for the chosen pair -----------------------------
const KEY = "alphahunter.pair";

export function getPair(): PairPick | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export function savePair(p: PairPick | null) {
  try {
    if (p) localStorage.setItem(KEY, JSON.stringify(p));
    else localStorage.removeItem(KEY);
  } catch { /* private mode */ }
  window.dispatchEvent(new Event("pair-changed"));
}

export function onPairChange(fn: () => void): () => void {
  window.addEventListener("pair-changed", fn);
  window.addEventListener("storage", fn);
  return () => {
    window.removeEventListener("pair-changed", fn);
    window.removeEventListener("storage", fn);
  };
}
