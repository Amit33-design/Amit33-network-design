"""Backtesting engine.

Replays a scanner's entry signal over historical OHLCV and measures forward
returns over a fixed hold, reporting the spec's metrics: win rate, average /
median return, max drawdown, Sharpe, Sortino, profit factor, average hold days.

This is a single-name, signal-quality backtest (does the setup tend to bounce?)
rather than a full portfolio simulator — intentionally simple and transparent.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    trades: int
    win_rate: float
    avg_return: float
    median_return: float
    max_drawdown: float
    sharpe: float
    sortino: float
    profit_factor: float
    avg_hold_days: float

    def as_dict(self) -> dict:
        return {
            "trades": self.trades,
            "win_rate": round(self.win_rate, 3),
            "avg_return_%": round(self.avg_return, 2),
            "median_return_%": round(self.median_return, 2),
            "max_drawdown_%": round(self.max_drawdown, 2),
            "sharpe": round(self.sharpe, 2),
            "sortino": round(self.sortino, 2),
            "profit_factor": round(self.profit_factor, 2),
            "avg_hold_days": round(self.avg_hold_days, 1),
        }


def _rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def backtest_oversold(
    hist: pd.DataFrame,
    hold_days: int = 10,
    day_drop: float = -5.0,
    month_drop: float = -20.0,
    rsi_max: float = 35.0,
) -> BacktestResult:
    """Entry when the AlphaHunter crash setup fires; exit after ``hold_days``."""
    closes = hist["Close"].dropna()
    if len(closes) < 60:
        return BacktestResult(0, 0, 0, 0, 0, 0, 0, 0, 0)

    rsi = _rsi(closes)
    day_ret = closes.pct_change() * 100
    month_ret = closes.pct_change(20) * 100

    returns: list[float] = []
    i = 21
    last_exit = -1
    while i < len(closes) - hold_days:
        if i <= last_exit:
            i += 1
            continue
        if (day_ret.iloc[i] <= day_drop
                and month_ret.iloc[i] <= month_drop
                and (pd.isna(rsi.iloc[i]) or rsi.iloc[i] < rsi_max)):
            entry = closes.iloc[i]
            exit_px = closes.iloc[i + hold_days]
            returns.append((exit_px - entry) / entry * 100)
            last_exit = i + hold_days
        i += 1

    if not returns:
        return BacktestResult(0, 0, 0, 0, 0, 0, 0, 0, 0)

    arr = np.array(returns)
    wins = arr[arr > 0]
    losses = arr[arr <= 0]
    win_rate = len(wins) / len(arr)
    avg = float(arr.mean())
    median = float(np.median(arr))
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    downside = float(losses.std(ddof=1)) if len(losses) > 1 else 0.0
    sharpe = (avg / std * math.sqrt(252 / hold_days)) if std else 0.0
    sortino = (avg / downside * math.sqrt(252 / hold_days)) if downside else 0.0
    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss else float("inf")

    # Max drawdown of the equity curve built from sequential trades.
    equity = (1 + arr / 100).cumprod()
    peak = np.maximum.accumulate(equity)
    drawdown = float(((equity - peak) / peak).min() * 100)

    return BacktestResult(
        trades=len(arr),
        win_rate=win_rate,
        avg_return=avg,
        median_return=median,
        max_drawdown=drawdown,
        sharpe=sharpe,
        sortino=sortino,
        profit_factor=profit_factor if profit_factor != float("inf") else 999.0,
        avg_hold_days=float(hold_days),
    )
