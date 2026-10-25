"""
BharatTrader-AI: Master Orchestrator.
Unified Indian AI Live & Intraday Trading Engine.
"""

import os
import sys
import yaml
import logging
import argparse

from core.brokers import get_broker_adapter
from core.risk_engine import RiskEngine
from core.session_manager import IndianMarketSessionManager
from brain.composite_scorer import CompositeScorer
from brain.regime_detector import MarketRegimeDetector
from brain.rl_exit_agent import RLExitAgent
from bridge.action_center import ActionCenter
from bridge.webhook_server import create_app
from analytics.black76_greeks import black76_greeks, calculate_implied_volatility
from analytics.max_pain import calculate_max_pain

# Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("BharatTrader.Main")


def load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        logger.error(f"Config path {path} does not exist.")
        sys.exit(1)
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="BharatTrader-AI Unified Trading Engine")
    parser.add_argument("--config", default="config/config.yaml", help="Path to master config.yaml")
    parser.add_argument("--test-signal", action="store_true", help="Simulate a test order execution")
    parser.add_argument("--test-greeks", action="store_true", help="Verify Black-76 options Greeks calculations")
    parser.add_argument("--test-regime", action="store_true", help="Verify market regime detector")
    args = parser.parse_args()

    config = load_yaml(args.config)
    app_cfg = config.get("app", {})
    risk_cfg = config.get("risk", {})
    session_cfg = config.get("session", {})
    brain_cfg = config.get("brain", {})

    logger.info("=================================================================")
    logger.info("     BHARAT-TRADER AI: UNIFIED INDIAN LIVE TRADING ENGINE        ")
    logger.info(f"     Environment: {app_cfg.get('environment', 'paper').upper()} TRADING")
    logger.info(f"     Active Broker: {config.get('brokers', {}).get('active_broker', 'zerodha').upper()}")
    logger.info(f"     Execution Mode: {app_cfg.get('execution_mode', 'full_auto').upper()}")
    logger.info("=================================================================")

    # 1. Initialize Subsystems
    broker = get_broker_adapter(config)
    broker.connect()

    risk_engine = RiskEngine(risk_cfg)
    session_manager = IndianMarketSessionManager(
        market_open_time=session_cfg.get("market_open_time", "09:15"),
        market_close_time=session_cfg.get("market_close_time", "15:30"),
        square_off_time=session_cfg.get("intraday_square_off_time", "15:15"),
        no_fresh_entries_after=session_cfg.get("no_fresh_entries_after", "15:00")
    )
    weights = brain_cfg.get("weights", {})
    composite_scorer = CompositeScorer(
        weight_tech=weights.get("technical", 0.35),
        weight_regime=weights.get("market_regime", 0.35),
        weight_flow=weights.get("options_flow", 0.30),
        min_approval_threshold=brain_cfg.get("confidence_threshold", 0.65)
    )
    action_center = ActionCenter(execution_mode=app_cfg.get("execution_mode", "full_auto"))

    # Test Mode 1: Greeks Verification
    if args.test_greeks:
        logger.info("Testing Black-76 Greeks for NIFTY 24500 CE...")
        greeks = black76_greeks(
            option_type="CE",
            forward_price=24520.0,
            strike_price=24500.0,
            time_to_expiry_years=4.0 / 365.0,  # 4 days to weekly expiry
            interest_rate=0.07,
            volatility=0.14
        )
        logger.info(f"Computed Greeks: {greeks}")
        iv = calculate_implied_volatility(
            option_type="CE",
            market_price=125.0,
            forward_price=24520.0,
            strike_price=24500.0,
            time_to_expiry_years=4.0 / 365.0
        )
        logger.info(f"Computed Implied Volatility (IV): {iv * 100.0:.2f}%")
        return

    # Test Mode 2: Regime Detector
    if args.test_regime:
        logger.info("Testing Market Regime Detector...")
        import pandas as pd
        import numpy as np

        # Generate synthetic trending data
        dates = pd.date_range("2026-10-25 09:15", periods=60, freq="5min")
        prices = 24000.0 + np.cumsum(np.random.normal(5, 10, 60))
        df = pd.DataFrame({
            "open": prices - 2,
            "high": prices + 8,
            "low": prices - 6,
            "close": prices,
            "volume": np.random.randint(1000, 50000, 60)
        }, index=dates)

        detector = MarketRegimeDetector()
        res = detector.detect_regime(df)
        logger.info(f"Detected Regime: {res['regime']} (Confidence: {res['confidence']}) - {res['reason']}")
        return

    # Test Mode 3: Signal Order Execution
    if args.test_signal:
        logger.info("Testing simulated TradingView webhook signal...")
        from core.broker_base import OrderRequest
        order = OrderRequest(
            symbol="NIFTY24OCT24500CE",
            action="BUY",
            quantity=25,  # 1 lot of NIFTY
            order_type="MARKET",
            price=145.0,
            stop_loss=120.0,
            take_profit=190.0,
            product="INTRADAY",
            tag="TEST_TV_SIGNAL"
        )
        allowed, reason = risk_engine.check_pre_trade_risk(order, 0, 1000000.0)
        logger.info(f"Pre-Trade Risk Verification: Allowed={allowed} ({reason})")
        if allowed:
            result = action_center.handle_incoming_signal(order, broker, risk_engine)
            logger.info(f"Execution Output: {result}")
        return

    # Normal Mode: Launch FastAPI Server
    import uvicorn
    app = create_app(
        broker_adapter=broker,
        risk_engine=risk_engine,
        session_manager=session_manager,
        composite_scorer=composite_scorer,
        action_center=action_center,
        configured_secret=app_cfg.get("webhook_secret_key", "SECRET"),
        enable_ai_sentinel=app_cfg.get("enable_ai_sentinel", True)
    )

    host = app_cfg.get("server_host", "0.0.0.0")
    port = app_cfg.get("server_port", 8000)
    logger.info(f"Starting BharatTrader-AI Webhook Listener on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
