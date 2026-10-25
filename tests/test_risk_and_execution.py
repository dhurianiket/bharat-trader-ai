"""
Unit tests for Risk Engine, Kelly Sizing, and Broker Order Execution.
"""

import pytest
from core.risk_engine import RiskEngine
from core.broker_base import OrderRequest
from core.brokers.zerodha_adapter import ZerodhaAdapter
from bridge.action_center import ActionCenter


def test_kelly_sizing():
    risk = RiskEngine({"max_capital_per_trade_percent": 5.0, "kelly_fraction": 0.5})
    qty = risk.calculate_kelly_quantity(
        account_equity=1000000.0,
        share_price=200.0,
        win_rate=0.60,
        risk_reward_ratio=1.5,
        lot_size=25
    )
    assert qty > 0
    assert qty % 25 == 0  # Multiple of lot size
    # Value must be capped at 5% of 1,000,000 = 50,000 / 200 = 250 shares
    assert qty <= 250


def test_risk_engine_circuit_breaker():
    risk = RiskEngine({"max_intraday_loss_inr": 5000.0})
    order = OrderRequest(
        symbol="NIFTY",
        action="BUY",
        quantity=25,
        price=100.0
    )

    # 1. Allowed initial order
    allowed, _ = risk.check_pre_trade_risk(order, 0, 100000.0)
    assert allowed is True

    # 2. Simulate loss breaching circuit breaker
    risk.record_trade_completion(-5500.0)
    assert risk.is_kill_switch_active is True

    # 3. Subsequent order must be blocked
    blocked, reason = risk.check_pre_trade_risk(order, 0, 100000.0)
    assert blocked is False
    assert "Kill-Switch" in reason or "Daily loss limit" in reason


def test_broker_paper_execution():
    broker = ZerodhaAdapter({}, is_paper=True)
    broker.connect()
    order = OrderRequest(
        symbol="NIFTY24OCT24500CE",
        action="BUY",
        quantity=25,
        order_type="MARKET",
        price=120.0
    )
    res = broker.place_order(order)
    assert res.success is True
    assert res.status == "COMPLETE"
    assert len(broker.get_positions()) == 1

    # Test kill-switch square-off
    results = broker.square_off_all()
    assert len(results) == 1
    assert len(broker.get_positions()) == 0
