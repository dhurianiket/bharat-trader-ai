"""
AI Agent Sentinel & Market Regime Classifier.
Analyzes market conditions, trend alignment, and technical confirmation
to approve, veto, or adjust incoming trade signals.
"""

import logging
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("Brain.Sentinel")


class AgentSentinel:
    def __init__(self, confidence_threshold: float = 0.65):
        self.confidence_threshold = confidence_threshold

    def evaluate_signal_confidence(
        self,
        signal: Dict[str, Any],
        historical_candles: pd.DataFrame = None
    ) -> Tuple[bool, float, str]:
        """
        Evaluates incoming alert against market context and trend alignment.
        Returns: (is_approved: bool, confidence_score: float, reasoning: str)
        """
        action = signal.get("action", "").upper()
        symbol = signal.get("symbol", "")

        # If no candle dataframe is provided, perform heuristic evaluation
        if historical_candles is None or historical_candles.empty or len(historical_candles) < 20:
            logger.info(f"Insufficient tick/candle history for {symbol}. Bypassing deep AI filter with base confidence.")
            return True, 0.70, "Base confirmation passed; insufficient bar history for deep regime filter."

        try:
            # 1. Trend Filter: EMA 20 vs EMA 50
            close_prices = historical_candles["close"]
            ema20 = close_prices.ewm(span=20, adjust=False).mean().iloc[-1]
            ema50 = close_prices.ewm(span=50, adjust=False).mean().iloc[-1]
            current_price = close_prices.iloc[-1]

            # 2. Momentum Filter: RSI 14
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-9)
            rsi = 100 - (100 / (1 + rs)).iloc[-1]

            score = 0.50
            reasons = []

            if action == "BUY":
                if current_price > ema20 > ema50:
                    score += 0.25
                    reasons.append("Bullish EMA alignment (Price > EMA20 > EMA50)")
                elif current_price < ema50:
                    score -= 0.20
                    reasons.append("Counter-trend BUY (Price < EMA50)")

                if 45 <= rsi <= 70:
                    score += 0.15
                    reasons.append(f"Healthy RSI momentum ({rsi:.1f})")
                elif rsi > 78:
                    score -= 0.15
                    reasons.append(f"Overbought RSI warning ({rsi:.1f})")

            elif action == "SELL":
                if current_price < ema20 < ema50:
                    score += 0.25
                    reasons.append("Bearish EMA alignment (Price < EMA20 < EMA50)")
                elif current_price > ema50:
                    score -= 0.20
                    reasons.append("Counter-trend SELL (Price > EMA50)")

                if 30 <= rsi <= 55:
                    score += 0.15
                    reasons.append(f"Healthy bearish RSI momentum ({rsi:.1f})")
                elif rsi < 22:
                    score -= 0.15
                    reasons.append(f"Oversold RSI warning ({rsi:.1f})")

            final_score = float(np.clip(score, 0.0, 1.0))
            approved = final_score >= self.confidence_threshold
            reasoning = " | ".join(reasons) if reasons else "Neutral conditions"

            logger.info(f"AI Sentinel Evaluation for {symbol} {action}: Score={final_score:.2f}, Approved={approved} ({reasoning})")
            return approved, final_score, reasoning

        except Exception as e:
            logger.error(f"Error during AI sentinel evaluation: {e}")
            return True, 0.60, f"Error in calculation: {e}; defaulted to approval."
