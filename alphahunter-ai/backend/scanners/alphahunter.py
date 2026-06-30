"""AlphaHunter scanner — the spec's "Existing Screener", extended.

Keeps the original strategy:
    Revenue > $1B  AND  down >=5% today  AND  down >=20% over the month
and extends it with:
    RSI < 35, Volume > 150% of average, price above EMA200,
    positive free cash flow, institutional ownership > 50%,
    and a no-bankruptcy-risk sanity check.

Every criterion is recorded as a ``Criterion`` (pass/fail + detail) so the UI
and the AI explainer can show exactly why a name did or didn't qualify.

By default ``require_all=True`` reproduces the strict AND-screen. Set it False
to surface "near-miss" candidates (passes the core crash filter but misses one
or two confirmation signals) and let the composite score rank them.
"""
from __future__ import annotations

from backend.config import settings
from backend.indicators import technical as ta
from backend.scanners.base import Criterion, ScanHit
from backend.utils.market_data import StockSnapshot

# Core crash criteria that must always hold for a name to be considered.
CORE_CRITERIA = {"revenue_over_1b", "down_5pct_day", "down_20pct_month"}


class AlphaHunterScanner:
    name = "alphahunter"

    def __init__(self, require_all: bool = True) -> None:
        self.require_all = require_all

    def evaluate(self, snap: StockSnapshot) -> ScanHit | None:
        ind = ta.indicator_bundle(snap.history)
        last = snap.last_close
        if last is None:
            return None

        day_change = ind["ret_1d"]
        month_change = ind["ret_20d"]   # ~1 trading month
        rsi = ind["rsi"]
        vol_ratio = ind["volume_ratio"]
        above_200 = ind["above_ema200"]
        revenue = snap.revenue
        usd = snap.financial_currency == "USD"
        fcf = snap.free_cash_flow
        inst = snap.institutional_ownership

        criteria: list[Criterion] = []

        # --- core crash strategy ---
        criteria.append(Criterion(
            "revenue_over_1b",
            usd and revenue >= settings.revenue_floor,
            f"revenue ${revenue/1e9:.2f}B ({snap.financial_currency or 'n/a'})",
        ))
        criteria.append(Criterion(
            "down_5pct_day",
            day_change is not None and day_change <= settings.day_drop_pct,
            f"day {day_change:.1f}%" if day_change is not None else "day n/a",
        ))
        criteria.append(Criterion(
            "down_20pct_month",
            month_change is not None and month_change <= settings.month_drop_pct,
            f"month {month_change:.1f}%" if month_change is not None else "month n/a",
        ))

        # --- extended confirmation signals ---
        criteria.append(Criterion(
            "rsi_below_35",
            rsi is not None and rsi < settings.rsi_max,
            f"RSI {rsi:.1f}" if rsi is not None else "RSI n/a",
        ))
        criteria.append(Criterion(
            "volume_spike",
            vol_ratio is not None and vol_ratio >= settings.volume_spike_ratio,
            f"vol x{vol_ratio:.2f} avg" if vol_ratio is not None else "vol n/a",
        ))
        criteria.append(Criterion(
            "above_ema200",
            bool(above_200),
            "above EMA200" if above_200 else "below/at EMA200",
        ))
        criteria.append(Criterion(
            "positive_fcf",
            fcf is not None and fcf > 0,
            f"FCF ${fcf/1e9:.2f}B" if fcf is not None else "FCF n/a",
        ))
        criteria.append(Criterion(
            "institutional_over_50",
            inst is not None and inst > settings.institutional_ownership_min,
            f"inst {inst*100:.0f}%" if inst is not None else "inst n/a",
        ))
        criteria.append(Criterion(
            "no_bankruptcy_risk",
            self._no_bankruptcy_risk(snap),
            self._bankruptcy_detail(snap),
        ))

        # Decide whether this is a hit.
        core_ok = all(c.passed for c in criteria if c.name in CORE_CRITERIA)
        if not core_ok:
            return None
        if self.require_all and not all(c.passed for c in criteria):
            return None

        metrics = {
            "price": round(last, 2),
            "day_%": round(day_change, 1) if day_change is not None else None,
            "month_%": round(month_change, 1) if month_change is not None else None,
            "rsi": round(rsi, 1) if rsi is not None else None,
            "volume_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
            "above_ema200": bool(above_200),
            "revenue_$B": round(revenue / 1e9, 2),
            "fcf_$B": round(fcf / 1e9, 2) if fcf is not None else None,
            "institutional_%": round(inst * 100, 1) if inst is not None else None,
            "rec_mean": snap.recommendation_mean,
            "target": snap.target_mean_price,
            "passed": [c.name for c in criteria if c.passed],
            "failed": [c.name for c in criteria if not c.passed],
            "indicators": ind,
        }
        return ScanHit(ticker=snap.ticker, metrics=metrics, criteria=criteria)

    # ---- bankruptcy-risk proxy (no paid data feed required) ----
    @staticmethod
    def _no_bankruptcy_risk(snap: StockSnapshot) -> bool:
        info = snap.info
        current_ratio = info.get("currentRatio")
        debt_to_equity = info.get("debtToEquity")
        ebitda = info.get("ebitda")
        # Healthy if liquidity covers short-term liabilities and leverage isn't
        # extreme; positive EBITDA is a coarse going-concern signal.
        if current_ratio is not None and current_ratio < 1.0:
            return False
        if debt_to_equity is not None and debt_to_equity > 400:  # >4x equity
            return False
        if ebitda is not None and ebitda < 0:
            return False
        return True

    @staticmethod
    def _bankruptcy_detail(snap: StockSnapshot) -> str:
        info = snap.info
        cr = info.get("currentRatio")
        de = info.get("debtToEquity")
        bits = []
        if cr is not None:
            bits.append(f"CR {cr:.2f}")
        if de is not None:
            bits.append(f"D/E {de:.0f}%")
        return ", ".join(bits) if bits else "solvency data n/a"
