"""
Unified FastAPI Trading Server for BharatTrader-AI.
Combines TradingView Webhooks, Risk Management, AI Sentinel,
Options Greeks Analytics, and Action Center execution control.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, status
from bridge.payload_models import TradingViewAlertPayload, GreeksRequestPayload
from bridge.action_center import ActionCenter
from core.broker_base import BaseBrokerAdapter, OrderRequest
from core.risk_engine import RiskEngine
from core.session_manager import IndianMarketSessionManager
from brain.composite_scorer import CompositeScorer
from analytics.black76_greeks import black76_greeks, calculate_implied_volatility
from analytics.max_pain import calculate_max_pain

logger = logging.getLogger("Bridge.WebhookServer")


def create_app(
    broker_adapter: BaseBrokerAdapter,
    risk_engine: RiskEngine,
    session_manager: IndianMarketSessionManager,
    composite_scorer: CompositeScorer,
    action_center: ActionCenter,
    configured_secret: str,
    enable_ai_sentinel: bool = True
) -> FastAPI:
    app = FastAPI(
        title="BharatTrader-AI Unified Trading Engine",
        description="Autonomous Multi-Broker Algorithmic & AI Trading Server for Indian Markets",
        version="2.0.0"
    )

    @app.get("/health")
    def health_check():
        balance = broker_adapter.get_account_balance()
        positions = broker_adapter.get_positions()
        ist_now = session_manager.get_current_ist_time()
        is_entry_ok, entry_msg = session_manager.is_entry_allowed()

        return {
            "system": "BharatTrader-AI",
            "status": "ONLINE",
            "environment": "PAPER" if broker_adapter.is_paper else "LIVE_EXCHANGE",
            "active_broker": broker_adapter.__class__.__name__,
            "current_ist_time": ist_now.strftime("%Y-%m-%d %H:%M:%S IST"),
            "market_open": session_manager.is_market_open(),
            "entry_status": entry_msg,
            "kill_switch_active": risk_engine.is_kill_switch_active,
            "cumulative_daily_loss_inr": risk_engine.cumulative_daily_loss,
            "total_trades_today": risk_engine.total_trades_today,
            "open_positions_count": len(positions),
            "account_balance": balance
        }

    @app.post("/webhook", response_model=Dict[str, Any])
    def handle_tradingview_alert(payload: TradingViewAlertPayload):
        # 1. Authenticate Secret Key
        if payload.secret_key != configured_secret:
            logger.warning(f"Unauthorized webhook attempt with secret: {payload.secret_key[:4]}****")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid secret key. Webhook rejected."
            )

        logger.info(f"Incoming TV Alert: {payload.action} {payload.quantity}x {payload.symbol} [{payload.strategy_name}]")

        # 2. Check Market Timing (Only in Live Mode)
        if not broker_adapter.is_paper:
            is_entry_ok, entry_reason = session_manager.is_entry_allowed()
            if not is_entry_ok and payload.action.upper() == "BUY":
                logger.warning(f"Trade blocked by Session Manager: {entry_reason}")
                return {"status": "BLOCKED_BY_SESSION_MANAGER", "reason": entry_reason}

        # 3. AI Sentinel & Composite Scoring Confirmation (if enabled)
        if enable_ai_sentinel:
            # Synthetic indicators payload if raw alert
            tech_indicators = {"rsi": 55.0, "supertrend_direction": 1 if payload.action.upper() == "BUY" else -1, "ema_aligned": True}
            regime_info = {"regime": "TRENDING_BULL" if payload.action.upper() == "BUY" else "TRENDING_BEAR"}
            flow_info = {"flow_regime": "LONG_BUILDUP" if payload.action.upper() == "BUY" else "SHORT_BUILDUP"}

            approved, score, score_details = composite_scorer.calculate_score(
                action=payload.action,
                tech_indicators=tech_indicators,
                regime_info=regime_info,
                flow_info=flow_info
            )
            if not approved:
                logger.warning(f"AI Sentinel VETOED trade: Composite Score {score} < Threshold {composite_scorer.threshold}")
                return {
                    "status": "VETOED_BY_AI_SENTINEL",
                    "score": score,
                    "details": score_details
                }

        # 4. Pre-Trade Risk Verification
        current_positions = broker_adapter.get_positions()
        balance_info = broker_adapter.get_account_balance()
        cash = balance_info.get("available_cash", 1000000.0)

        # Dynamic Sizing via Kelly if enabled
        final_qty = payload.quantity
        if risk_engine.use_kelly and payload.price:
            final_qty = risk_engine.calculate_kelly_quantity(
                account_equity=cash,
                share_price=payload.price,
                win_rate=0.55,
                risk_reward_ratio=1.5,
                lot_size=1
            )

        order_req = OrderRequest(
            symbol=payload.symbol,
            action=payload.action,
            quantity=final_qty,
            order_type=payload.order_type,
            price=payload.price,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
            product=payload.product,
            tag=payload.strategy_name
        )

        is_allowed, risk_reason = risk_engine.check_pre_trade_risk(
            order=order_req,
            current_open_positions_count=len(current_positions),
            account_balance=cash
        )

        if not is_allowed:
            logger.warning(f"Trade blocked by Risk Engine: {risk_reason}")
            return {"status": "BLOCKED_BY_RISK_ENGINE", "reason": risk_reason}

        # 5. Route via Action Center (Full-Auto vs Semi-Auto)
        result = action_center.handle_incoming_signal(order_req, broker_adapter, risk_engine)
        return result

    @app.post("/kill-switch")
    def execute_kill_switch(secret_key: str):
        if secret_key != configured_secret:
            raise HTTPException(status_code=401, detail="Unauthorized")

        risk_engine.trigger_manual_kill_switch()
        results = broker_adapter.square_off_all()
        return {
            "status": "KILL_SWITCH_EXECUTED",
            "message": f"Closed {len(results)} positions. Trading halted.",
            "closed_orders": [r.model_dump() for r in results]
        }

    @app.get("/action-center/pending")
    def get_pending_orders():
        return {"pending_orders": action_center.list_pending()}

    @app.post("/action-center/approve/{queue_id}")
    def approve_pending_order(queue_id: str, secret_key: str):
        if secret_key != configured_secret:
            raise HTTPException(status_code=401, detail="Unauthorized")

        res = action_center.approve_order(queue_id, broker_adapter)
        if not res:
            raise HTTPException(status_code=404, detail=f"Order {queue_id} not found in pending queue.")
        return {"status": "APPROVED", "result": res.model_dump()}

    @app.post("/analytics/greeks")
    def calculate_greeks(req: GreeksRequestPayload):
        vol = req.volatility
        if not vol and req.market_price:
            vol = calculate_implied_volatility(
                option_type=req.option_type,
                market_price=req.market_price,
                forward_price=req.forward_price,
                strike_price=req.strike_price,
                time_to_expiry_years=req.time_to_expiry_years,
                interest_rate=req.interest_rate
            )

        if not vol:
            vol = 0.20  # Fallback 20% volatility

        greeks = black76_greeks(
            option_type=req.option_type,
            forward_price=req.forward_price,
            strike_price=req.strike_price,
            time_to_expiry_years=req.time_to_expiry_years,
            interest_rate=req.interest_rate,
            volatility=vol
        )
        return {
            "option_type": req.option_type,
            "strike_price": req.strike_price,
            "implied_volatility_pct": round(vol * 100.0, 2),
            "greeks": greeks
        }

    @app.post("/analytics/max-pain")
    def get_max_pain(strikes_data: List[Dict[str, Any]]):
        return calculate_max_pain(strikes_data)

    return app
