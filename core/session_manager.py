"""
Indian Market Session & 2FA Lifecycle Manager.
Enforces Asia/Kolkata (IST) market hours, mandatory 15:15 intraday square-off,
and automated RFC 6238 TOTP authentication tokens.
"""

import datetime
import logging
from typing import Dict, Any, Tuple
import pyotp

logger = logging.getLogger("Core.SessionManager")


class IndianMarketSessionManager:
    def __init__(
        self,
        market_open_time: str = "09:15",
        market_close_time: str = "15:30",
        square_off_time: str = "15:15",
        no_fresh_entries_after: str = "15:00",
        timezone_str: str = "Asia/Kolkata"
    ):
        self.market_open = datetime.time.fromisoformat(market_open_time)
        self.market_close = datetime.time.fromisoformat(market_close_time)
        self.square_off = datetime.time.fromisoformat(square_off_time)
        self.entry_cutoff = datetime.time.fromisoformat(no_fresh_entries_after)
        self.timezone_str = timezone_str

    def get_current_ist_time(self) -> datetime.datetime:
        """Returns current timestamp in Asia/Kolkata time."""
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        return utc_now + ist_offset

    def is_market_open(self) -> bool:
        """Checks if current time is within normal NSE/BSE cash/F&O market hours (Mon-Fri 09:15-15:30)."""
        now = self.get_current_ist_time()
        # Monday is 0, Sunday is 6
        if now.weekday() >= 5:
            return False
        current_time = now.time()
        return self.market_open <= current_time <= self.market_close

    def is_entry_allowed(self) -> Tuple[bool, str]:
        """Validates if fresh intraday trades are allowed."""
        now = self.get_current_ist_time()
        if now.weekday() >= 5:
            return False, "Market is closed (Weekend)"
        current_time = now.time()
        if current_time < self.market_open:
            return False, f"Market not yet open (Current IST: {current_time.strftime('%H:%M:%S')}, Opens: 09:15)"
        if current_time > self.entry_cutoff:
            return False, f"Fresh entries halted after 15:00 IST (Current IST: {current_time.strftime('%H:%M:%S')})"
        return True, "Trading session active"

    def is_square_off_due(self) -> bool:
        """Checks if 15:15 IST auto-square-off threshold has been reached."""
        now = self.get_current_ist_time()
        if now.weekday() >= 5:
            return False
        return now.time() >= self.square_off

    @staticmethod
    def generate_totp(totp_secret: str) -> str:
        """Generates current 6-digit TOTP code for headless broker 2FA."""
        if not totp_secret:
            raise ValueError("TOTP secret key cannot be empty.")
        totp = pyotp.TOTP(totp_secret.replace(" ", ""))
        return totp.now()
