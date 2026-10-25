"""
Broker Factory for BharatTrader-AI.
Instantiates the selected broker adapter based on system configuration.
"""

from typing import Dict, Any
from core.broker_base import BaseBrokerAdapter
from core.brokers.zerodha_adapter import ZerodhaAdapter
from core.brokers.dhan_adapter import DhanAdapter
from core.brokers.angel_one_adapter import AngelOneAdapter
from core.brokers.fyers_adapter import FyersAdapter
from core.brokers.upstox_adapter import UpstoxAdapter


def get_broker_adapter(config: Dict[str, Any]) -> BaseBrokerAdapter:
    env = config.get("app", {}).get("environment", "paper").lower()
    is_paper = (env == "paper")

    broker_cfg = config.get("brokers", {})
    active = broker_cfg.get("active_broker", "zerodha").lower()

    if active == "zerodha":
        return ZerodhaAdapter(broker_cfg.get("zerodha", {}), is_paper=is_paper)
    elif active == "dhan":
        return DhanAdapter(broker_cfg.get("dhan", {}), is_paper=is_paper)
    elif active == "angel_one" or active == "angel":
        return AngelOneAdapter(broker_cfg.get("angel_one", {}), is_paper=is_paper)
    elif active == "fyers":
        return FyersAdapter(broker_cfg.get("fyers", {}), is_paper=is_paper)
    elif active == "upstox":
        return UpstoxAdapter(broker_cfg.get("upstox", {}), is_paper=is_paper)
    else:
        # Default to simulated Zerodha adapter
        return ZerodhaAdapter({}, is_paper=True)
