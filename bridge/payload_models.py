"""
Pydantic Schemas for TradingView Webhooks and Action Center.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TradingViewAlertPayload(BaseModel):
    secret_key: str = Field(..., description="Authentication secret key matching server config")
    symbol: str = Field(..., description="Trading symbol, e.g. NIFTY24OCT24500CE, RELIANCE, INFY")
    action: str = Field(..., description="BUY or SELL")
    quantity: int = Field(1, description="Quantity in shares or lot multiple")
    order_type: str = Field("MARKET", description="MARKET, LIMIT, SL, SL-M")
    price: Optional[float] = Field(None, description="Limit price if LIMIT order")
    stop_loss: Optional[float] = Field(None, description="Hard Stop Loss price level")
    take_profit: Optional[float] = Field(None, description="Target Take Profit price level")
    product: str = Field("INTRADAY", description="INTRADAY (MIS) or DELIVERY (CNC/NORMAL)")
    strategy_name: Optional[str] = Field("TV_Strategy", description="Pine Script Strategy Name")
    exchange: Optional[str] = Field("NSE", description="NSE, BSE, or NFO")


class GreeksRequestPayload(BaseModel):
    option_type: str = Field(..., description="CE or PE")
    forward_price: float = Field(..., description="Underlying or Futures price")
    strike_price: float = Field(..., description="Option strike price")
    time_to_expiry_years: float = Field(..., description="Time to expiry in fraction of year")
    interest_rate: float = Field(0.07, description="Risk-free rate (default 7% for RBI repo)")
    volatility: Optional[float] = Field(None, description="Annualized volatility (e.g. 0.15 for 15%)")
    market_price: Optional[float] = Field(None, description="Market premium if calculating IV")
