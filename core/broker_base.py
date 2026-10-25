"""
Abstract Broker Interface for the Autonomous AI Trading Agent.
Normalizes order execution, position queries, and account telemetry across
Indian brokers (Zerodha, Dhan, Angel One) and US brokers (Alpaca, IBKR).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class OrderRequest(BaseModel):
    symbol: str
    action: str  # "BUY" or "SELL"
    quantity: int
    order_type: str = "MARKET"  # "MARKET", "LIMIT", "SL", "SL-M"
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    product: str = "INTRADAY"  # "INTRADAY" (MIS) or "CNC" / "NORMAL"
    tag: Optional[str] = "AI_AGENT"


class OrderResponse(BaseModel):
    success: bool
    order_id: Optional[str] = None
    status: str
    message: str
    executed_price: Optional[float] = None
    timestamp: str


class BaseBrokerAdapter(ABC):
    """
    Standard interface for all broker adapters.
    """

    def __init__(self, config: Dict[str, Any], is_paper: bool = True):
        self.config = config
        self.is_paper = is_paper

    @abstractmethod
    def connect(self) -> bool:
        """Authenticate and establish session with the broker."""
        pass

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place an order with the broker or paper trading simulator."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Fetch open and closed positions."""
        pass

    @abstractmethod
    def square_off_all(self) -> List[OrderResponse]:
        """Panic / Kill Switch: Close all open positions immediately."""
        pass

    @abstractmethod
    def get_account_balance(self) -> Dict[str, float]:
        """Retrieve current margin and cash balance."""
        pass
