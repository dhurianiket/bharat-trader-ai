"""
Unit tests for Options Analytics (Black-76 Greeks, IV Solver, Max Pain).
"""

import pytest
from analytics.black76_greeks import black76_price, black76_greeks, calculate_implied_volatility
from analytics.max_pain import calculate_max_pain
from analytics.option_chain import OptionChainResolver
from analytics.oi_tracker import analyze_oi_flow, OIFlowRegime


def test_black76_call_and_put():
    f = 24500.0
    k = 24500.0
    t = 7.0 / 365.0  # 1 week
    r = 0.07
    sigma = 0.15

    call_price = black76_price("CE", f, k, t, r, sigma)
    put_price = black76_price("PE", f, k, t, r, sigma)

    assert call_price > 0.0
    assert put_price > 0.0
    # For ATM with f=k, call and put prices should be virtually identical
    assert abs(call_price - put_price) < 1.0


def test_black76_greeks_values():
    greeks = black76_greeks(
        option_type="CE",
        forward_price=24500.0,
        strike_price=24500.0,
        time_to_expiry_years=7.0 / 365.0,
        interest_rate=0.07,
        volatility=0.15
    )
    # ATM call delta should be approximately 0.50
    assert 0.45 <= greeks["delta"] <= 0.55
    assert greeks["gamma"] > 0.0
    assert greeks["vega"] > 0.0
    assert greeks["theta"] < 0.0  # Option decay is negative


def test_iv_solver():
    market_price = 145.0
    f = 24500.0
    k = 24500.0
    t = 7.0 / 365.0

    iv = calculate_implied_volatility("CE", market_price, f, k, t)
    assert iv is not None
    assert 0.05 < iv < 0.50


def test_max_pain_calculation():
    strikes_data = [
        {"strike": 24300.0, "ce_oi": 20000, "pe_oi": 80000},
        {"strike": 24400.0, "ce_oi": 40000, "pe_oi": 70000},
        {"strike": 24500.0, "ce_oi": 150000, "pe_oi": 160000},
        {"strike": 24600.0, "ce_oi": 90000, "pe_oi": 30000},
        {"strike": 24700.0, "ce_oi": 120000, "pe_oi": 15000},
    ]
    res = calculate_max_pain(strikes_data)
    assert res["max_pain_strike"] == 24500.0
    assert res["put_call_ratio"] > 0.0


def test_option_chain_resolver():
    atm = OptionChainResolver.get_atm_strike("NIFTY", 24523.40)
    assert atm == 24500
    ladder = OptionChainResolver.generate_strike_ladder("NIFTY", 24500, num_strikes_above_below=2)
    assert ladder == [24400, 24450, 24500, 24550, 24600]


def test_oi_flow_regimes():
    # Long buildup: price up, oi up
    flow = analyze_oi_flow(current_price=24600, previous_price=24500, current_oi=200000, previous_oi=180000)
    assert flow["flow_regime"] == OIFlowRegime.LONG_BUILDUP.value
    assert flow["signal_bias"] == "STRONG_BULLISH"
