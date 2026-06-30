"""Technical indicators computed from a daily OHLCV DataFrame.

Pure pandas/numpy — no TA-Lib build dependency required. Each function is
None-safe and returns floats (or None when there isn't enough history), so the
scoring layer never has to special-case short series.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _closes(hist: pd.DataFrame) -> pd.Series:
    return hist["Close"].dropna() if "Close" in hist else pd.Series(dtype=float)


def ema(hist: pd.DataFrame, span: int) -> float | None:
    closes = _closes(hist)
    if len(closes) < span:
        return None
    return float(closes.ewm(span=span, adjust=False).mean().iloc[-1])


def sma(hist: pd.DataFrame, window: int) -> float | None:
    closes = _closes(hist)
    if len(closes) < window:
        return None
    return float(closes.tail(window).mean())


def rsi(hist: pd.DataFrame, period: int = 14) -> float | None:
    closes = _closes(hist)
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def macd(hist: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd_line, signal_line, histogram) or (None, None, None)."""
    closes = _closes(hist)
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist_val = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(hist_val.iloc[-1])


def atr(hist: pd.DataFrame, period: int = 14) -> float | None:
    if not {"High", "Low", "Close"}.issubset(hist.columns) or len(hist) < period + 1:
        return None
    high, low, close = hist["High"], hist["Low"], hist["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return float(tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


def avg_volume(hist: pd.DataFrame, window: int = 20) -> float | None:
    if "Volume" not in hist or len(hist) < window:
        return None
    return float(hist["Volume"].tail(window).mean())


def volume_ratio(hist: pd.DataFrame, window: int = 20) -> float | None:
    """Latest session volume relative to its trailing average (1.5 = +50%)."""
    av = avg_volume(hist, window)
    if av is None or av == 0 or "Volume" not in hist:
        return None
    return float(hist["Volume"].iloc[-1] / av)


def pct_return(hist: pd.DataFrame, lookback: int) -> float | None:
    """Percent change over ``lookback`` trading sessions."""
    closes = _closes(hist)
    if len(closes) < lookback + 1:
        return None
    past = closes.iloc[-(lookback + 1)]
    if past == 0:
        return None
    return float((closes.iloc[-1] - past) / past * 100.0)


def above_ema(hist: pd.DataFrame, span: int = 200) -> bool | None:
    e = ema(hist, span)
    closes = _closes(hist)
    if e is None or not len(closes):
        return None
    return bool(closes.iloc[-1] > e)


def distance_from_52w_high(hist: pd.DataFrame) -> float | None:
    closes = _closes(hist).tail(252)
    if not len(closes):
        return None
    hi = closes.max()
    if hi == 0:
        return None
    return float((closes.iloc[-1] - hi) / hi * 100.0)


def golden_cross(hist: pd.DataFrame) -> bool | None:
    """50-day SMA above 200-day SMA (bullish regime)."""
    s50, s200 = sma(hist, 50), sma(hist, 200)
    if s50 is None or s200 is None:
        return None
    return bool(s50 > s200)


def indicator_bundle(hist: pd.DataFrame) -> dict:
    """All indicators the scanner + scoring layers consume, computed once."""
    macd_line, signal_line, macd_hist = macd(hist)
    return {
        "rsi": rsi(hist),
        "ema9": ema(hist, 9),
        "ema20": ema(hist, 20),
        "ema50": ema(hist, 50),
        "ema200": ema(hist, 200),
        "above_ema200": above_ema(hist, 200),
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": macd_hist,
        "atr": atr(hist),
        "avg_volume_20": avg_volume(hist, 20),
        "volume_ratio": volume_ratio(hist),
        "ret_1d": pct_return(hist, 1),
        "ret_5d": pct_return(hist, 5),
        "ret_20d": pct_return(hist, 20),
        "ret_60d": pct_return(hist, 60),
        "ret_120d": pct_return(hist, 120),
        "ret_252d": pct_return(hist, 252),
        "dist_52w_high": distance_from_52w_high(hist),
        "golden_cross": golden_cross(hist),
    }
