"""
Tabular Q-Learning Reinforcement Learning Dynamic Exit Agent.
Merged from AI-trader. Adapts exit policy dynamically instead of fixed SL/TP.

State features (8):
  - unrealized_pnl_pct:  Current P&L as % of entry premium
  - bars_held_norm:      Minutes or bars held (normalized 0 to 1)
  - premium_momentum:    Rate of change of price (last 3 bars)
  - premium_volatility:  Std dev of price changes (last 5 bars)
  - distance_to_sl:      Distance to stop loss as %
  - distance_to_tgt:     Distance to target as %
  - trailing_active:     1 if trailing SL active, else 0
  - peak_gain_pct:       Maximum unrealized gain reached

Action space:
  0 = HOLD    (Keep position open)
  1 = EXIT    (Close position immediately)
  2 = TIGHTEN (Tighten SL closer to market price)
"""

from typing import Dict, Any, Tuple, List
import numpy as np


class RLExitAgent:
    ACTIONS = ["HOLD", "EXIT", "TIGHTEN"]

    BINS = {
        "unrealized_pnl_pct": [-0.30, -0.15, -0.05, 0.0, 0.05, 0.15, 0.30, 0.50],
        "bars_held_norm":      [0.1, 0.2, 0.3, 0.5, 0.7, 0.85, 1.0],
        "premium_momentum":    [-0.05, -0.02, -0.005, 0.0, 0.005, 0.02, 0.05],
        "premium_volatility":  [0.005, 0.01, 0.02, 0.03, 0.05, 0.08],
        "distance_to_sl":      [0.0, 0.05, 0.10, 0.20, 0.35, 0.50],
        "distance_to_tgt":     [0.0, 0.10, 0.25, 0.40, 0.60, 0.80],
        "trailing_active":     [0.5],
        "peak_gain_pct":       [0.0, 0.05, 0.10, 0.20, 0.35, 0.50],
    }

    def __init__(self, q_table: Dict[Tuple, np.ndarray] = None):
        self.q_table = q_table or {}

    def discretize_state(self, state: Dict[str, float]) -> Tuple[int, ...]:
        indices = []
        for feat, bins in self.BINS.items():
            val = float(state.get(feat, 0.0))
            idx = int(np.digitize(val, bins))
            indices.append(idx)
        return tuple(indices)

    def decide(self, state: Dict[str, float]) -> Tuple[str, str]:
        """
        Decides whether to HOLD, EXIT, or TIGHTEN based on Q-table or learned heuristic policy.
        Returns: (action: str, reason: str)
        """
        pnl = state.get("unrealized_pnl_pct", 0.0)
        peak = state.get("peak_gain_pct", 0.0)
        bars_held_norm = state.get("bars_held_norm", 0.0)
        dist_sl = state.get("distance_to_sl", 0.1)

        discrete_state = self.discretize_state(state)

        # If Q-table has this state entry, use argmax Q
        if discrete_state in self.q_table:
            q_values = self.q_table[discrete_state]
            action_idx = int(np.argmax(q_values))
            action = self.ACTIONS[action_idx]
            return action, f"Learned Q-table policy decision ({action})"

        # Heuristic RL Fallback Policy (Zero-cold-start stability)
        # 1. Take profit if gain is strong and retraces > 30% from peak
        if peak >= 0.15 and (peak - pnl) > 0.05:
            return "EXIT", f"Locking in profits: gained {peak*100:.1f}%, now {pnl*100:.1f}%"

        # 2. Tighten SL if profit exceeds 10%
        if pnl >= 0.10 and dist_sl > 0.05:
            return "TIGHTEN", f"Profit threshold reached (+{pnl*100:.1f}%): tightening SL"

        # 3. Timeout / Stale position protection
        if bars_held_norm >= 0.90 and pnl < 0.02:
            return "EXIT", "Stale trade exit: time horizon reached without target acceleration"

        # 4. Standard hold
        return "HOLD", "Conditions optimal to hold position"
