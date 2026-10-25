"""
Black-76 Options Greeks & Implied Volatility (IV) Engine.
Optimized for Indian F&O (NSE NIFTY, BANKNIFTY, and equity options).

Formulas:
  Delta (Call) = e^(-rT) * N(d1)
  Delta (Put)  = -e^(-rT) * N(-d1)
  Gamma        = e^(-rT) * phi(d1) / (F * sigma * sqrt(T))
  Vega         = F * e^(-rT) * phi(d1) * sqrt(T) / 100  (per 1% vol change)
  Theta        = (-F * e^(-rT) * phi(d1) * sigma / (2 * sqrt(T)) - r * premium) / 365 (per calendar day)
  Rho          = -T * premium / 100                     (per 1% rate change)

IV solved via robust Bisection search (reliable, no derivative singularities).
"""

import math
from typing import Dict, Any, Optional, Tuple


def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


def black76_price(
    option_type: str,
    forward_price: float,
    strike_price: float,
    time_to_expiry_years: float,
    interest_rate: float,
    volatility: float
) -> float:
    """
    Computes theoretical option price using the Black-76 model.
    """
    if time_to_expiry_years <= 0 or volatility <= 0 or forward_price <= 0 or strike_price <= 0:
        intrinsic = (
            max(0.0, forward_price - strike_price)
            if option_type.upper() in ("CE", "CALL")
            else max(0.0, strike_price - forward_price)
        )
        return intrinsic

    f = float(forward_price)
    k = float(strike_price)
    t = float(time_to_expiry_years)
    r = float(interest_rate)
    sigma = float(volatility)

    sqrt_t = math.sqrt(t)
    d1 = (math.log(f / k) + 0.5 * sigma * sigma * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    discount = math.exp(-r * t)

    is_call = option_type.upper() in ("CE", "CALL")
    if is_call:
        return discount * (f * norm_cdf(d1) - k * norm_cdf(d2))
    else:
        return discount * (k * norm_cdf(-d2) - f * norm_cdf(-d1))


def black76_greeks(
    option_type: str,
    forward_price: float,
    strike_price: float,
    time_to_expiry_years: float,
    interest_rate: float,
    volatility: float
) -> Dict[str, float]:
    """
    Computes all First and Second-Order Greeks:
      - delta: Hedge ratio
      - gamma: Rate of change of delta per 1 pt underlying move
      - theta: Daily time decay (₹ / day)
      - vega: Sensitivity to 1% change in implied volatility
      - rho: Sensitivity to 1% change in risk-free interest rate
    """
    f = max(0.0001, float(forward_price))
    k = max(0.0001, float(strike_price))
    t = max(1e-6, float(time_to_expiry_years))
    r = float(interest_rate)
    sigma = max(0.001, float(volatility))

    sqrt_t = math.sqrt(t)
    d1 = (math.log(f / k) + 0.5 * sigma * sigma * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    discount = math.exp(-r * t)
    pdf_d1 = norm_pdf(d1)

    is_call = option_type.upper() in ("CE", "CALL")

    # Delta
    if is_call:
        delta = discount * norm_cdf(d1)
    else:
        delta = -discount * norm_cdf(-d1)

    # Gamma
    gamma = (discount * pdf_d1) / (f * sigma * sqrt_t)

    # Vega (scaled per 1% change in vol, i.e. / 100)
    vega = (f * discount * pdf_d1 * sqrt_t) / 100.0

    # Theta (per calendar day, i.e. / 365)
    premium = black76_price(option_type, f, k, t, r, sigma)
    theta_term1 = -(f * discount * pdf_d1 * sigma) / (2.0 * sqrt_t)
    theta_annual = theta_term1 - (r * premium)
    theta = theta_annual / 365.0

    # Rho (per 1% move in interest rate)
    rho = (-t * premium) / 100.0

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "rho": round(rho, 4)
    }


def calculate_implied_volatility(
    option_type: str,
    market_price: float,
    forward_price: float,
    strike_price: float,
    time_to_expiry_years: float,
    interest_rate: float = 0.07,
    tolerance: float = 1e-4,
    max_iterations: int = 100
) -> Optional[float]:
    """
    Solves for Implied Volatility (IV) using Bisection.
    Guaranteed convergence without Newton-Raphson division-by-zero crashes.
    """
    if market_price <= 0 or time_to_expiry_years <= 0 or forward_price <= 0 or strike_price <= 0:
        return None

    # Check intrinsic value
    is_call = option_type.upper() in ("CE", "CALL")
    intrinsic = max(0.0, forward_price - strike_price) if is_call else max(0.0, strike_price - forward_price)
    if market_price < intrinsic:
        return None

    low_vol = 0.001  # 0.1%
    high_vol = 5.0   # 500%

    price_low = black76_price(option_type, forward_price, strike_price, time_to_expiry_years, interest_rate, low_vol)
    price_high = black76_price(option_type, forward_price, strike_price, time_to_expiry_years, interest_rate, high_vol)

    if market_price < price_low:
        return low_vol
    if market_price > price_high:
        return high_vol

    for _ in range(max_iterations):
        mid_vol = (low_vol + high_vol) / 2.0
        mid_price = black76_price(option_type, forward_price, strike_price, time_to_expiry_years, interest_rate, mid_vol)
        diff = mid_price - market_price

        if abs(diff) < tolerance:
            return round(mid_vol, 4)

        if diff > 0:
            high_vol = mid_vol
        else:
            low_vol = mid_vol

    return round((low_vol + high_vol) / 2.0, 4)
