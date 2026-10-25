"""
Multi-Factor Composite Trade Confidence Scorer.
Combines Technical momentum, Market Regime, and Institutional Options Flow.
"""

from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger("Brain.CompositeScorer")


class CompositeScorer:
    def __init__(
        self,
        weight_tech: float = 0.35,
        weight_regime: float = 0.35,
        weight_flow: float = 0.30,
        min_approval_threshold: float = 0.65
    ):
        self.w_tech = weight_tech
        self.w_regime = weight_regime
        self.w_flow = weight_flow
        self.threshold = min_approval_threshold

    def calculate_score(
        self,
        action: str,  # "BUY" or "SELL"
        tech_indicators: Dict[str, Any],
        regime_info: Dict[str, Any],
        flow_info: Dict[str, Any]
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Calculates normalized composite confidence score (0.0 to 1.0).
        """
        is_buy = action.upper() == "BUY"

        # 1. Technical Score (0.0 to 1.0)
        tech_score = 0.50
        rsi = float(tech_indicators.get("rsi", 50.0))
        st_dir = int(tech_indicators.get("supertrend_direction", 0))  # 1 or -1
        ema_aligned = bool(tech_indicators.get("ema_aligned", False))

        if is_buy:
            if st_dir == 1:
                tech_score += 0.20
            if ema_aligned:
                tech_score += 0.20
            if 50.0 <= rsi <= 72.0:
                tech_score += 0.10
            elif rsi > 78.0:
                tech_score -= 0.20  # Overbought penalty
        else:
            if st_dir == -1:
                tech_score += 0.20
            if ema_aligned:
                tech_score += 0.20
            if 28.0 <= rsi <= 50.0:
                tech_score += 0.10
            elif rsi < 22.0:
                tech_score -= 0.20  # Oversold penalty

        tech_score = max(0.0, min(1.0, tech_score))

        # 2. Market Regime Score (0.0 to 1.0)
        regime = regime_info.get("regime", "UNKNOWN")
        regime_score = 0.50

        if is_buy:
            if regime == "TRENDING_BULL":
                regime_score = 0.90
            elif regime == "LOW_VOLATILITY":
                regime_score = 0.65
            elif regime == "SIDEWAYS":
                regime_score = 0.40  # Penalty for range-bound chop
            elif regime == "TRENDING_BEAR":
                regime_score = 0.15  # Counter-trend penalty
        else:
            if regime == "TRENDING_BEAR":
                regime_score = 0.90
            elif regime == "LOW_VOLATILITY":
                regime_score = 0.65
            elif regime == "SIDEWAYS":
                regime_score = 0.40
            elif regime == "TRENDING_BULL":
                regime_score = 0.15

        # 3. Institutional Flow Score (0.0 to 1.0)
        flow_regime = flow_info.get("flow_regime", "NEUTRAL")
        flow_score = 0.50

        if is_buy:
            if flow_regime == "LONG_BUILDUP":
                flow_score = 0.95
            elif flow_regime == "SHORT_COVERING":
                flow_score = 0.70
            elif flow_regime == "SHORT_BUILDUP":
                flow_score = 0.10
        else:
            if flow_regime == "SHORT_BUILDUP":
                flow_score = 0.95
            elif flow_regime == "LONG_UNWINDING":
                flow_score = 0.70
            elif flow_regime == "LONG_BUILDUP":
                flow_score = 0.10

        # Composite Calculation
        composite = (
            (self.w_tech * tech_score) +
            (self.w_regime * regime_score) +
            (self.w_flow * flow_score)
        )
        composite = round(max(0.0, min(1.0, composite)), 3)
        approved = composite >= self.threshold

        details = {
            "composite_score": composite,
            "approved": approved,
            "threshold": self.threshold,
            "subscores": {
                "technical": round(tech_score, 2),
                "regime": round(regime_score, 2),
                "flow": round(flow_score, 2)
            }
        }
        return approved, composite, details
