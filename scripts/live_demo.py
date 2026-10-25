"""
Live Interactive Demonstration of BharatTrader-AI.
Demonstrates:
  1. System Telemetry & Health Monitoring
  2. TradingView Webhook Signal Execution (NIFTY 24500 CE Buy)
  3. Pre-Trade Risk Rejection (SEBI Capital Sizing Violation)
  4. Real-time Options Greeks & Bisection IV Analytics
  5. NSE Option Chain Max Pain & PCR Calculation
  6. Emergency Kill-Switch & Position Liquidation
"""

import time
import requests
import json

BASE_URL = "http://localhost:8080"
SECRET = "BHARAT_SECURE_KEY_REPLACE_ME_IN_PROD"


def print_step(title: str):
    print("\n" + "=" * 70)
    print(f"  >>> {title}")
    print("=" * 70)


def main():
    print("\n" + "#" * 70)
    print("    BHARAT-TRADER AI: LIVE REAL-TIME ENGINE DEMONSTRATION")
    print("#" * 70)

    # -------------------------------------------------------------
    # 1. Health & Telemetry
    # -------------------------------------------------------------
    print_step("STEP 1: Checking Live System Telemetry (/health)")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status Code: {r.status_code}")
        print("Live Telemetry Data:")
        print(json.dumps(r.json(), indent=2))
    except Exception as e:
        print(f"Could not connect to {BASE_URL}: {e}")
        return

    time.sleep(1.5)

    # -------------------------------------------------------------
    # 2. Ingesting a Valid TradingView Signal (NIFTY ATM Call Option)
    # -------------------------------------------------------------
    print_step("STEP 2: Ingesting Live TradingView Webhook Alert (NIFTY 24500 CE BUY)")
    tv_payload = {
        "secret_key": SECRET,
        "symbol": "NIFTY24OCT24500CE",
        "action": "BUY",
        "quantity": 25,  # 1 lot of NIFTY
        "order_type": "MARKET",
        "price": 142.50,
        "stop_loss": 115.00,
        "take_profit": 195.00,
        "product": "INTRADAY",
        "strategy_name": "Supertrend_Options_Buyer"
    }
    print(f"Outgoing Webhook Payload from TradingView Cloud:\n{json.dumps(tv_payload, indent=2)}")

    start_time = time.time()
    res = requests.post(f"{BASE_URL}/webhook", json=tv_payload)
    latency_ms = (time.time() - start_time) * 1000

    print(f"\nResponse [{res.status_code}] (Latency: {latency_ms:.1f}ms):")
    print(json.dumps(res.json(), indent=2))

    time.sleep(1.5)

    # -------------------------------------------------------------
    # 3. Portfolio State After Execution
    # -------------------------------------------------------------
    print_step("STEP 3: Checking Portfolio State After Trade Execution")
    r = requests.get(f"{BASE_URL}/health")
    data = r.json()
    print(f"Open Positions Count : {data['open_positions_count']}")
    print(f"Active Margin Cash   : ₹{data['account_balance']['available_cash']:,.2f}")
    print(f"Cumulative Daily Loss: ₹{data['cumulative_daily_loss_inr']:.2f}")
    print(f"Kill-Switch Status   : {'ACTIVE (Halted)' if data['kill_switch_active'] else 'INACTIVE (Normal)'}")

    time.sleep(1.5)

    # -------------------------------------------------------------
    # 4. Pre-Trade Risk Engine Interception (Violating Size Cap)
    # -------------------------------------------------------------
    print_step("STEP 4: Testing SEBI Pre-Trade Risk Guardrail (Oversized Order Rejection)")
    oversized_payload = {
        "secret_key": SECRET,
        "symbol": "NIFTY_FUT",
        "action": "BUY",
        "quantity": 500,  # 500 lots * 25,000 = ₹12,500,000 >> 5% Account Limit
        "order_type": "MARKET",
        "price": 25000.0,
        "product": "INTRADAY",
        "strategy_name": "Rogue_Large_Signal"
    }
    print(f"Sending Oversized Signal: 500x NIFTY_FUT @ ₹25,000 (Value: ₹1.25 Crore)")
    r = requests.post(f"{BASE_URL}/webhook", json=oversized_payload)
    print(f"Risk Engine Decision:\n{json.dumps(r.json(), indent=2)}")

    time.sleep(1.5)

    # -------------------------------------------------------------
    # 5. Live Options Analytics: Greeks & IV
    # -------------------------------------------------------------
    print_step("STEP 5: Computing Live Black-76 Greeks & Implied Volatility")
    greeks_req = {
        "option_type": "CE",
        "forward_price": 24520.0,
        "strike_price": 24500.0,
        "time_to_expiry_years": 4.0 / 365.0,  # 4 days to weekly expiry
        "interest_rate": 0.07,
        "market_price": 142.50
    }
    print(f"Greeks Request for NIFTY 24500 CE:\n{json.dumps(greeks_req, indent=2)}")
    r = requests.post(f"{BASE_URL}/analytics/greeks", json=greeks_req)
    print(f"Calculated Greeks & IV Output:\n{json.dumps(r.json(), indent=2)}")

    time.sleep(1.5)

    # -------------------------------------------------------------
    # 6. Live Options Analytics: Max Pain & Put-Call Ratio (PCR)
    # -------------------------------------------------------------
    print_step("STEP 6: Calculating NSE Option Chain Max Pain & PCR")
    option_chain_sample = [
        {"strike": 24300, "ce_oi": 25000, "pe_oi": 85000},
        {"strike": 24400, "ce_oi": 45000, "pe_oi": 95000},
        {"strike": 24500, "ce_oi": 165000, "pe_oi": 180000},
        {"strike": 24600, "ce_oi": 120000, "pe_oi": 40000},
        {"strike": 24700, "ce_oi": 140000, "pe_oi": 15000}
    ]
    r = requests.post(f"{BASE_URL}/analytics/max-pain", json=option_chain_sample)
    print(f"Max Pain Analysis Output:\n{json.dumps(r.json(), indent=2)}")

    time.sleep(1.5)

    # -------------------------------------------------------------
    # 7. Emergency Panic Button: Kill-Switch
    # -------------------------------------------------------------
    print_step("STEP 7: Triggering Emergency Kill-Switch (Square Off All)")
    print("Sending POST /kill-switch...")
    r = requests.post(f"{BASE_URL}/kill-switch?secret_key={SECRET}")
    print(f"Kill-Switch Result:\n{json.dumps(r.json(), indent=2)}")

    r = requests.get(f"{BASE_URL}/health")
    data = r.json()
    print(f"\nFinal Portfolio Check: Open Positions Count = {data['open_positions_count']}")
    print(f"Kill-Switch Locked  : {data['kill_switch_active']}")

    print("\n" + "#" * 70)
    print("    LIVE DEMONSTRATION COMPLETE: ALL SYSTEMS NOMINAL")
    print("#" * 70 + "\n")


if __name__ == "__main__":
    main()
