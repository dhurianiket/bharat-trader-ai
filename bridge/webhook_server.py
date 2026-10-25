"""
Unified FastAPI Trading Server for BharatTrader-AI.
Combines TradingView Webhooks, Risk Management, AI Sentinel,
Options Greeks Analytics, Action Center, Agent Monies (Virtual Capital),
and serves the Institutional Web Trading Terminal Dashboard.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from bridge.payload_models import TradingViewAlertPayload, GreeksRequestPayload
from bridge.action_center import ActionCenter
from core.broker_base import BaseBrokerAdapter, OrderRequest
from core.risk_engine import RiskEngine
from core.session_manager import IndianMarketSessionManager
from brain.composite_scorer import CompositeScorer
from analytics.black76_greeks import black76_greeks, calculate_implied_volatility
from analytics.max_pain import calculate_max_pain
from analytics.market_data import MarketDataService

logger = logging.getLogger("Bridge.WebhookServer")


class DepositFundsRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in INR to deposit to agent virtual capital")
    secret_key: Optional[str] = Field(None, description="Optional authentication key")


class ResetFundsRequest(BaseModel):
    amount: float = Field(1000000.0, ge=0, description="Amount in INR to reset agent virtual capital to")
    secret_key: Optional[str] = Field(None, description="Optional authentication key")


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

    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")

    # -------------------------------------------------------------
    # WEB DASHBOARD ENDPOINTS
    # -------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    def serve_dashboard():
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse("<h2>BharatTrader-AI Dashboard Template Not Found</h2>", status_code=404)

    # -------------------------------------------------------------
    # SYSTEM TELEMETRY & HEALTH
    # -------------------------------------------------------------
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

    # -------------------------------------------------------------
    # AGENT MONIES (VIRTUAL DEMO CAPITAL MANAGEMENT)
    # -------------------------------------------------------------
    @app.post("/agent/funds/deposit")
    def deposit_virtual_funds(req: DepositFundsRequest):
        new_balance = broker_adapter.deposit_virtual_funds(req.amount)
        return {
            "status": "SUCCESS",
            "message": f"Successfully deposited ₹{req.amount:,.2f} to Agent Virtual Capital.",
            "deposited_amount": req.amount,
            "new_balance": new_balance
        }

    @app.post("/agent/funds/reset")
    def reset_virtual_funds(req: ResetFundsRequest):
        new_balance = broker_adapter.reset_virtual_funds(req.amount)
        return {
            "status": "SUCCESS",
            "message": f"Agent Virtual Capital reset to ₹{req.amount:,.2f}.",
            "new_balance": new_balance
        }

    @app.get("/agent/positions")
    def get_agent_positions():
        return {"positions": broker_adapter.get_positions()}

    @app.post("/agent/positions/close/{order_id}")
    def close_single_position(order_id: str, secret_key: Optional[str] = None):
        positions = broker_adapter.get_positions()
        target_pos = None
        for p in positions:
            if str(p.get("order_id")) == str(order_id) or str(positions.index(p)) == str(order_id):
                target_pos = p
                break

        if not target_pos:
            # Fallback close first position
            if positions:
                target_pos = positions[0]

        if target_pos:
            qty = abs(int(target_pos.get("quantity", target_pos.get("netQty", 1))))
            action = "SELL" if target_pos.get("action") == "BUY" else "BUY"
            symbol = target_pos.get("symbol", target_pos.get("tradingsymbol", ""))
            res = broker_adapter.place_order(OrderRequest(
                symbol=symbol,
                action=action,
                quantity=qty,
                order_type="MARKET",
                product="INTRADAY",
                tag="MANUAL_SQUARE_OFF"
            ))
            # Remove from paper positions if in paper mode
            if broker_adapter.is_paper and target_pos in broker_adapter._paper_positions:
                broker_adapter._paper_positions.remove(target_pos)
            return {"status": "SUCCESS", "result": res.model_dump()}

        return {"status": "NOT_FOUND", "message": f"Position {order_id} not found."}

    # -------------------------------------------------------------
    # TRADINGVIEW WEBHOOK INGESTION
    # -------------------------------------------------------------
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

    # -------------------------------------------------------------
    # PANIC EMERGENCY KILL-SWITCH
    # -------------------------------------------------------------
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

    # -------------------------------------------------------------
    # ACTION CENTER (SEMI-AUTO APPROVAL QUEUE)
    # -------------------------------------------------------------
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

    # -------------------------------------------------------------
    # OPTIONS ANALYTICS (GREEKS & MAX PAIN)
    # -------------------------------------------------------------
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
            vol = 0.20

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

    # -------------------------------------------------------------
    # GOOGLE FINANCE-GRADE MARKET INTELLIGENCE (FREE OPEN APIS)
    # -------------------------------------------------------------
    market_data_service = MarketDataService(cache_ttl_seconds=60)

    @app.get("/api/market/company/{symbol}")
    def get_company_analysis(symbol: str):
        """
        Returns full Google Finance-style fundamentals, technical metrics,
        and company intelligence for any Indian or Global asset.
        """
        return market_data_service.get_company_profile(symbol)

    @app.get("/api/market/google-finance/{symbol}")
    def get_google_finance_live_quote(symbol: str):
        """
        Direct parser extracting live quote and status directly from Google Finance page.
        """
        live_data = market_data_service.fetch_google_finance_live(symbol)
        if live_data:
            return live_data
        # Resilient fallback to profile data
        prof = market_data_service.get_company_profile(symbol)
        gf_sym = market_data_service.resolve_google_finance_symbol(symbol)
        return {
            "google_finance_symbol": gf_sym,
            "google_finance_url": f"https://www.google.com/finance/quote/{gf_sym}",
            "company_name": prof.get("company_name", symbol),
            "currency_symbol": prof.get("currency_symbol", "₹"),
            "current_price": prof.get("current_price", 0.0),
            "change": prof.get("change", 0.0),
            "change_percent": prof.get("change_percent", 0.0),
            "is_positive": prof.get("is_positive", True),
            "description": prof.get("description", ""),
            "data_source": "Google Finance Direct / Hybrid Feed"
        }

    @app.get("/api/market/serpapi/{symbol}")
    def get_serpapi_live_payload(symbol: str, api_key: Optional[str] = None):
        """
        Returns structured SerpApi JSON payload matching the SerpApi Google Finance API playground.
        """
        return market_data_service.get_serpapi_payload(symbol, api_key=api_key)

    @app.post("/api/market/serpapi-key")
    def set_serpapi_key(payload: Dict[str, str]):
        """
        Configures SerpApi API key for live SerpApi search queries.
        """
        key = payload.get("api_key", "").strip()
        market_data_service.serpapi_api_key = key
        return {"status": "SUCCESS", "configured": bool(key)}

    @app.get("/api/market/financials/{symbol}")
    def get_company_financials(symbol: str):
        """
        Returns quarterly and annual financials (Revenue, Net Income, Margins, Cash Flow).
        """
        return market_data_service.get_company_financials(symbol)

    @app.get("/api/market/earnings/{symbol}")
    def get_company_earnings(symbol: str):
        """
        Returns quarterly EPS estimates, actuals, surprises, and next earnings dates.
        """
        return market_data_service.get_company_earnings(symbol)

    @app.get("/api/market/history/{symbol}")
    def get_company_historical_bars(symbol: str, period: str = "1mo", interval: str = "1d"):
        """
        Returns historical OHLCV candles/bars for charting across timeframes
        (1d, 5d, 1mo, 6mo, 1y, 5y).
        """
        return market_data_service.get_historical_ohlcv(symbol, period=period, interval=interval)

    @app.get("/api/market/search")
    def search_market_symbols(q: str = ""):
        """
        Searches symbols across NSE, BSE, and global exchanges using open autocomplete.
        """
        return {"query": q, "results": market_data_service.search_symbols(q)}

    @app.get("/api/market/watchlist")
    def get_live_market_watchlist():
        """
        Returns live prices and daily performance for top index & equity heavyweights.
        """
        return {"watchlist": market_data_service.get_watchlist_summary()}

    @app.get("/api/market/ticks")
    def get_market_ticks():
        """
        REST endpoint returning immediate live ticks snapshot.
        """
        return market_data_service.get_live_ticks()

    @app.get("/api/market/tools-status")
    def get_tools_and_apis_status():
        """
        Returns telemetry on all required tools, public APIs, and streaming protocols.
        """
        return market_data_service.get_tools_spec()

    @app.get("/api/stream/live-ticks")
    async def stream_live_ticks():
        """
        Server-Sent Events (SSE) stream pushing sub-second live price updates
        and uptick/downtick directional telemetry.
        """
        async def event_generator():
            while True:
                ticks_payload = market_data_service.get_live_ticks()
                yield f"data: {json.dumps(ticks_payload)}\n\n"
                await asyncio.sleep(1.0)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    return app
