"""
Dhan Broker Adapter (dhanhq).
Dhan provides native webhook support as well as an official REST API.
"""

import datetime
import logging
from typing import Dict, Any, List
from core.broker_base import BaseBrokerAdapter, OrderRequest, OrderResponse

logger = logging.getLogger("BrokerAdapter.Dhan")


class DhanAdapter(BaseBrokerAdapter):
    def __init__(self, config: Dict[str, Any], is_paper: bool = True):
        super().__init__(config, is_paper)
        self.client_id = config.get("client_id", "")
        self.access_token = config.get("access_token", "")
        self.dhan_client = None
        self._paper_positions: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        if self.is_paper:
            logger.info("Dhan Adapter initialized in PAPER TRADING simulation mode.")
            return True

        if not self.client_id or not self.access_token:
            logger.warning("Dhan credentials missing. Defaulting to Paper Mode.")
            self.is_paper = True
            return True

        try:
            from dhanhq import dhanhq
            self.dhan_client = dhanhq(self.client_id, self.access_token)
            logger.info(f"DhanHQ connection initialized for Client ID: {self.client_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize DhanHQ SDK: {e}. Defaulting to Paper Mode.")
            self.is_paper = True
            return False

    def place_order(self, order: OrderRequest) -> OrderResponse:
        now_str = datetime.datetime.now().isoformat()

        if self.is_paper:
            simulated_id = f"SIM_DHAN_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            self._paper_positions.append({
                "symbol": order.symbol,
                "action": order.action,
                "quantity": order.quantity,
                "price": order.price or 100.0,
                "product": order.product,
                "order_id": simulated_id,
                "timestamp": now_str,
            })
            logger.info(f"[PAPER TRADING - DHAN] Executed {order.action} {order.quantity}x {order.symbol}")
            return OrderResponse(
                success=True,
                order_id=simulated_id,
                status="COMPLETE",
                message=f"Simulated execution for {order.symbol}",
                executed_price=order.price or 100.0,
                timestamp=now_str
            )

        if not self.dhan_client:
            return OrderResponse(
                success=False,
                status="REJECTED",
                message="Dhan client not connected.",
                timestamp=now_str
            )

        try:
            from dhanhq import dhanhq
            trans_type = dhanhq.BUY if order.action.upper() == "BUY" else dhanhq.SELL
            prod_type = dhanhq.INTRA if order.product.upper() == "INTRADAY" else dhanhq.CNC
            order_type = dhanhq.MARKET if order.order_type.upper() == "MARKET" else dhanhq.LIMIT

            response = self.dhan_client.place_order(
                security_id=order.symbol,
                exchange_segment=dhanhq.NSE,
                transaction_type=trans_type,
                quantity=order.quantity,
                order_type=order_type,
                product_type=prod_type,
                price=order.price or 0.0
            )

            order_id = response.get("data", {}).get("orderId", "UNKNOWN")
            return OrderResponse(
                success=True,
                order_id=str(order_id),
                status=response.get("status", "SUBMITTED"),
                message="Order placed via DhanHQ",
                timestamp=now_str
            )
        except Exception as e:
            logger.error(f"[LIVE DHAN] Order placement failed: {e}")
            return OrderResponse(
                success=False,
                status="FAILED",
                message=str(e),
                timestamp=now_str
            )

    def cancel_order(self, order_id: str) -> bool:
        if self.is_paper or not self.dhan_client:
            return True
        try:
            self.dhan_client.cancel_order(order_id)
            return True
        except Exception as e:
            logger.error(f"Error cancelling Dhan order {order_id}: {e}")
            return False

    def get_positions(self) -> List[Dict[str, Any]]:
        if self.is_paper:
            return self._paper_positions
        if not self.dhan_client:
            return []
        try:
            res = self.dhan_client.get_positions()
            return res.get("data", [])
        except Exception as e:
            logger.error(f"Error fetching Dhan positions: {e}")
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
            qty = pos.get("netQty", 0)
            if qty != 0:
                action = "SELL" if qty > 0 else "BUY"
                symbol = str(pos.get("securityId", ""))
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
        if not self.dhan_client:
            return {"available_cash": 0.0, "used_margin": 0.0}
        try:
            res = self.dhan_client.get_fund_limits()
            data = res.get("data", {})
            return {
                "available_cash": float(data.get("availabelBalance", 0.0)),
                "used_margin": float(data.get("utilizedAmount", 0.0))
            }
        except Exception as e:
            logger.error(f"Error fetching Dhan funds: {e}")
            return {"available_cash": 0.0, "used_margin": 0.0}
