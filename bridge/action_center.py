"""
Action Center & Execution Queue.
Supports Full-Auto (instant execution) and Semi-Auto (human-in-the-loop confirmation) modes.
"""

import uuid
import datetime
from typing import Dict, Any, List, Optional
from core.broker_base import OrderRequest, OrderResponse, BaseBrokerAdapter
from core.risk_engine import RiskEngine

logger = logging = __import__("logging").getLogger("Bridge.ActionCenter")


class ActionCenter:
    def __init__(self, execution_mode: str = "full_auto"):
        self.execution_mode = execution_mode  # "full_auto" or "semi_auto"
        self._pending_orders: Dict[str, Dict[str, Any]] = {}

    def handle_incoming_signal(
        self,
        order: OrderRequest,
        broker: BaseBrokerAdapter,
        risk: RiskEngine
    ) -> Dict[str, Any]:
        """
        Processes incoming signal based on execution mode.
        """
        if self.execution_mode == "full_auto":
            resp = broker.place_order(order)
            return {
                "mode": "full_auto",
                "status": "EXECUTED" if resp.success else "EXECUTION_FAILED",
                "order_id": resp.order_id,
                "message": resp.message,
                "timestamp": resp.timestamp
            }
        else:
            # Semi-Auto: Queue for manual approval
            queue_id = f"ACT_{uuid.uuid4().hex[:8].upper()}"
            item = {
                "queue_id": queue_id,
                "order": order.model_dump(),
                "created_at": datetime.datetime.now().isoformat(),
                "status": "PENDING_CONFIRMATION"
            }
            self._pending_orders[queue_id] = item
            logger.info(f"[ACTION CENTER] Queued order {queue_id} for {order.symbol} {order.action} {order.quantity}x")
            return {
                "mode": "semi_auto",
                "status": "QUEUED_FOR_APPROVAL",
                "queue_id": queue_id,
                "message": "Order held in Action Center. Call /action-center/approve to execute."
            }

    def list_pending(self) -> List[Dict[str, Any]]:
        return list(self._pending_orders.values())

    def approve_order(self, queue_id: str, broker: BaseBrokerAdapter) -> Optional[OrderResponse]:
        item = self._pending_orders.pop(queue_id, None)
        if not item:
            return None
        order = OrderRequest(**item["order"])
        resp = broker.place_order(order)
        logger.info(f"[ACTION CENTER] Approved and placed order {queue_id} (Broker ID: {resp.order_id})")
        return resp

    def reject_order(self, queue_id: str) -> bool:
        return self._pending_orders.pop(queue_id, None) is not None
