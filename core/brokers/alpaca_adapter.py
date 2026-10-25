"""
Alpaca Broker Adapter for US Equities & Crypto.
Supports both Alpaca Paper Trading and Live Trading APIs.
"""

import datetime
import logging
from typing import Dict, Any, List
from core.broker_base import BaseBrokerAdapter, OrderRequest, OrderResponse

logger = logging.getLogger("BrokerAdapter.Alpaca")


class AlpacaAdapter(BaseBrokerAdapter):
    def __init__(self, config: Dict[str, Any], is_paper: bool = True):
        super().__init__(config, is_paper)
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.is_paper = config.get("is_paper", True)
        self.trading_client = None
        self._paper_positions: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        if not self.api_key or not self.api_secret:
            logger.warning("Alpaca API credentials missing. Running local simulation.")
            return True

        try:
            from alpaca.trading.client import TradingClient
            self.trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=self.is_paper
            )
            account = self.trading_client.get_account()
            logger.info(
                f"Alpaca {'Paper' if self.is_paper else 'Live'} connected! Account #{account.account_number}, Equity: ${account.equity}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca API: {e}. Defaulting to local paper simulation.")
            return False

    def place_order(self, order: OrderRequest) -> OrderResponse:
        now_str = datetime.datetime.now().isoformat()

        if not self.trading_client:
            sim_id = f"SIM_ALPACA_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            self._paper_positions.append({
                "symbol": order.symbol,
                "action": order.action,
                "quantity": order.quantity,
                "price": order.price or 150.0,
                "order_id": sim_id,
                "timestamp": now_str
            })
            logger.info(f"[SIMULATION - ALPACA] {order.action} {order.quantity}x {order.symbol}")
            return OrderResponse(
                success=True,
                order_id=sim_id,
                status="COMPLETE",
                message=f"Local simulated order for {order.symbol}",
                executed_price=order.price or 150.0,
                timestamp=now_str
            )

        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            side = OrderSide.BUY if order.action.upper() == "BUY" else OrderSide.SELL

            if order.order_type.upper() == "MARKET":
                order_data = MarketOrderRequest(
                    symbol=order.symbol.upper(),
                    qty=order.quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY
                )
            else:
                order_data = LimitOrderRequest(
                    symbol=order.symbol.upper(),
                    qty=order.quantity,
                    side=side,
                    limit_price=order.price,
                    time_in_force=TimeInForce.DAY
                )

            alpaca_order = self.trading_client.submit_order(order_data=order_data)
            logger.info(f"[ALPACA] Order submitted: ID {alpaca_order.id}, Status: {alpaca_order.status}")
            return OrderResponse(
                success=True,
                order_id=str(alpaca_order.id),
                status=str(alpaca_order.status),
                message="Alpaca order submitted successfully",
                timestamp=now_str
            )
        except Exception as e:
            logger.error(f"[ALPACA] Order submission failed: {e}")
            return OrderResponse(
                success=False,
                status="FAILED",
                message=str(e),
                timestamp=now_str
            )

    def cancel_order(self, order_id: str) -> bool:
        if not self.trading_client:
            return True
        try:
            self.trading_client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.error(f"Error cancelling Alpaca order {order_id}: {e}")
            return False

    def get_positions(self) -> List[Dict[str, Any]]:
        if not self.trading_client:
            return self._paper_positions
        try:
            positions = self.trading_client.get_all_positions()
            return [
                {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "current_price": float(pos.current_price),
                    "unrealized_pl": float(pos.unrealized_pl)
                }
                for pos in positions
            ]
        except Exception as e:
            logger.error(f"Error fetching Alpaca positions: {e}")
            return []

    def square_off_all(self) -> List[OrderResponse]:
        now_str = datetime.datetime.now().isoformat()
        if not self.trading_client:
            self._paper_positions.clear()
            return [OrderResponse(success=True, status="CLOSED", message="Local simulation cleared", timestamp=now_str)]
        try:
            self.trading_client.close_all_positions(cancel_orders=True)
            logger.warning("Alpaca kill-switch executed: All positions closed and pending orders cancelled.")
            return [OrderResponse(success=True, status="CLOSED", message="All Alpaca positions closed", timestamp=now_str)]
        except Exception as e:
            logger.error(f"Alpaca close_all_positions error: {e}")
            return [OrderResponse(success=False, status="ERROR", message=str(e), timestamp=now_str)]

    def get_account_balance(self) -> Dict[str, float]:
        if not self.trading_client:
            return {"available_cash": 100000.0, "portfolio_value": 100000.0}
        try:
            acc = self.trading_client.get_account()
            return {
                "available_cash": float(acc.cash),
                "portfolio_value": float(acc.equity)
            }
        except Exception as e:
            logger.error(f"Error retrieving Alpaca account: {e}")
            return {"available_cash": 0.0, "portfolio_value": 0.0}
