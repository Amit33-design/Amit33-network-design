"""Two-stock daily rebalancing — volatility harvesting, measured.

The strategy: hold two stocks at fixed weights, and every day sell whichever
has grown past its weight to buy whichever has fallen short. This is Shannon's
Demon, and the gain it produces is real but widely misdescribed.

What actually drives it is NOT "the price goes back up after it goes down".
No mean reversion is required. The bonus comes from volatility and imperfect
correlation, and to first order is:

    bonus ≈ ½ · w₁w₂ · (σ₁² + σ₂² − 2ρσ₁σ₂)

Read that carefully, because it says three things that matter:

  * it scales with VARIANCE, so it rewards genuinely volatile names;
  * it scales with (1 − ρ), so the two stocks must not move together —
    two AI semiconductor names will harvest almost nothing;
  * it is a bonus over the WEIGHTED AVERAGE of the two stocks' own compound
    returns, not over the better one. If one name triples and the other is
    flat, rebalancing systematically sells the winner and you end up behind
    simply holding the winner. That is the honest cost of the strategy and
    it is what the comparison columns here exist to show.

`simulate` is pure — two price series in, a result dict out — so the whole
thing is testable offline, including the cost and tax drag that decide whether
any of this survives contact with a brokerage.
"""
from __future__ import annotations

import math

TRADING_DAYS = 252


def _safe_series(xs: list[float]) -> list[float]:
    return [float(x) for x in xs if x is not None and float(x) > 0]


def realized_vol(prices: list[float]) -> float | None:
    """Annualised volatility of daily log returns."""
    if len(prices) < 3:
        return None
    rets = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def correlation(a: list[float], b: list[float]) -> float | None:
    """Correlation of the two series' daily returns."""
    n = min(len(a), len(b))
    if n < 3:
        return None
    ra = [a[i] / a[i - 1] - 1 for i in range(1, n)]
    rb = [b[i] / b[i - 1] - 1 for i in range(1, n)]
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va <= 0 or vb <= 0:
        return None
    return cov / math.sqrt(va * vb)


def expected_bonus(vol_a: float, vol_b: float, rho: float, w: float = 0.5) -> float:
    """Analytic rebalancing bonus, in percent per year.

    Useful as a sanity check on the simulation: if the two disagree wildly,
    one of them is wrong.
    """
    return 0.5 * w * (1 - w) * (vol_a ** 2 + vol_b ** 2 - 2 * rho * vol_a * vol_b) * 100


def _cagr(start: float, end: float, days: int) -> float | None:
    if start <= 0 or end <= 0 or days <= 0:
        return None
    years = days / TRADING_DAYS
    return ((end / start) ** (1 / years) - 1) * 100 if years > 0 else None


def _max_drawdown(curve: list[float]) -> float:
    peak, mdd = curve[0] if curve else 1.0, 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v / peak - 1)
    return mdd * 100


def simulate(
    prices_a: list[float],
    prices_b: list[float],
    *,
    weight_a: float = 0.5,
    capital: float = 100_000.0,
    cost_bps: float = 0.0,
    band: float = 0.0,
    tax_rate: float = 0.0,
) -> dict:
    """Daily rebalancing to fixed weights, against the honest comparisons.

    ``band`` is a no-trade tolerance: with band=0.02 nothing trades until a
    weight drifts more than 2 percentage points off target. Zero means
    rebalance every single day, which is what the strategy says literally and
    is also where costs do the most damage.

    ``cost_bps`` is charged on the traded notional each rebalance, and
    ``tax_rate`` is applied at the end to net gains, since daily rebalancing
    in a taxable account realises short-term gains continuously.
    """
    a, b = _safe_series(prices_a), _safe_series(prices_b)
    n = min(len(a), len(b))
    if n < 30:
        return {"error": "need at least 30 overlapping daily prices"}
    a, b = a[-n:], b[-n:]
    w_b = 1 - weight_a

    # Rebalanced book, tracked as share counts so trades are explicit.
    val_a, val_b = capital * weight_a, capital * w_b
    sh_a, sh_b = val_a / a[0], val_b / b[0]
    curve, turnover, trades, costs = [1.0], 0.0, 0, 0.0

    for i in range(1, n):
        val_a, val_b = sh_a * a[i], sh_b * b[i]
        total = val_a + val_b
        if total <= 0:
            break
        drift = abs(val_a / total - weight_a)
        if drift > band:
            target_a = total * weight_a
            traded = abs(target_a - val_a)
            cost = traded * cost_bps / 10_000.0
            total -= cost
            costs += cost
            turnover += traded
            trades += 1
            sh_a = (total * weight_a) / a[i]
            sh_b = (total * w_b) / b[i]
        curve.append(total / capital)

    final = curve[-1] * capital
    days = n - 1

    # The comparisons that decide whether this was worth doing.
    hold_a = capital * (a[-1] / a[0])
    hold_b = capital * (b[-1] / b[0])
    # Bought 50/50 once and never touched — isolates the rebalancing bonus
    # from the simple fact of owning the two stocks.
    static = capital * (weight_a * a[-1] / a[0] + w_b * b[-1] / b[0])
    static_curve = [weight_a * a[i] / a[0] + w_b * b[i] / b[0] for i in range(n)]

    # Weighted average of each stock's own COMPOUND return — the baseline the
    # analytic formula is defined against.
    g_a = _cagr(capital, hold_a, days) or 0.0
    g_b = _cagr(capital, hold_b, days) or 0.0
    weighted_avg_cagr = weight_a * g_a + w_b * g_b

    gain = final - capital
    after_tax = capital + gain * (1 - tax_rate) if gain > 0 else final

    return {
        "days": days,
        "years": round(days / TRADING_DAYS, 2),
        "capital": capital,
        "final_value": round(final, 2),
        "after_tax_value": round(after_tax, 2),
        "profit": round(final - capital, 2),
        "cagr_%": round(_cagr(capital, final, days) or 0, 2),
        "max_drawdown_%": round(_max_drawdown(curve), 2),
        "rebalances": trades,
        "turnover_x_capital": round(turnover / capital, 1),
        "trading_costs": round(costs, 2),
        # Comparisons
        "hold_a_value": round(hold_a, 2),
        "hold_b_value": round(hold_b, 2),
        "static_5050_value": round(static, 2),
        "static_5050_cagr_%": round(_cagr(capital, static, days) or 0, 2),
        "static_max_drawdown_%": round(_max_drawdown(static_curve), 2),
        # Two different questions, and conflating them is the classic error.
        #
        # vs_static: what rebalancing added over buying the same two stocks in
        #   the same proportions and never touching them. This is the PRACTICAL
        #   number — the choice an investor actually faces.
        #
        # vs_weighted_avg: the bonus over the weighted average of the two
        #   stocks' own compound returns. This is the THEORETICAL number the
        #   ½·w₁w₂·(σ₁²+σ₂²−2ρσ₁σ₂) formula predicts, and the only one it can
        #   be checked against. It is larger than vs_static because a static
        #   blend drifts toward whichever stock won, which is itself a form of
        #   momentum exposure rather than something rebalancing provides.
        "rebalancing_bonus_%": round((_cagr(capital, final, days) or 0)
                                     - (_cagr(capital, static, days) or 0), 2),
        "weighted_avg_cagr_%": round(weighted_avg_cagr, 2),
        "bonus_vs_weighted_avg_%": round((_cagr(capital, final, days) or 0)
                                         - weighted_avg_cagr, 2),
        "beat_best_single_stock": final > max(hold_a, hold_b),
        "vol_a_%": round((realized_vol(a) or 0) * 100, 1),
        "vol_b_%": round((realized_vol(b) or 0) * 100, 1),
        "correlation": round(correlation(a, b) or 0, 3),
        "expected_bonus_%": round(
            expected_bonus(realized_vol(a) or 0, realized_vol(b) or 0,
                           correlation(a, b) or 0, weight_a), 2),
        "curve": [round(c, 5) for c in curve],
    }


def rank_pairs(series: dict[str, list[float]], *, top: int = 10) -> list[dict]:
    """Rank every pair by the analytic bonus: high vol, low correlation.

    Ranking on the formula rather than on backtested profit is deliberate —
    picking the pair with the best realized return over the sample is just
    choosing the two stocks that went up most, which says nothing about
    whether rebalancing helped.
    """
    names = [k for k, v in series.items() if len(_safe_series(v)) >= 60]
    vols = {k: realized_vol(_safe_series(series[k])) for k in names}
    out = []
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            sa, sb = _safe_series(series[x]), _safe_series(series[y])
            m = min(len(sa), len(sb))
            rho = correlation(sa[-m:], sb[-m:])
            if vols[x] is None or vols[y] is None or rho is None:
                continue
            out.append({
                "pair": f"{x}/{y}", "a": x, "b": y,
                "vol_a_%": round(vols[x] * 100, 1),
                "vol_b_%": round(vols[y] * 100, 1),
                "correlation": round(rho, 3),
                "expected_bonus_%": round(expected_bonus(vols[x], vols[y], rho), 2),
            })
    out.sort(key=lambda d: -d["expected_bonus_%"])
    return out[:top]


def capital_for_goal(goal: float, bonus_pct: float) -> float | None:
    """Capital needed for ``goal`` per year from the rebalancing bonus alone."""
    if bonus_pct <= 0:
        return None
    return goal / (bonus_pct / 100.0)
