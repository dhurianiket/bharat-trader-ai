"""
Comprehensive Risk Management Engine for Indian Algorithmic & AI Trading.
Enforces SEBI 2025/2026 mandates:
  - Account-level circuit breaker & max daily drawdown halt
  - Kelly Criterion dynamic position sizing
  - Maximum concurrent open positions & max trades per day
  - Mandatory stop-loss validation
  - Emergency Kill-Switch with one-click square-off
"""

import logging
from typing import Dict, Any, Tuple
from core.broker_base import OrderRequest

logger = logging.getLogger("Core.RiskEngine")


class RiskEngine:
    def __init__(self, risk_config: Dict[str, Any]):
        self.max_loss_inr = float(risk_config.get("max_intraday_loss_inr", 5000.0))
        self.max_capital_pct = float(risk_config.get("max_capital_per_trade_percent", 5.0))
        self.max_open_positions = int(risk_config.get("max_open_positions", 3))
        self.max_daily_trades = int(risk_config.get("max_trades_per_day", 15))
        self.enforce_hard_sl = bool(risk_config.get("enforce_hard_stop_loss", True))
        self.default_sl_pct = float(risk_config.get("default_stop_loss_percent", 1.0))
        self.use_kelly = bool(risk_config.get("use_kelly_sizing", True))
        self.kelly_fraction = float(risk_config.get("kelly_fraction", 0.5))  # Half-Kelly default

        self.cumulative_daily_loss = 0.0
        self.total_trades_today = 0
        self.is_kill_switch_active = False

    def calculate_kelly_quantity(
        self,
        account_equity: float,
        share_price: float,
        win_rate: float = 0.55,
        risk_reward_ratio: float = 1.5,
        lot_size: int = 1
    ) -> int:
        """
        Calculates optimal position size using the Kelly Criterion:
        f* = (p * b - q) / b
        where:
          p = win probability
          q = 1 - p (loss probability)
          b = payoff ratio (risk-reward)
        """
        if share_price <= 0 or account_equity <= 0:
            return lot_size

        p = win_rate
        q = 1.0 - p
        b = risk_reward_ratio

        kelly_full = (p * b - q) / b
        if kelly_full <= 0:
            return lot_size  # Non-positive edge: allocate minimum

        kelly_sized = kelly_full * self.kelly_fraction
        # Cap Kelly to maximum allowed capital allocation percentage
        max_allowed_fraction = self.max_capital_pct / 100.0
        target_fraction = min(kelly_sized, max_allowed_fraction)

        allocated_capital = account_equity * target_fraction
        raw_qty = int(allocated_capital // share_price)

        # Round down to nearest multiple of lot size
        final_qty = max(lot_size, (raw_qty // lot_size) * lot_size)
        return final_qty

    def check_pre_trade_risk(
        self,
        order: OrderRequest,
        current_open_positions_count: int,
        account_balance: float
    ) -> Tuple[bool, str]:
        """
        Validates all risk constraints before permitting order routing.
        """
        # 1. Kill-Switch Check
        if self.is_kill_switch_active:
            msg = "REJECTED: Kill-Switch is currently ACTIVE. All trading halted."
            logger.warning(msg)
            return False, msg

        # 2. Maximum Drawdown Check
        if self.cumulative_daily_loss >= self.max_loss_inr:
            self.is_kill_switch_active = True
            msg = f"REJECTED: Daily loss limit reached (₹{self.cumulative_daily_loss:.2f} >= ₹{self.max_loss_inr:.2f}). System halted."
            logger.critical(msg)
            return False, msg

        # 3. Maximum Trades Per Day Check
        if self.total_trades_today >= self.max_daily_trades:
            msg = f"REJECTED: Max daily trades count reached ({self.total_trades_today}/{self.max_daily_trades}). Overtrading protection active."
            logger.warning(msg)
            return False, msg

        # 4. Position Limit Check
        if order.action.upper() == "BUY" and current_open_positions_count >= self.max_open_positions:
            msg = f"REJECTED: Max concurrent open positions reached ({current_open_positions_count}/{self.max_open_positions})."
            logger.warning(msg)
            return False, msg

        # 5. Quantity Sanity Check
        if order.quantity <= 0:
            msg = f"REJECTED: Quantity must be positive (received {order.quantity})."
            logger.warning(msg)
            return False, msg

        # 6. Stop-Loss Validation
        if self.enforce_hard_sl and order.action.upper() == "BUY" and order.price:
            if order.stop_loss and order.stop_loss >= order.price:
                msg = f"REJECTED: Invalid Stop Loss (SL ₹{order.stop_loss} >= Entry ₹{order.price} for BUY)."
                logger.warning(msg)
                return False, msg

        # 7. Sizing Limit Check
        if account_balance > 0 and order.price:
            trade_value = order.quantity * order.price
            max_val = (self.max_capital_pct / 100.0) * account_balance
            if trade_value > max_val:
                msg = f"REJECTED: Order value ₹{trade_value:.2f} exceeds allowed risk allocation (₹{max_val:.2f})."
                logger.warning(msg)
                return False, msg

        return True, "APPROVED"

    def record_trade_completion(self, realized_pnl: float):
        """Updates internal risk trackers upon order or position closure."""
        self.total_trades_today += 1
        if realized_pnl < 0:
            self.cumulative_daily_loss += abs(realized_pnl)
            logger.warning(f"Recorded loss: ₹{abs(realized_pnl):.2f}. Total daily loss: ₹{self.cumulative_daily_loss:.2f}")
            if self.cumulative_daily_loss >= self.max_loss_inr:
                self.is_kill_switch_active = True
                logger.critical(f"CIRCUIT BREAKER TRIGGERED: Daily loss ₹{self.cumulative_daily_loss:.2f} exceeded ₹{self.max_loss_inr:.2f}!")
        else:
            logger.info(f"Recorded profit: ₹{realized_pnl:.2f}.")

    def trigger_manual_kill_switch(self):
        """Immediately triggers emergency circuit breaker."""
        self.is_kill_switch_active = True
        logger.critical("MANUAL EMERGENCY KILL-SWITCH TRIGGERED. Halting all operations.")

    def reset_daily_metrics(self):
        """Resets counters for a new trading day."""
        self.cumulative_daily_loss = 0.0
        self.total_trades_today = 0
        self.is_kill_switch_active = False
        logger.info("Daily risk metrics reset for new market session.")
