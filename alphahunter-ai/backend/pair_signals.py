"""Daily buy/sell instructions for a two-stock rebalancing book.

`pair_rebalance.py` answers "would this have worked?". This answers "what do I
do today?" — given what you hold and what the two stocks are worth right now,
it produces a concrete order: sell N of one, buy M of the other.

Three things separate a usable instruction from a naive one:

  WHOLE SHARES      you cannot buy 3.7 shares, so the order is rounded and the
                    residual drift is reported rather than hidden.
  A NO-TRADE BAND   rebalancing on a 0.3% drift costs more in spread and
                    commission than it harvests. Nothing trades until the
                    weight is meaningfully off.
  A MINIMUM TICKET  even inside the band, a $14 trade is not worth placing.

Pure functions. No network, no state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_BAND = 0.03          # 3 percentage points of weight drift
DEFAULT_MIN_TRADE = 100.0    # dollars


@dataclass
class Order:
    action: str                      # "hold" | "rebalance"
    sell_ticker: str | None = None
    sell_shares: int = 0
    sell_value: float = 0.0
    buy_ticker: str | None = None
    buy_shares: int = 0
    buy_value: float = 0.0
    drift_pp: float = 0.0            # percentage points off target
    weight_a: float = 0.0
    total_value: float = 0.0
    reason: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "sell": ({"ticker": self.sell_ticker, "shares": self.sell_shares,
                      "value": round(self.sell_value, 2)} if self.sell_shares else None),
            "buy": ({"ticker": self.buy_ticker, "shares": self.buy_shares,
                     "value": round(self.buy_value, 2)} if self.buy_shares else None),
            "drift_pp": round(self.drift_pp, 2),
            "weight_a": round(self.weight_a, 4),
            "total_value": round(self.total_value, 2),
            "reason": self.reason,
            "warnings": self.warnings,
        }


def open_position(ticker_a: str, ticker_b: str, price_a: float, price_b: float,
                  capital: float, target_a: float = 0.5) -> dict:
    """How many whole shares of each to buy to start the book."""
    if price_a <= 0 or price_b <= 0 or capital <= 0:
        return {"error": "prices and capital must be positive"}
    sh_a = int((capital * target_a) // price_a)
    sh_b = int((capital * (1 - target_a)) // price_b)
    spent = sh_a * price_a + sh_b * price_b
    warnings = []
    if sh_a == 0 or sh_b == 0:
        warnings.append(
            f"${capital:,.0f} is not enough to hold both — "
            f"one share each costs ${price_a + price_b:,.2f}")
    return {
        "buy": [{"ticker": ticker_a, "shares": sh_a, "value": round(sh_a * price_a, 2)},
                {"ticker": ticker_b, "shares": sh_b, "value": round(sh_b * price_b, 2)}],
        "invested": round(spent, 2),
        "cash_left": round(capital - spent, 2),
        "warnings": warnings,
    }


def daily_order(
    ticker_a: str, ticker_b: str,
    price_a: float, price_b: float,
    shares_a: int, shares_b: int,
    *,
    target_a: float = 0.5,
    band: float = DEFAULT_BAND,
    min_trade: float = DEFAULT_MIN_TRADE,
) -> Order:
    """Today's instruction for the book, or an explicit hold."""
    val_a, val_b = shares_a * price_a, shares_b * price_b
    total = val_a + val_b
    if total <= 0:
        return Order("hold", reason="no position to rebalance", total_value=0.0)

    w_a = val_a / total
    drift = w_a - target_a
    drift_pp = drift * 100

    base = Order("hold", drift_pp=drift_pp, weight_a=w_a, total_value=total)

    if abs(drift) <= band:
        base.reason = (
            f"{ticker_a} is {w_a * 100:.1f}% of the book against a "
            f"{target_a * 100:.0f}% target — inside the "
            f"{band * 100:.0f}pp band, so nothing to do today")
        return base

    # Move half the imbalance into the other leg: selling exactly the excess
    # restores the target in one trade.
    excess = val_a - total * target_a
    if excess > 0:
        sell_t, sell_px, buy_t, buy_px, avail = ticker_a, price_a, ticker_b, price_b, shares_a
    else:
        sell_t, sell_px, buy_t, buy_px, avail = ticker_b, price_b, ticker_a, price_a, shares_b
        excess = -excess

    sell_sh = min(int(excess // sell_px), avail)
    if sell_sh < 1:
        base.reason = (
            f"{sell_t} is {abs(drift_pp):.1f}pp overweight but that is less than "
            f"one share (${sell_px:,.2f}) — hold")
        return base

    sell_val = sell_sh * sell_px
    if sell_val < min_trade:
        base.reason = (
            f"rebalancing would only move ${sell_val:,.2f}, below the "
            f"${min_trade:,.0f} minimum — not worth the spread")
        return base

    buy_sh = int(sell_val // buy_px)
    warnings = []
    if buy_sh < 1:
        base.reason = (
            f"${sell_val:,.2f} does not buy a single share of {buy_t} "
            f"(${buy_px:,.2f}) — hold")
        return base

    buy_val = buy_sh * buy_px
    leftover = sell_val - buy_val
    if leftover > buy_px * 0.5:
        warnings.append(f"${leftover:,.2f} left as cash — whole shares only")

    return Order(
        "rebalance",
        sell_ticker=sell_t, sell_shares=sell_sh, sell_value=sell_val,
        buy_ticker=buy_t, buy_shares=buy_sh, buy_value=buy_val,
        drift_pp=drift_pp, weight_a=w_a, total_value=total,
        reason=(f"{sell_t} has run to {max(w_a, 1 - w_a) * 100:.1f}% of the book "
                f"({abs(drift_pp):.1f}pp over target) — sell {sell_sh} "
                f"{sell_t} (${sell_val:,.2f}) and buy {buy_sh} {buy_t}"),
        warnings=warnings,
    )
