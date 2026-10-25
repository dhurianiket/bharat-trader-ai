"""
End-to-End Automated Integration Test Suite for BharatTrader-AI.
Tests the complete pipeline:
  1. Health & Telemetry Endpoint
  2. TradingView Webhook Authentication (Valid vs Unauthorized)
  3. Full-Auto Trade Execution & Broker Position Updates
  4. AI Sentinel & Composite Scoring Confirmation / Vetoing
  5. Pre-Trade Risk Engine Guardrails (Sizing & Loss Limits)
  6. Action Center Semi-Auto Approval Queue Flow
  7. Options Analytics API (Black-76 Greeks & Max Pain)
  8. Emergency Kill-Switch & Position Liquidation
"""

import pytest
from fastapi.testclient import TestClient

from core.brokers.zerodha_adapter import ZerodhaAdapter
from core.risk_engine import RiskEngine
from core.session_manager import IndianMarketSessionManager
from brain.composite_scorer import CompositeScorer
from bridge.action_center import ActionCenter
from bridge.webhook_server import create_app


@pytest.fixture
def test_setup():
    secret_key = "TEST_SECRET_KEY_123"
    broker = ZerodhaAdapter({}, is_paper=True)
    broker.connect()

    risk_engine = RiskEngine({
        "max_intraday_loss_inr": 5000.0,
        "max_capital_per_trade_percent": 10.0,
        "max_open_positions": 3,
        "max_trades_per_day": 10,
        "use_kelly_sizing": False
    })

    session_manager = IndianMarketSessionManager(
        market_open_time="00:00",  # Open all day for automated testing
        market_close_time="23:59",
        square_off_time="23:50",
        no_fresh_entries_after="23:45"
    )

    composite_scorer = CompositeScorer(min_approval_threshold=0.60)
    action_center = ActionCenter(execution_mode="full_auto")

    app = create_app(
        broker_adapter=broker,
        risk_engine=risk_engine,
        session_manager=session_manager,
        composite_scorer=composite_scorer,
        action_center=action_center,
        configured_secret=secret_key,
        enable_ai_sentinel=True
    )

    client = TestClient(app)
    return {
        "client": client,
        "secret": secret_key,
        "broker": broker,
        "risk": risk_engine,
        "action_center": action_center
    }


def test_health_endpoint(test_setup):
    client = test_setup["client"]
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ONLINE"
    assert data["environment"] == "PAPER"
    assert data["active_broker"] == "ZerodhaAdapter"
    assert "account_balance" in data


def test_webhook_unauthorized(test_setup):
    client = test_setup["client"]
    payload = {
        "secret_key": "WRONG_SECRET",
        "symbol": "NIFTY24OCT24500CE",
        "action": "BUY",
        "quantity": 25,
        "order_type": "MARKET"
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 401
    assert "Invalid secret key" in resp.json()["detail"]


def test_webhook_full_auto_execution(test_setup):
    client = test_setup["client"]
    broker = test_setup["broker"]
    secret = test_setup["secret"]

    payload = {
        "secret_key": secret,
        "symbol": "NIFTY24OCT24500CE",
        "action": "BUY",
        "quantity": 25,
        "order_type": "MARKET",
        "price": 140.0,
        "stop_loss": 115.0,
        "take_profit": 190.0,
        "product": "INTRADAY",
        "strategy_name": "Test_FullAuto_CE"
    }

    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "EXECUTED"
    assert data["mode"] == "full_auto"
    assert "order_id" in data

    # Verify broker recorded the open position
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "NIFTY24OCT24500CE"


def test_webhook_risk_sizing_rejection(test_setup):
    client = test_setup["client"]
    secret = test_setup["secret"]

    # Huge order that violates max capital per trade limit (10% of 1,000,000 = 100,000)
    # 1000 shares * 25000 = 25,000,000 >> 100,000
    payload = {
        "secret_key": secret,
        "symbol": "NIFTY_FUT",
        "action": "BUY",
        "quantity": 1000,
        "order_type": "MARKET",
        "price": 25000.0,
        "product": "INTRADAY"
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "BLOCKED_BY_RISK_ENGINE"
    assert "exceeds allowed risk allocation" in data["reason"]


def test_semi_auto_approval_flow(test_setup):
    client = test_setup["client"]
    action_center = test_setup["action_center"]
    secret = test_setup["secret"]

    # Switch Action Center to Semi-Auto mode
    action_center.execution_mode = "semi_auto"

    payload = {
        "secret_key": secret,
        "symbol": "BANKNIFTY24OCT51000PE",
        "action": "BUY",
        "quantity": 15,
        "order_type": "MARKET",
        "price": 220.0,
        "product": "INTRADAY",
        "strategy_name": "SemiAuto_PE_Signal"
    }

    # Step 1: Webhook arrives and is held in Action Center
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "QUEUED_FOR_APPROVAL"
    queue_id = data["queue_id"]

    # Step 2: Query pending orders in Action Center
    pending_resp = client.get("/action-center/pending")
    assert pending_resp.status_code == 200
    pending_list = pending_resp.json()["pending_orders"]
    assert any(item["queue_id"] == queue_id for item in pending_list)

    # Step 3: Approve the queued order
    approve_resp = client.post(f"/action-center/approve/{queue_id}?secret_key={secret}")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"


def test_analytics_api_endpoints(test_setup):
    client = test_setup["client"]

    # Test /analytics/greeks
    greeks_req = {
        "option_type": "CE",
        "forward_price": 24500.0,
        "strike_price": 24500.0,
        "time_to_expiry_years": 0.02,
        "interest_rate": 0.07,
        "market_price": 135.0
    }
    resp = client.post("/analytics/greeks", json=greeks_req)
    assert resp.status_code == 200
    data = resp.json()
    assert "implied_volatility_pct" in data
    assert 0.40 <= data["greeks"]["delta"] <= 0.60
    assert data["greeks"]["theta"] < 0

    # Test /analytics/max-pain
    chain_data = [
        {"strike": 24400, "ce_oi": 50000, "pe_oi": 90000},
        {"strike": 24500, "ce_oi": 150000, "pe_oi": 160000},
        {"strike": 24600, "ce_oi": 110000, "pe_oi": 40000}
    ]
    mp_resp = client.post("/analytics/max-pain", json=chain_data)
    assert mp_resp.status_code == 200
    mp_data = mp_resp.json()
    assert mp_data["max_pain_strike"] == 24500
    assert mp_data["put_call_ratio"] > 0


def test_kill_switch_liquidation(test_setup):
    client = test_setup["client"]
    broker = test_setup["broker"]
    secret = test_setup["secret"]

    # Place a trade first
    client.post("/webhook", json={
        "secret_key": secret,
        "symbol": "RELIANCE",
        "action": "BUY",
        "quantity": 10,
        "order_type": "MARKET",
        "product": "INTRADAY"
    })
    assert len(broker.get_positions()) > 0

    # Fire Kill Switch
    resp = client.post(f"/kill-switch?secret_key={secret}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "KILL_SWITCH_EXECUTED"

    # All positions must now be zero
    assert len(broker.get_positions()) == 0


def test_market_data_endpoints(test_setup):
    """Verifies free Google Finance-grade company analysis and search endpoints."""
    client = test_setup["client"]

    # 1. Company Profile
    resp = client.get("/api/market/company/TCS")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_price" in data
    assert "company_name" in data
    assert "pe_ratio" in data
    assert "market_cap" in data
    assert data["current_price"] > 0

    # 2. Symbol Search
    search_resp = client.get("/api/market/search?q=Tata")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert "results" in search_data
    assert len(search_data["results"]) > 0

    # 3. Historical Bars
    hist_resp = client.get("/api/market/history/TCS?period=5d&interval=1d")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert "bars" in hist_data
    assert len(hist_data["bars"]) > 0

    # 4. Watchlist
    watch_resp = client.get("/api/market/watchlist")
    assert watch_resp.status_code == 200
    watch_data = watch_resp.json()
    assert "watchlist" in watch_data
    assert len(watch_data["watchlist"]) > 0

    # 5. Google Finance Direct & SerpApi Payloads
    gf_resp = client.get("/api/market/google-finance/TCS")
    assert gf_resp.status_code == 200
    assert "google_finance_symbol" in gf_resp.json()

    serp_resp = client.get("/api/market/serpapi/TCS")
    assert serp_resp.status_code == 200
    serp_data = serp_resp.json()
    assert "search_metadata" in serp_data
    assert "summary" in serp_data
    assert "knowledge_graph" in serp_data

    # 6. Financials & Earnings Tabs
    fin_resp = client.get("/api/market/financials/TCS")
    assert fin_resp.status_code == 200
    assert "annual_revenue" in fin_resp.json()

    earn_resp = client.get("/api/market/earnings/TCS")
    assert earn_resp.status_code == 200
    assert "quarters" in earn_resp.json()

    # 7. Tools Status
    tools_resp = client.get("/api/market/tools-status")
    assert tools_resp.status_code == 200
    assert "free_apis" in tools_resp.json()

