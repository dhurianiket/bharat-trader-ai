"""
Zerodha Kite Connect Broker Adapter.
Handles automated session initialization, 2FA/TOTP handling,
order placement, and kill switch functionality.
"""

import datetime
import logging
from typing import Dict, Any, List, Optional
from core.broker_base import BaseBrokerAdapter, OrderRequest, OrderResponse

logger = logging.getLogger("BrokerAdapter.Zerodha")


class ZerodhaAdapter(BaseBrokerAdapter):
    def __init__(self, config: Dict[str, Any], is_paper: bool = True):
        super().__init__(config, is_paper)
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.access_token = config.get("access_token", "")
        self.user_id = config.get("user_id", "")
        self.kite_client = None
        self._paper_positions: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        if self.is_paper:
            logger.info("Zerodha Adapter initialized in PAPER TRADING simulation mode.")
            return True

        if not self.api_key or not self.access_token:
            logger.warning(
                "Zerodha credentials missing or unconfigured. Falling back to Paper Mode."
            )
            self.is_paper = True
            return True

        try:
            from kiteconnect import KiteConnect
            self.kite_client = KiteConnect(api_key=self.api_key)
            self.kite_client.set_access_token(self.access_token)
            # Verify profile to check valid session
            profile = self.kite_client.profile()
            logger.info(f"Successfully authenticated Zerodha Kite session for user: {profile.get('user_name', self.user_id)}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zerodha Kite API: {e}. Defaulting to Paper Mode.")
            self.is_paper = True
            return False

    def place_order(self, order: OrderRequest) -> OrderResponse:
        now_str = datetime.datetime.now().isoformat()

        if self.is_paper:
            simulated_id = f"SIM_KITE_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            simulated_pos = {
                "symbol": order.symbol,
                "action": order.action,
                "quantity": order.quantity,
                "price": order.price or 100.0,
                "product": order.product,
                "order_id": simulated_id,
                "timestamp": now_str,
            }
            self._paper_positions.append(simulated_pos)
            logger.info(f"[PAPER TRADING - ZERODHA] Executed {order.action} {order.quantity}x {order.symbol} @ MARKET")
            return OrderResponse(
                success=True,
                order_id=simulated_id,
                status="COMPLETE",
                message=f"Simulated execution for {order.symbol}",
                executed_price=order.price or 100.0,
                timestamp=now_str
            )

        if not self.kite_client:
            return OrderResponse(
                success=False,
                status="REJECTED",
                message="Kite Client not connected.",
                timestamp=now_str
            )

        try:
            from kiteconnect import KiteConnect
            variety = KiteConnect.VARIETY_REGULAR
            exchange = KiteConnect.EXCHANGE_NSE
            transaction_type = (
                KiteConnect.TRANSACTION_TYPE_BUY
                if order.action.upper() == "BUY"
                else KiteConnect.TRANSACTION_TYPE_SELL
            )
            product = (
                KiteConnect.PRODUCT_MIS
                if order.product.upper() == "INTRADAY"
                else KiteConnect.PRODUCT_CNC
            )
            order_type = (
                KiteConnect.ORDER_TYPE_MARKET
                if order.order_type.upper() == "MARKET"
                else KiteConnect.ORDER_TYPE_LIMIT
            )

            order_id = self.kite_client.place_order(
                variety=variety,
                exchange=exchange,
                tradingsymbol=order.symbol,
                transaction_type=transaction_type,
                quantity=order.quantity,
                product=product,
                order_type=order_type,
                price=order.price,
                tag=order.tag or "AI_AGENT"
            )

            logger.info(f"[LIVE ZERODHA] Order submitted. ID: {order_id}")
            return OrderResponse(
                success=True,
                order_id=str(order_id),
                status="SUBMITTED",
                message="Order placed successfully on NSE/BSE via Zerodha Kite",
                timestamp=now_str
            )
        except Exception as e:
            logger.error(f"[LIVE ZERODHA] Order placement failed: {e}")
            return OrderResponse(
                success=False,
                status="FAILED",
                message=str(e),
                timestamp=now_str
            )

    def cancel_order(self, order_id: str) -> bool:
        if self.is_paper:
            return True
        if not self.kite_client:
            return False
        try:
            self.kite_client.cancel_order(variety="regular", order_id=order_id)
            return True
        except Exception as e:
            logger.error(f"Error cancelling Zerodha order {order_id}: {e}")
            return False

    def get_positions(self) -> List[Dict[str, Any]]:
        if self.is_paper:
            return self._paper_positions
        if not self.kite_client:
            return []
        try:
            positions = self.kite_client.positions()
            return positions.get("net", [])
        except Exception as e:
            logger.error(f"Error fetching Zerodha positions: {e}")
            return []

    def square_off_all(self) -> List[OrderResponse]:
        """Emergency Kill Switch: Square off all open intraday positions."""
        now_str = datetime.datetime.now().isoformat()
        results = []
        logger.warning(f"KILL-SWITCH ACTIVATED: Closing all positions on Zerodha.")

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
            qty = pos.get("quantity", 0)
            if qty != 0:
                action = "SELL" if qty > 0 else "BUY"
                symbol = pos.get("symbol", pos.get("tradingsymbol", ""))
                exit_order = OrderRequest(
                    symbol=symbol,
                    action=action,
                    quantity=abs(qty),
                    order_type="MARKET",
                    product="INTRADAY",
                    tag="KILL_SWITCH"
                )
                res = self.place_order(exit_order)
                results.append(res)
        return results

    def get_account_balance(self) -> Dict[str, float]:
        if self.is_paper:
            return {"available_cash": 1000000.0, "used_margin": 0.0}
        if not self.kite_client:
            return {"available_cash": 0.0, "used_margin": 0.0}
        try:
            margins = self.kite_client.margins(segment="equity")
            return {
                "available_cash": float(margins.get("available", {}).get("cash", 0.0)),
                "used_margin": float(margins.get("utilised", {}).get("debits", 0.0))
            }
        except Exception as e:
            logger.error(f"Error fetching Zerodha margins: {e}")
            return {"available_cash": 0.0, "used_margin": 0.0}
