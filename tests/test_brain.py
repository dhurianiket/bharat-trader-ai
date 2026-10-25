"""
Unit tests for AI Brain (Regime Detector, Indicators, Composite Scorer, RL Exit Agent).
"""

import pandas as pd
import numpy as np
import pytest

from brain.regime_detector import MarketRegimeDetector, MarketRegime
from brain.indicators import calculate_ema, calculate_rsi, calculate_atr, calculate_supertrend
from brain.composite_scorer import CompositeScorer
from brain.rl_exit_agent import RLExitAgent


def test_indicators():
    series = pd.Series([10, 11, 12, 13, 14, 15, 14, 13, 14, 15, 16, 17, 18, 19, 20])
    ema = calculate_ema(series, period=5)
    assert len(ema) == len(series)
    assert ema.iloc[-1] > 10

    rsi = calculate_rsi(series, period=5)
    assert len(rsi) == len(series)
    assert 0.0 <= rsi.iloc[-1] <= 100.0


def test_regime_detector():
    dates = pd.date_range("2026-10-25 09:15", periods=55, freq="5min")
    prices = 24000.0 + np.cumsum(np.full(55, 10.0))  # Consistent upward trend
    df = pd.DataFrame({
        "open": prices - 2,
        "high": prices + 5,
        "low": prices - 5,
        "close": prices,
        "volume": np.random.randint(1000, 50000, 55)
    }, index=dates)

    detector = MarketRegimeDetector(lookback_bars=50)
    result = detector.detect_regime(df)
    assert result["regime"] == MarketRegime.TRENDING_BULL.value
    assert result["confidence"] > 0.70


def test_composite_scorer():
    scorer = CompositeScorer()
    approved, score, details = scorer.calculate_score(
        action="BUY",
        tech_indicators={"rsi": 58.0, "supertrend_direction": 1, "ema_aligned": True},
        regime_info={"regime": "TRENDING_BULL"},
        flow_info={"flow_regime": "LONG_BUILDUP"}
    )
    assert approved is True
    assert score >= 0.85


def test_rl_exit_agent():
    agent = RLExitAgent()
    # Scenario: High profit that retraces -> Expect EXIT action
    state = {
        "unrealized_pnl_pct": 0.08,
        "peak_gain_pct": 0.20,
        "bars_held_norm": 0.40,
        "distance_to_sl": 0.15
    }
    action, reason = agent.decide(state)
    assert action == "EXIT"
    assert "Locking in profits" in reason
