"""
Option Chain Generator & Strike Resolver.
Handles ATM/ITM/OTM strike determination and option symbol formatting for Indian brokers.
"""

import math
from typing import List, Dict, Any, Tuple


class OptionChainResolver:
    STRIKE_STEPS = {
        "NIFTY": 50,
        "BANKNIFTY": 100,
        "FINNIFTY": 50,
        "MIDCPNIFTY": 25,
        "SENSEX": 100
    }

    @classmethod
    def get_atm_strike(cls, underlying_symbol: str, spot_price: float) -> int:
        """Calculates nearest At-The-Money (ATM) strike price."""
        symbol_upper = underlying_symbol.upper()
        step = cls.STRIKE_STEPS.get(symbol_upper, 50)
        return int(round(spot_price / step) * step)

    @classmethod
    def generate_strike_ladder(
        cls,
        underlying_symbol: str,
        spot_price: float,
        num_strikes_above_below: int = 5
    ) -> List[int]:
        """
        Generates a symmetrical ladder of strikes centered around ATM.
        """
        atm = cls.get_atm_strike(underlying_symbol, spot_price)
        step = cls.STRIKE_STEPS.get(underlying_symbol.upper(), 50)

        strikes = []
        for i in range(-num_strikes_above_below, num_strikes_above_below + 1):
            strikes.append(atm + (i * step))
        return sorted(strikes)

    @classmethod
    def format_tradingsymbol(
        cls,
        underlying_symbol: str,
        expiry_date_str: str,  # Format: "24OCT" or "24O24" (YYMDD or YYMMM)
        strike: int,
        option_type: str       # "CE" or "PE"
    ) -> str:
        """
        Constructs standard NSE option trading symbol.
        Example: NIFTY24OCT24500CE
        """
        return f"{underlying_symbol.upper()}{expiry_date_str.upper()}{strike}{option_type.upper()}"
