"""
Angel One SmartAPI Broker Adapter.
Supports authentication with client code, password, API key, and automated TOTP.
"""

import datetime
import logging
from typing import Dict, Any, List
from core.broker_base import BaseBrokerAdapter, OrderRequest, OrderResponse
import pyotp

logger = logging.getLogger("BrokerAdapter.AngelOne")


class AngelOneAdapter(BaseBrokerAdapter):
    def __init__(self, config: Dict[str, Any], is_paper: bool = True):
        super().__init__(config, is_paper)
        self.api_key = config.get("api_key", "")
        self.client_code = config.get("client_code", "")
        self.password = config.get("password", "")
        self.totp_secret = config.get("totp_secret", "")
        self.smart_api = None
        self._paper_positions: List[Dict[str, Any]] = []
        self._paper_cash: float = 1000000.0

    def deposit_virtual_funds(self, amount: float) -> float:
        if amount > 0:
            self._paper_cash += amount
            logger.info(f"[AGENT MONIES] Deposited virtual capital ₹{amount:,.2f}. New total: ₹{self._paper_cash:,.2f}")
        return self._paper_cash

    def reset_virtual_funds(self, amount: float = 1000000.0) -> float:
        self._paper_cash = max(0.0, amount)
        logger.info(f"[AGENT MONIES] Reset virtual capital to ₹{self._paper_cash:,.2f}")
        return self._paper_cash

    def connect(self) -> bool:
        if self.is_paper:
            logger.info("Angel One SmartAPI initialized in PAPER TRADING simulation mode.")
            return True

        if not self.api_key or not self.client_code:
            logger.warning("Angel One credentials missing. Defaulting to Paper Mode.")
            self.is_paper = True
            return True

        try:
            from SmartApi import SmartConnect
            self.smart_api = SmartConnect(api_key=self.api_key)
            totp_val = pyotp.TOTP(self.totp_secret).now() if self.totp_secret else None
            data = self.smart_api.generateSession(self.client_code, self.password, totp_val)
            if data.get("status"):
                logger.info(f"Angel One SmartAPI session successfully generated for {self.client_code}")
                return True
            else:
                logger.error(f"Angel One login failed: {data.get('message')}. Defaulting to Paper Mode.")
                self.is_paper = True
                return False
        except Exception as e:
            logger.error(f"Error connecting to Angel One SmartAPI: {e}. Defaulting to Paper Mode.")
            self.is_paper = True
            return False

    def place_order(self, order: OrderRequest) -> OrderResponse:
        now_str = datetime.datetime.now().isoformat()
        if self.is_paper or not self.smart_api:
            sim_id = f"SIM_ANGEL_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            self._paper_positions.append({
                "symbol": order.symbol,
                "action": order.action,
                "quantity": order.quantity,
                "price": order.price or 100.0,
                "order_id": sim_id,
                "timestamp": now_str
            })
            logger.info(f"[PAPER TRADING - ANGEL ONE] {order.action} {order.quantity}x {order.symbol} @ MARKET")
            return OrderResponse(
                success=True,
                order_id=sim_id,
                status="COMPLETE",
                message=f"Simulated execution for {order.symbol}",
                executed_price=order.price or 100.0,
                timestamp=now_str
            )

        try:
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": order.symbol,
                "symboltoken": order.symbol,  # In production, mapped via master contract
                "transactiontype": order.action.upper(),
                "exchange": "NSE",
                "ordertype": "MARKET" if order.order_type.upper() == "MARKET" else "LIMIT",
                "producttype": "INTRADAY" if order.product.upper() == "INTRADAY" else "DELIVERY",
                "duration": "DAY",
                "price": str(order.price or 0.0),
                "quantity": str(order.quantity)
            }
            order_id = self.smart_api.placeOrder(order_params)
            return OrderResponse(
                success=True,
                order_id=str(order_id),
                status="SUBMITTED",
                message="Angel One order submitted successfully",
                timestamp=now_str
            )
        except Exception as e:
            logger.error(f"Angel One order execution error: {e}")
            return OrderResponse(
                success=False,
                status="FAILED",
                message=str(e),
                timestamp=now_str
            )

    def cancel_order(self, order_id: str) -> bool:
        if self.is_paper or not self.smart_api:
            return True
        try:
            self.smart_api.cancelOrder(order_id, "NORMAL")
            return True
        except Exception as e:
            logger.error(f"Error cancelling Angel One order {order_id}: {e}")
            return False

    def get_positions(self) -> List[Dict[str, Any]]:
        if self.is_paper or not self.smart_api:
            return self._paper_positions
        try:
            pos = self.smart_api.position()
            return pos.get("data", []) or []
        except Exception as e:
            logger.error(f"Error fetching Angel One positions: {e}")
            return []

    def square_off_all(self) -> List[OrderResponse]:
        now_str = datetime.datetime.now().isoformat()
        results = []
        if self.is_paper or not self.smart_api:
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
            qty = int(pos.get("netqty", 0))
            if qty != 0:
                action = "SELL" if qty > 0 else "BUY"
                symbol = pos.get("tradingsymbol", "")
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
        if self.is_paper or not self.smart_api:
            used = sum(float(p.get("price", 0.0)) * int(p.get("quantity", 0)) for p in self._paper_positions)
            return {"available_cash": self._paper_cash, "used_margin": used}
        try:
            rms = self.smart_api.rmsLimit()
            data = rms.get("data", {})
            return {
                "available_cash": float(data.get("availablecash", 0.0)),
                "used_margin": float(data.get("utilisedmargin", 0.0))
            }
        except Exception as e:
            logger.error(f"Error fetching Angel One balance: {e}")
            return {"available_cash": 0.0, "used_margin": 0.0}
