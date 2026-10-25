"""
Market Regime Detector.
Classifies current market state into 5 regimes:
  - TRENDING_BULL
  - TRENDING_BEAR
  - SIDEWAYS
  - HIGH_VOLATILITY
  - LOW_VOLATILITY
"""

from enum import Enum
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd


class MarketRegime(str, Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"


class MarketRegimeDetector:
    def __init__(
        self,
        ema_fast: int = 20,
        ema_slow: int = 50,
        atr_period: int = 14,
        lookback_bars: int = 50,
        trend_threshold_pct: float = 0.25
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.lookback_bars = lookback_bars
        self.trend_threshold_pct = trend_threshold_pct

    def detect_regime(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Classifies regime from OHLCV candle DataFrame.
        Required columns: 'open', 'high', 'low', 'close', 'volume'.
        """
        if df is None or len(df) < self.ema_slow:
            return {
                "regime": MarketRegime.UNKNOWN.value,
                "confidence": 0.50,
                "reason": "Insufficient candle data"
            }

        data = df.tail(self.lookback_bars).copy()

        # 1. EMAs
        close = data["close"]
        ema_f = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_s = close.ewm(span=self.ema_slow, adjust=False).mean()

        last_f = ema_f.iloc[-1]
        last_s = ema_s.iloc[-1]
        last_close = close.iloc[-1]

        diff_pct = ((last_f - last_s) / last_s) * 100.0

        # 2. True Range & ATR Volatility
        high = data["high"]
        low = data["low"]
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean().iloc[-1]
        atr_pct = (atr / last_close) * 100.0

        # 3. Decision Logic: Trend takes precedence if directional slope is clear
        if diff_pct > self.trend_threshold_pct and last_close > last_f:
            regime = MarketRegime.TRENDING_BULL
            reason = f"Clear bullish trend (Fast EMA +{diff_pct:.2f}% above Slow EMA)"
            conf = 0.85
        elif diff_pct < -self.trend_threshold_pct and last_close < last_f:
            regime = MarketRegime.TRENDING_BEAR
            reason = f"Clear bearish trend (Fast EMA {diff_pct:.2f}% below Slow EMA)"
            conf = 0.85
        elif atr_pct > 1.8:
            regime = MarketRegime.HIGH_VOLATILITY
            reason = f"Extreme volatility detected (ATR = {atr_pct:.2f}% of price)"
            conf = 0.80
        elif atr_pct < 0.35:
            regime = MarketRegime.LOW_VOLATILITY
            reason = f"Volatility compression / squeeze (ATR = {atr_pct:.2f}% of price)"
            conf = 0.75
        else:
            regime = MarketRegime.SIDEWAYS
            reason = f"Range-bound consolidation (EMA separation {diff_pct:.2f}%)"
            conf = 0.70

        return {
            "regime": regime.value,
            "confidence": conf,
            "atr_pct": round(atr_pct, 2),
            "ema_diff_pct": round(diff_pct, 2),
            "reason": reason
        }
