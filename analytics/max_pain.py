"""
NSE Max Pain & Put-Call Ratio (PCR) Calculation Engine.
Identifies the strike price where option buyers experience maximum financial loss.
"""

from typing import List, Dict, Any, Tuple


def calculate_max_pain(strikes_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates Max Pain strike and Total Market Loss from option chain data.
    
    Expected format of each entry in strikes_data:
      {
        "strike": 24500.0,
        "ce_oi": 150000,   # Call Open Interest
        "pe_oi": 210000    # Put Open Interest
      }
    
    Returns:
      {
        "max_pain_strike": 24500.0,
        "total_pain_value": 125000000.0,
        "put_call_ratio": 1.40,
        "sentiment": "BULLISH"
      }
    """
    if not strikes_data:
        return {
            "max_pain_strike": 0.0,
            "total_pain_value": 0.0,
            "put_call_ratio": 0.0,
            "sentiment": "NEUTRAL"
        }

    strikes = [float(item["strike"]) for item in strikes_data]
    total_ce_oi = sum(int(item.get("ce_oi", 0)) for item in strikes_data)
    total_pe_oi = sum(int(item.get("pe_oi", 0)) for item in strikes_data)

    pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 1.0

    min_total_loss = float("inf")
    max_pain_strike = strikes[0]

    for test_strike in strikes:
        total_loss = 0.0
        for item in strikes_data:
            k = float(item["strike"])
            ce_oi = int(item.get("ce_oi", 0))
            pe_oi = int(item.get("pe_oi", 0))

            # Call loss: if underlying ends at test_strike > k, calls are ITM
            if test_strike > k:
                total_loss += (test_strike - k) * ce_oi

            # Put loss: if underlying ends at test_strike < k, puts are ITM
            elif test_strike < k:
                total_loss += (k - test_strike) * pe_oi

        if total_loss < min_total_loss:
            min_total_loss = total_loss
            max_pain_strike = test_strike

    # Sentiment based on PCR
    if pcr > 1.25:
        sentiment = "BULLISH"
    elif pcr < 0.75:
        sentiment = "BEARISH"
    else:
        sentiment = "NEUTRAL"

    return {
        "max_pain_strike": max_pain_strike,
        "total_pain_value": round(min_total_loss, 2),
        "put_call_ratio": pcr,
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
        "sentiment": sentiment
    }
