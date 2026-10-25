"""
Upstox API v2 Broker Adapter.
Connects with Upstox for Indian stock and derivatives execution.
"""

import datetime
import logging
from typing import Dict, Any, List
from core.broker_base import BaseBrokerAdapter, OrderRequest, OrderResponse

logger = logging.getLogger("BrokerAdapter.Upstox")


class UpstoxAdapter(BaseBrokerAdapter):
    def __init__(self, config: Dict[str, Any], is_paper: bool = True):
        super().__init__(config, is_paper)
        self.api_key = config.get("api_key", "")
        self.access_token = config.get("access_token", "")
        self._paper_positions: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        if self.is_paper:
            logger.info("Upstox Adapter initialized in PAPER TRADING simulation mode.")
            return True

        if not self.access_token:
            logger.warning("Upstox access token missing. Defaulting to Paper Mode.")
            self.is_paper = True
            return True

        logger.info("Upstox adapter configured with OAuth access token.")
        return True

    def place_order(self, order: OrderRequest) -> OrderResponse:
        now_str = datetime.datetime.now().isoformat()
        if self.is_paper:
            sim_id = f"SIM_UPSTOX_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            self._paper_positions.append({
                "symbol": order.symbol,
                "action": order.action,
                "quantity": order.quantity,
                "price": order.price or 100.0,
                "order_id": sim_id,
                "timestamp": now_str
            })
            logger.info(f"[PAPER TRADING - UPSTOX] {order.action} {order.quantity}x {order.symbol} @ MARKET")
            return OrderResponse(
                success=True,
                order_id=sim_id,
                status="COMPLETE",
                message=f"Simulated execution for {order.symbol}",
                executed_price=order.price or 100.0,
                timestamp=now_str
            )

        try:
            import upstox_client
            configuration = upstox_client.Configuration()
            configuration.access_token = self.access_token
            api_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))

            body = upstox_client.PlaceOrderRequest(
                quantity=order.quantity,
                product="I" if order.product.upper() == "INTRADAY" else "D",
                validity="DAY",
                price=order.price or 0.0,
                tag=order.tag or "AI_AGENT",
                instrument_token=order.symbol,
                order_type="MARKET" if order.order_type.upper() == "MARKET" else "LIMIT",
                transaction_type=order.action.upper(),
                disclosed_quantity=0,
                trigger_price=0.0,
                is_amo=False
            )
            api_response = api_instance.place_order(body, "2.0")
            order_id = api_response.data.order_id if api_response.data else "UNKNOWN"
            return OrderResponse(
                success=True,
                order_id=str(order_id),
                status="SUBMITTED",
                message="Upstox order submitted successfully",
                timestamp=now_str
            )
        except Exception as e:
            logger.error(f"Upstox place_order failed: {e}")
            return OrderResponse(success=False, status="FAILED", message=str(e), timestamp=now_str)

    def cancel_order(self, order_id: str) -> bool:
        if self.is_paper:
            return True
        try:
            import upstox_client
            configuration = upstox_client.Configuration()
            configuration.access_token = self.access_token
            api_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
            api_instance.cancel_order(order_id, "2.0")
            return True
        except Exception as e:
            logger.error(f"Error cancelling Upstox order {order_id}: {e}")
            return False

    def get_positions(self) -> List[Dict[str, Any]]:
        if self.is_paper:
            return self._paper_positions
        try:
            import upstox_client
            configuration = upstox_client.Configuration()
            configuration.access_token = self.access_token
            portfolio_api = upstox_client.PortfolioApi(upstox_client.ApiClient(configuration))
            res = portfolio_api.get_positions("2.0")
            return res.data or []
        except Exception as e:
            logger.error(f"Error getting Upstox positions: {e}")
            return []

    def square_off_all(self) -> List[OrderResponse]:
        now_str = datetime.datetime.now().isoformat()
        results = []
        if self.is_paper:
            for pos in list(self._paper_positions):
                results.append(OrderResponse(
                    success=True,
                    order_id=f"SQ_OFF_{pos.get('order_id', 'SIM')}",
                    status="CLOSED",
                    message=f"Paper position closed for {pos.get('symbol')}",
                    timestamp=now_str
                ))
            self._paper_positions.clear()
            return results

        positions = self.get_positions()
        for pos in positions:
            qty = int(pos.quantity if hasattr(pos, "quantity") else pos.get("quantity", 0))
            if qty != 0:
                action = "SELL" if qty > 0 else "BUY"
                symbol = pos.tradingsymbol if hasattr(pos, "tradingsymbol") else pos.get("tradingsymbol", "")
                res = self.place_order(OrderRequest(
                    symbol=symbol,
                    action=action,
                    quantity=abs(qty),
                    order_type="MARKET",
                    product="INTRADAY",
                    tag="KILL_SWITCH"
                ))
                results.append(res)
        return results

    def get_account_balance(self) -> Dict[str, float]:
        if self.is_paper:
            return {"available_cash": 1000000.0, "used_margin": 0.0}
        try:
            import upstox_client
            configuration = upstox_client.Configuration()
            configuration.access_token = self.access_token
            user_api = upstox_client.UserApi(upstox_client.ApiClient(configuration))
            profile = user_api.get_user_fund_margin("2.0")
            equity = profile.data.equity if profile.data else None
            cash = float(equity.available_margin) if equity else 0.0
            used = float(equity.used_margin) if equity else 0.0
            return {"available_cash": cash, "used_margin": used}
        except Exception as e:
            logger.error(f"Error fetching Upstox balance: {e}")
            return {"available_cash": 0.0, "used_margin": 0.0}
