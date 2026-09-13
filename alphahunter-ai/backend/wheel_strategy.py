"""The wheel, backtested: sell puts, take assignment, sell calls, repeat.

The strategy in the user's words: put $25k behind a cash-secured put, close it
at 70% of max profit and re-sell, and if assigned switch to covered calls until
the shares are called away. This is the wheel, and it is one of the few retail
income strategies with a genuinely favourable structure — you are paid for
providing insurance, and most insurance expires worthless.

It also has a shape people consistently misread. The return distribution is
many small wins and occasional large losses: you keep the full downside of
owning the stock while capping the upside at the strike. A 30-40% year is
entirely possible. So is giving back three years of premium in one quarter,
because the assignment happens precisely when the stock is falling.

Option prices come from Black-Scholes on trailing realized volatility, because
historical option chains are not available from a free source. That is an
approximation and it cuts BOTH ways: real implied vol usually exceeds realized
(so premiums here are conservative), but real chains have bid-ask spreads and
strike granularity that this ignores. Treat the output as the shape of the
strategy, not a fill-accurate P&L.

Pure functions. No network.
"""
from __future__ import annotations

import math

TRADING_DAYS = 252


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_put(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    """Black-Scholes European put."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, K - S)
    d1 = (math.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, S - K)
    d1 = (math.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def trailing_vol(prices: list[float], i: int, window: int = 60) -> float:
    """Annualised realized vol over the window ENDING at i — never past it."""
    lo = max(1, i - window + 1)
    rets = [math.log(prices[j] / prices[j - 1]) for j in range(lo, i + 1)
            if prices[j - 1] > 0 and prices[j] > 0]
    if len(rets) < 10:
        return 0.35
    m = sum(rets) / len(rets)
    var = sum((x - m) ** 2 for x in rets) / max(1, len(rets) - 1)
    return max(0.05, min(2.5, math.sqrt(var) * math.sqrt(TRADING_DAYS)))


def simulate_wheel(
    prices: list[float],
    *,
    capital: float = 25_000.0,
    dte: int = 30,
    put_otm: float = 0.05,
    call_otm: float = 0.05,
    take_profit: float = 0.70,
    iv_premium: float = 1.15,
    commission_per_contract: float = 0.65,
) -> dict:
    """Run the wheel over a daily price series.

    ``take_profit`` closes a short option once it has lost that fraction of the
    premium collected — the "close at 70% profit and re-sell" rule, which is
    the part of this strategy that genuinely helps: it removes the last of the
    gamma risk for the smallest remaining reward.

    ``iv_premium`` scales realized vol up to stand in for implied, since
    options systematically price above realized. 1.15 is deliberately modest.
    """
    px = [float(p) for p in prices if p and p > 0]
    if len(px) < 120:
        return {"error": "need at least 120 daily prices"}

    cash = capital
    shares = 0
    # Open short option: (kind, strike, expiry_index, premium_collected, contracts)
    pos: tuple[str, float, int, float, int] | None = None

    trades: list[dict] = []
    assignments = calls_away = 0
    premium_collected = 0.0
    commissions = 0.0
    equity: list[float] = []

    i = 60                                  # warm-up for the vol window
    while i < len(px):
        S = px[i]
        sigma = trailing_vol(px, i) * iv_premium

        # ---- mark to market ----
        mark = cash + shares * S
        if pos:
            kind, K, exp_i, prem, n = pos
            T = max(0.0, (exp_i - i) / TRADING_DAYS)
            val = (bs_put(S, K, T, sigma) if kind == "put" else bs_call(S, K, T, sigma))
            mark -= val * 100 * n           # short option is a liability
        equity.append(mark)

        # ---- manage an open position ----
        if pos:
            kind, K, exp_i, prem, n = pos
            T = max(0.0, (exp_i - i) / TRADING_DAYS)
            val = (bs_put(S, K, T, sigma) if kind == "put" else bs_call(S, K, T, sigma))

            if val <= prem * (1 - take_profit) and i < exp_i:
                # Bought back cheap: keep most of the premium, free the capital.
                cash -= val * 100 * n
                commissions += commission_per_contract * n
                cash -= commission_per_contract * n
                trades.append({"type": f"{kind}_closed_early", "at": i,
                               "kept": round((prem - val) * 100 * n, 2)})
                pos = None
            elif i >= exp_i:
                if kind == "put":
                    if S < K:               # assigned: buy the shares at K
                        bought = 100 * n
                        cash -= K * bought
                        shares += bought
                        assignments += 1
                        trades.append({"type": "assigned", "at": i, "strike": K,
                                       "price": round(S, 2)})
                    else:
                        trades.append({"type": "put_expired", "at": i})
                else:
                    if S > K:               # called away: sell shares at K
                        sold = min(shares, 100 * n)
                        cash += K * sold
                        shares -= sold
                        calls_away += 1
                        trades.append({"type": "called_away", "at": i, "strike": K,
                                       "price": round(S, 2)})
                    else:
                        trades.append({"type": "call_expired", "at": i})
                pos = None

        # ---- open a new position ----
        if pos is None:
            exp_i = min(i + dte, len(px) - 1)
            T = (exp_i - i) / TRADING_DAYS
            if T > 0:
                if shares >= 100:
                    K = round(S * (1 + call_otm), 2)
                    n = shares // 100
                    prem = bs_call(S, K, T, sigma)
                    if prem > 0.05:
                        cash += prem * 100 * n - commission_per_contract * n
                        commissions += commission_per_contract * n
                        premium_collected += prem * 100 * n
                        pos = ("call", K, exp_i, prem, n)
                else:
                    K = round(S * (1 - put_otm), 2)
                    n = int(cash // (K * 100))       # cash-secured: no leverage
                    if n >= 1:
                        prem = bs_put(S, K, T, sigma)
                        if prem > 0.05:
                            cash += prem * 100 * n - commission_per_contract * n
                            commissions += commission_per_contract * n
                            premium_collected += prem * 100 * n
                            pos = ("put", K, exp_i, prem, n)
        i += 1

    final = cash + shares * px[-1]
    if pos:                                  # close any open short at fair value
        kind, K, exp_i, prem, n = pos
        sigma = trailing_vol(px, len(px) - 1) * iv_premium
        T = max(0.0, (exp_i - (len(px) - 1)) / TRADING_DAYS)
        val = bs_put(px[-1], K, T, sigma) if kind == "put" else bs_call(px[-1], K, T, sigma)
        final -= val * 100 * n

    years = (len(px) - 60) / TRADING_DAYS
    cagr = ((final / capital) ** (1 / years) - 1) * 100 if years > 0 and final > 0 else None
    hold = capital * (px[-1] / px[60])
    hold_cagr = ((hold / capital) ** (1 / years) - 1) * 100 if years > 0 else None

    peak, mdd = equity[0] if equity else capital, 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v / peak - 1)

    # A cash-secured put needs the full strike x 100 in collateral. On $25k,
    # SPY at ~$550 needs ~$55k for a single contract, so the strategy is not
    # merely unprofitable there — it is impossible. Reporting that as "0.0%
    # CAGR" makes it look like a bad result rather than an unavailable one.
    if not trades:
        cheapest = min(px[60:]) * (1 - put_otm) * 100
        return {
            "capital": capital,
            "error": "no trades possible",
            "reason": (f"a cash-secured put needs about ${cheapest:,.0f} of collateral "
                       f"per contract at this price; ${capital:,.0f} is not enough"),
            "min_capital_needed": round(cheapest, 2),
        }

    return {
        "capital": capital,
        "final_value": round(final, 2),
        "profit": round(final - capital, 2),
        "cagr_%": round(cagr, 2) if cagr is not None else None,
        "years": round(years, 2),
        "premium_collected": round(premium_collected, 2),
        "commissions": round(commissions, 2),
        "assignments": assignments,
        "called_away": calls_away,
        "trades": len(trades),
        "max_drawdown_%": round(mdd * 100, 2),
        "still_holding_shares": shares,
        # The comparison that matters: the wheel caps your upside, so on a
        # stock that ran it will lose to simply owning it.
        "buy_hold_value": round(hold, 2),
        "buy_hold_cagr_%": round(hold_cagr, 2) if hold_cagr is not None else None,
        "beat_buy_hold": final > hold,
    }
