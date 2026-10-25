"""
Technical Indicators Engine for Algorithmic & AI Trading.
Pure Python/NumPy/Pandas implementation ensuring zero C-extension compile errors.
"""

from typing import Tuple, Dict, Any
import numpy as np
import pandas as pd


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Average True Range (ATR)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def calculate_macd(
    series: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates MACD Line, Signal Line, and Histogram."""
    fast_ema = calculate_ema(series, fast_period)
    slow_ema = calculate_ema(series, slow_period)
    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal_period)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def calculate_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculates Supertrend Indicator and Direction (1 for Bullish, -1 for Bearish).
    """
    atr = calculate_atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)

    supertrend = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)

    # Initialize
    supertrend.iloc[0] = lowerband.iloc[0]
    direction.iloc[0] = 1

    for i in range(1, len(close)):
        curr_close = close.iloc[i]
        curr_upper = upperband.iloc[i]
        curr_lower = lowerband.iloc[i]
        prev_st = supertrend.iloc[i - 1]
        prev_dir = direction.iloc[i - 1]

        if prev_dir == 1:
            if curr_close < prev_st:
                direction.iloc[i] = -1
                supertrend.iloc[i] = curr_upper
            else:
                direction.iloc[i] = 1
                supertrend.iloc[i] = max(curr_lower, prev_st)
        else:
            if curr_close > prev_st:
                direction.iloc[i] = 1
                supertrend.iloc[i] = curr_lower
            else:
                direction.iloc[i] = -1
                supertrend.iloc[i] = min(curr_upper, prev_st)

    return supertrend, direction


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculates Volume Weighted Average Price (VWAP)."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
    return vwap
