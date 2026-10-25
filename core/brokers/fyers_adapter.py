"""
Fyers API v3 Broker Adapter.
Connects with Fyers for Indian cash and derivatives execution.
"""

import datetime
import logging
from typing import Dict, Any, List
from core.broker_base import BaseBrokerAdapter, OrderRequest, OrderResponse

logger = logging.getLogger("BrokerAdapter.Fyers")


class FyersAdapter(BaseBrokerAdapter):
    def __init__(self, config: Dict[str, Any], is_paper: bool = True):
        super().__init__(config, is_paper)
        self.app_id = config.get("app_id", "")
        self.access_token = config.get("access_token", "")
        self.fyers_model = None
        self._paper_positions: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        if self.is_paper:
            logger.info("Fyers Adapter initialized in PAPER TRADING simulation mode.")
            return True

        if not self.app_id or not self.access_token:
            logger.warning("Fyers credentials missing. Defaulting to Paper Mode.")
            self.is_paper = True
            return True

        try:
            from fyers_apiv3 import fyersModel
            self.fyers_model = fyersModel.FyersModel(
                client_id=self.app_id,
                token=self.access_token,
                is_async=False,
                log_path=""
            )
            profile = self.fyers_model.get_profile()
            if profile.get("s") == "ok":
                logger.info(f"Fyers API connected for user {profile.get('data', {}).get('name')}")
                return True
            else:
                logger.error(f"Fyers connection failed: {profile.get('message')}. Defaulting to Paper.")
                self.is_paper = True
                return False
        except Exception as e:
            logger.error(f"Error initializing Fyers API: {e}. Defaulting to Paper.")
            self.is_paper = True
            return False

    def place_order(self, order: OrderRequest) -> OrderResponse:
        now_str = datetime.datetime.now().isoformat()
        if self.is_paper or not self.fyers_model:
            sim_id = f"SIM_FYERS_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            self._paper_positions.append({
                "symbol": order.symbol,
                "action": order.action,
                "quantity": order.quantity,
                "price": order.price or 100.0,
                "order_id": sim_id,
                "timestamp": now_str
            })
            logger.info(f"[PAPER TRADING - FYERS] {order.action} {order.quantity}x {order.symbol} @ MARKET")
            return OrderResponse(
                success=True,
                order_id=sim_id,
                status="COMPLETE",
                message=f"Simulated execution for {order.symbol}",
                executed_price=order.price or 100.0,
                timestamp=now_str
            )

        try:
            side = 1 if order.action.upper() == "BUY" else -1
            order_type = 2 if order.order_type.upper() == "MARKET" else 1
            product = "INTRADAY" if order.product.upper() == "INTRADAY" else "CNC"

            data = {
                "symbol": order.symbol,
                "qty": order.quantity,
                "type": order_type,
                "side": side,
                "productType": product,
                "limitPrice": order.price or 0.0,
                "stopPrice": order.stop_loss or 0.0,
                "validity": "DAY"
            }
            res = self.fyers_model.place_order(data=data)
            return OrderResponse(
                success=(res.get("s") == "ok"),
                order_id=str(res.get("id", "")),
                status=res.get("s", "FAILED"),
                message=res.get("message", "Fyers order response"),
                timestamp=now_str
            )
        except Exception as e:
            logger.error(f"Fyers place_order error: {e}")
            return OrderResponse(success=False, status="FAILED", message=str(e), timestamp=now_str)

    def cancel_order(self, order_id: str) -> bool:
        if self.is_paper or not self.fyers_model:
            return True
        try:
            self.fyers_model.cancel_order(data={"id": order_id})
            return True
        except Exception as e:
            logger.error(f"Error cancelling Fyers order {order_id}: {e}")
            return False

    def get_positions(self) -> List[Dict[str, Any]]:
        if self.is_paper or not self.fyers_model:
            return self._paper_positions
        try:
            pos = self.fyers_model.positions()
            return pos.get("netPositions", []) or []
        except Exception as e:
            logger.error(f"Error getting Fyers positions: {e}")
            return []

    def square_off_all(self) -> List[OrderResponse]:
        now_str = datetime.datetime.now().isoformat()
        results = []
        if self.is_paper or not self.fyers_model:
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
            qty = int(pos.get("netQty", 0))
            if qty != 0:
                action = "SELL" if qty > 0 else "BUY"
                symbol = pos.get("symbol", "")
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
        if self.is_paper or not self.fyers_model:
            return {"available_cash": 1000000.0, "used_margin": 0.0}
        try:
            funds = self.fyers_model.funds()
            fund_limit = funds.get("fund_limit", [])
            cash = 0.0
            margin = 0.0
            for item in fund_limit:
                if item.get("title") == "Total Balance":
                    cash = float(item.get("equityAmount", 0.0))
                elif item.get("title") == "Utilized Amount":
                    margin = float(item.get("equityAmount", 0.0))
            return {"available_cash": cash, "used_margin": margin}
        except Exception as e:
            logger.error(f"Error fetching Fyers funds: {e}")
            return {"available_cash": 0.0, "used_margin": 0.0}
