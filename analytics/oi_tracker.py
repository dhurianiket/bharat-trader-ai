"""
Open Interest (OI) & Options Flow Analysis Engine.
Detects Long Buildup, Short Buildup, Short Covering, and Long Unwinding regimes.
"""

from enum import Enum
from typing import Dict, Any, Tuple


class OIFlowRegime(str, Enum):
    LONG_BUILDUP = "LONG_BUILDUP"         # Price UP + OI UP (Strong Bullish)
    SHORT_BUILDUP = "SHORT_BUILDUP"       # Price DOWN + OI UP (Strong Bearish)
    SHORT_COVERING = "SHORT_COVERING"     # Price UP + OI DOWN (Short-term Relief Rally)
    LONG_UNWINDING = "LONG_UNWINDING"     # Price DOWN + OI DOWN (Weak Liquidation)
    NEUTRAL = "NEUTRAL"


def analyze_oi_flow(
    current_price: float,
    previous_price: float,
    current_oi: int,
    previous_oi: int,
    min_price_change_pct: float = 0.05,
    min_oi_change_pct: float = 1.0
) -> Dict[str, Any]:
    """
    Analyzes price & open interest momentum to determine the dominant institutional flow.
    """
    if previous_price <= 0 or previous_oi <= 0:
        return {
            "flow_regime": OIFlowRegime.NEUTRAL.value,
            "price_change_pct": 0.0,
            "oi_change_pct": 0.0,
            "signal_bias": "NEUTRAL"
        }

    price_diff_pct = ((current_price - previous_price) / previous_price) * 100.0
    oi_diff_pct = ((current_oi - previous_oi) / previous_oi) * 100.0

    is_price_up = price_diff_pct > min_price_change_pct
    is_price_down = price_diff_pct < -min_price_change_pct
    is_oi_up = oi_diff_pct > min_oi_change_pct
    is_oi_down = oi_diff_pct < -min_oi_change_pct

    if is_price_up and is_oi_up:
        flow = OIFlowRegime.LONG_BUILDUP
        bias = "STRONG_BULLISH"
    elif is_price_down and is_oi_up:
        flow = OIFlowRegime.SHORT_BUILDUP
        bias = "STRONG_BEARISH"
    elif is_price_up and is_oi_down:
        flow = OIFlowRegime.SHORT_COVERING
        bias = "MODERATE_BULLISH"
    elif is_price_down and is_oi_down:
        flow = OIFlowRegime.LONG_UNWINDING
        bias = "MODERATE_BEARISH"
    else:
        flow = OIFlowRegime.NEUTRAL
        bias = "NEUTRAL"

    return {
        "flow_regime": flow.value,
        "price_change_pct": round(price_diff_pct, 2),
        "oi_change_pct": round(oi_diff_pct, 2),
        "signal_bias": bias
    }
