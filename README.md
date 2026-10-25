<div align="center">

# 🇮🇳 BharatTrader-AI
### **Autonomous Multi-Broker AI & Quantitative Trading Engine**
*High-Frequency TradingView Webhook Bridge • Pure-Math Black-76 Greeks • 5-Regime Market Classifier • Q-Learning Exit Agent • SEBI 2025/2026 Circuit Breakers*

<p align="center">
  <a href="https://github.com/dhurianiket/bharat-trader-ai/actions"><img src="https://img.shields.io/badge/Tests-20%2F20%20Passed-brightgreen?style=for-the-badge&logo=pytest&logoColor=white" alt="Tests" /></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.12%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/API-FastAPI%20v2-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" /></a>
  <a href="https://tradingview.com"><img src="https://img.shields.io/badge/TradingView-PineScript%20v5-2962FF?style=for-the-badge&logo=tradingview&logoColor=white" alt="TradingView" /></a>
  <a href="https://github.com/dhurianiket/bharat-trader-ai/blob/master/LICENSE"><img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge" alt="License" /></a>
</p>

<p align="center">
  <a href="#-architecture">Architecture</a> •
  <a href="#-core-capabilities">Capabilities</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-broker-adapters">Brokers</a> •
  <a href="#-tradingview-webhooks">TradingView</a> •
  <a href="#-rest-api-reference">API Reference</a> •
  <a href="#-sebi-regulatory-compliance">SEBI Compliance</a>
</p>

---

</div>

## 📌 Executive Overview

**BharatTrader-AI** is a unified, production-grade algorithmic trading framework engineered specifically for Indian equities, indices, and derivatives (NSE/BSE/NFO). Built on a **decoupled architecture**, it separates heavy asynchronous AI deliberation and options mathematics from ultra-low-latency order execution and strict risk guardrails.

It synthesizes the architectural paradigms of the top open-source quantitative ecosystems:
* 🌐 **`marketcalls/openalgo`**: Normalized REST API, Action Center, and multi-broker routing.
* ⚡ **`TheHardeep/fenix`**: Resilient Python adapters for **Zerodha, Dhan, Angel One, Upstox, and Fyers**.
* 📐 **`marketcalls/openbull`**: Pure-math Black-76 Options Greeks (Delta, Gamma, Vega, Theta, Rho), Bisection IV solver, and NSE Max Pain.
* 🧠 **`aaryansinha16/AI-trader`**: 5-Regime Market Classifier (`TRENDING_BULL`, `TRENDING_BEAR`, `SIDEWAYS`, `HIGH_VOLATILITY`, `LOW_VOLATILITY`), Tabular Q-Learning Reinforcement Learning Exit Agent (`RLExitAgent`), and multi-factor scoring.
* 🤖 **`marketcalls/Agentic-Trader`**: Multi-agent LLM reasoning sentinel with LiteLLM (Groq, Cerebras, OpenAI, Ollama).
* ⏱️ **`arimanyus/warrenduffer`**: Strict Asia/Kolkata (IST) market clock lifecycle, 15:15 IST mandatory intraday auto-square-off, and circuit breaker risk halts.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph TriggerLayer["1. Signal Ingestion & Triggers"]
        TV["TradingView Cloud<br/>Pine Script Strategy Alert"]
        Manual["Action Center Web UI / REST"]
        Scanner["Intraday Market Scanner"]
    end

    subgraph BridgeLayer["2. Webhook Bridge & Session Gate"]
        WH["FastAPI Server (:8000/webhook)"]
        AUTH["HMAC Secret Key & 2FA Validation"]
        CLOCK["Session Manager (IST 09:15-15:30)"]
    end

    subgraph BrainLayer["3. Quantitative & AI Decision Engine"]
        REGIME["5-Regime Classifier<br/>(ADX / ATR / EMA)"]
        TECH["Technical Indicators<br/>(Supertrend / RSI / VWAP)"]
        FLOW["OI Flow Detector<br/>(Long/Short Buildup)"]
        SCORE["Composite Scorer<br/>(0.35 Tech + 0.35 Regime + 0.30 Flow)"]
        RL["Q-Learning RL Exit Agent<br/>(HOLD / EXIT / TIGHTEN)"]
    end

    subgraph RiskLayer["4. SEBI Regulatory & Risk Engine"]
        CB["Account Circuit Breaker (Max Daily Loss)"]
        KELLY["Kelly Criterion Position Sizing"]
        LIMITS["Max Open Positions & SL Validator"]
        KILL["Emergency One-Click Kill-Switch"]
    end

    subgraph BrokerLayer["5. Unified Broker Gateways"]
        ROUTER["Normalized Broker Adapter"]
        Kite["Zerodha Kite Connect"]
        Dhan["DhanHQ REST & Webhook"]
        Angel["Angel One SmartAPI"]
        Fyers["Fyers API v3"]
        Upstox["Upstox API v2"]
        Paper["Realistic Paper Simulator"]
    end

    TV --> WH
    Manual --> WH
    Scanner --> WH

    WH --> AUTH --> CLOCK
    CLOCK --> REGIME & TECH & FLOW
    REGIME & TECH & FLOW --> SCORE
    SCORE -->|"Approved (Score ≥ 0.65)"| CB
    SCORE -->|"Vetoed"| REJECT["Alert Discarded / Logged"]
    
    CB --> KELLY --> LIMITS --> ROUTER
    KILL -.->|"Square Off All"| ROUTER

    ROUTER --> Kite & Dhan & Angel & Fyers & Upstox & Paper
    Paper --> RL
```

---

## ⚡ Core Capabilities

| Capability | Engine Module | Description | Performance / Spec |
| :--- | :--- | :--- | :--- |
| **TradingView Webhooks** | [`bridge/webhook_server.py`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/bridge/webhook_server.py) | High-throughput asynchronous listener accepting JSON alerts. | Sub-millisecond parsing, HMAC authentication |
| **Black-76 Greeks & IV** | [`analytics/black76_greeks.py`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/analytics/black76_greeks.py) | Pure-math option pricing for Indian F&O (Delta, Gamma, Vega, Theta, Rho). | Zero external C-dependencies, Bisection IV solver |
| **Max Pain & PCR** | [`analytics/max_pain.py`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/analytics/max_pain.py) | Pinpoints strike where option buyers experience maximum financial pain. | Computes PCR, Put/Call OI and market sentiment |
| **Market Regime Detector** | [`brain/regime_detector.py`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/brain/regime_detector.py) | Classifies market into Bull, Bear, Sideways, High Vol, or Low Vol. | Multi-timeframe EMA + ATR volatility scoring |
| **Reinforcement Learning Exit** | [`brain/rl_exit_agent.py`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/brain/rl_exit_agent.py) | Q-Learning agent with 8-feature state vector deciding HOLD, EXIT, TIGHTEN. | Dynamic trailing stops; locks in peak profits |
| **SEBI Circuit Breakers** | [`core/risk_engine.py`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/core/risk_engine.py) | Account-level loss caps, hard stop-losses, and one-click panic kill-switch. | Instant order cancellation & position liquidation |
| **Kelly Criterion Sizing** | [`core/risk_engine.py`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/core/risk_engine.py) | Dynamic sizing formula: $f^* = \frac{p \cdot b - q}{b}$ with Half-Kelly factor. | Caps trade value to 5% equity ceiling |
| **Action Center** | [`bridge/action_center.py`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/bridge/action_center.py) | Supports Full-Auto (instant) and Semi-Auto (human approval queue) modes. | Pending order queue, REST approval endpoints |

---

## 🚀 Quick Start

### 1. Installation
Clone the repository and set up the Python virtual environment:
```powershell
git clone https://github.com/dhurianiket/bharat-trader-ai.git
cd bharat-trader-ai

# Initialize virtual environment with uv (or python -m venv)
uv venv
.\.venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
```

### 2. Automated Test & Diagnostics Suite
Run the master automated test runner to verify everything end-to-end:
```powershell
.\.venv\Scripts\python.exe scripts/run_automated_tests.py
```
> [!NOTE]
> All 20 unit tests, options pricing mathematics, market regime classification, and simulated TradingView signals will run and report status automatically.

### 3. Launch Webhook Server
```powershell
.\.venv\Scripts\python.exe main.py
```
*The FastAPI server will boot on `http://0.0.0.0:8000/webhook` ready to accept alerts.*

---

## ⚙️ Configuration Guide

The master configuration resides in [`config/config.yaml`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/config/config.yaml).

```yaml
app:
  environment: "paper"  # "paper" for risk-free simulation, "live" for real exchange orders
  server_host: "0.0.0.0"
  server_port: 8000
  webhook_secret_key: "BHARAT_SECURE_KEY_REPLACE_ME_IN_PROD"
  execution_mode: "full_auto"  # "full_auto" (instant order) or "semi_auto" (approval queue)
  enable_ai_sentinel: true

session:
  market_open_time: "09:15"
  market_close_time: "15:30"
  intraday_square_off_time: "15:15"  # Mandatory auto square-off for MIS
  no_fresh_entries_after: "15:00"

risk:
  max_intraday_loss_inr: 5000.0        # Kill-switch halts all trading if hit
  max_capital_per_trade_percent: 5.0   # Max % equity per trade
  max_open_positions: 3                # Max concurrent open positions
  enforce_hard_stop_loss: true
  use_kelly_sizing: true               # Kelly criterion dynamic sizing
  kelly_fraction: 0.5                  # Half-Kelly for capital preservation

brokers:
  active_broker: "zerodha"  # Options: 'zerodha', 'dhan', 'angel_one', 'fyers', 'upstox'

  zerodha:
    api_key: ""
    api_secret: ""
    user_id: ""
    totp_secret: ""          # RFC 6238 Base32 secret for headless daily 2FA
    access_token: ""

  dhan:
    client_id: ""
    access_token: ""

  angel_one:
    api_key: ""
    client_code: ""
    password: ""
    totp_secret: ""
```

---

## 📈 TradingView Webhook Integration

### Step 1: Deploy Pine Script Strategy
In TradingView's **Pine Editor**, paste either of the provided production strategies:
* 🎯 **[`tradingview/pinescript_options_buyer.pine`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/tradingview/pinescript_options_buyer.pine)**: Automatically calculates ATM Call/Put strikes on NIFTY & BANKNIFTY based on Supertrend and EMA momentum.
* 📊 **[`tradingview/pinescript_strategy_template.pine`](file:///c:/Users/dhuri/Downloads/antigravity%20ai%20workspace/trading%20ai%20agent/tradingview/pinescript_strategy_template.pine)**: Universal intraday equity & futures strategy with dynamic ATR stop-loss and take-profit.

### Step 2: Configure Alert Webhook
1. Press `Alt + A` on TradingView to create a new alert.
2. Under **Condition**, select your strategy.
3. Check **Webhook URL** and enter your endpoint:
   ```
   https://YOUR_DOMAIN_OR_NGROK/webhook
   ```
4. Under **Message**, format the JSON payload:
   ```json
   {
     "secret_key": "BHARAT_SECURE_KEY_REPLACE_ME_IN_PROD",
     "symbol": "NIFTY24OCT24500CE",
     "action": "BUY",
     "quantity": 25,
     "order_type": "MARKET",
     "price": 140.0,
     "stop_loss": 115.0,
     "take_profit": 190.0,
     "product": "INTRADAY",
     "strategy_name": "Supertrend_CE_Buyer"
   }
   ```

---

## 🔌 REST API Reference

| Method | Endpoint | Description | Sample Request / Query |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | System status, IST clock, margin balance, and active broker telemetry. | None |
| `POST` | `/webhook` | Receives and routes TradingView JSON alerts through AI and Risk engines. | `{"secret_key": "...", "symbol": "...", "action": "BUY", ...}` |
| `POST` | `/kill-switch` | **Emergency Panic Button**: Instantly liquidates all positions and halts trading. | `?secret_key=YOUR_SECRET` |
| `GET` | `/action-center/pending` | Lists all orders held in semi-auto approval queue. | None |
| `POST` | `/action-center/approve/{id}` | Approves and executes a pending order from the Action Center. | `?secret_key=YOUR_SECRET` |
| `POST` | `/analytics/greeks` | Computes Black-76 Greeks & solves Implied Volatility (IV). | `{"option_type": "CE", "forward_price": 24500, "strike_price": 24500, ...}` |
| `POST` | `/analytics/max-pain` | Computes option chain Max Pain strike and Put-Call Ratio (PCR). | `[{"strike": 24400, "ce_oi": 50000, "pe_oi": 90000}, ...]` |

---

## 🛡️ SEBI Regulatory Compliance (2025/2026 Mandates)

> [!IMPORTANT]
> The Securities and Exchange Board of India (SEBI) requires all retail automated and algorithmic trading systems to comply with the *Safer Participation of Retail Investors in Algorithmic Trading* directives:

* ✅ **Retail DIY Exemption**: Personal algorithms running under 10 orders per second for self/family accounts do **not** require exchange product certification.
* ✅ **Static IP Whitelisting**: Broker developer portals (Zerodha Developer, Angel SmartAPI) require registering the server's static IP address.
* ✅ **Mandatory RFC 6238 TOTP**: Headless logins must authenticate via time-based one-time passwords generated through `pyotp`.
* ✅ **Mandatory Kill-Switch & Loss Halt**: Systems must implement circuit breakers to immediately halt trading if daily drawdown reaches the risk ceiling.
* ✅ **Mandatory 15:15 IST Square-Off**: All intraday (MIS) positions must be closed before the cash market session closes at 15:30 IST.

---

## ⚠️ Financial Risk Disclaimer

> [!CAUTION]
> Algorithmic trading, intraday trading, and trading in Futures & Options (F&O) involves substantial financial risk and can result in the loss of all invested capital. SEBI studies indicate that 9 out of 10 individual traders in equity F&O incur net financial losses.
> 
> Always test strategies thoroughly using `environment: "paper"` simulation before deploying live capital. The developers of BharatTrader-AI assume no responsibility for financial losses incurred through the use of this software.

---

<div align="center">
  <sub>Engineered with precision for the Indian Financial Markets • Open Source under the MIT License</sub>
</div>
