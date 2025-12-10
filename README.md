# Market Risk Dynamic Hedging & Stress Testing Framework (PoC)

## 1. Executive Summary
This repository serves as a **Proof of Concept (PoC)** for a modernized Market Risk stress testing framework. It moves beyond static "instantaneous shock" models (like standard VaR) to capture **Path-Dependent Risks** and **Liquidity Feedback Loops**.

The core objective is to quantify the **"Cost of Survival"**—the realized P&L erosion caused by re-hedging a portfolio during a market crisis, driven by widening bid-ask spreads, volatility spikes, and funding squeezes.

## 2. Key Financial Concepts Modeled

### A. The Volatility-Liquidity Feedback Loop
Standard stress tests often shock Spot and Volatility independently. This engine models the endogenous relationship between them:
*   **Inverse Correlation:** As Spot prices drop, Volatility is programmed to spike.
*   **Dynamic Spreads:** Transaction costs are not static. The engine calculates a "Liquidity Haircut," widening the Bid-Ask Spread proportionally to the volatility spike.

### B. Maturity Bucketing & Curve Risk
The framework treats time-to-maturity as a dynamic variable attached to each instrument, allowing for the testing of **Term Structure** risks:
*   **Gamma Mismatch:** Captures the risk of hedging long-dated liabilities (Low Gamma) with short-dated assets (High Gamma).
*   **Vega Convexity:** Demonstrates why "Netting Vega" across different tenors fails during a crash.

### C. The Funding Squeeze
The simulation explicitly tracks the **Cash Balance** required to maintain the hedge.
*   **Shorting Stock:** Generates cash, earning the Risk-Free Rate (SOFR).
*   **Borrowing Cash:** If the strategy requires buying assets (e.g., hedging a Short Call), the desk must borrow at `SOFR + Credit Spread`.
*   **Stress Impact:** In scenarios like the **2019 Repo Crisis**, this reveals how a spike in funding rates can erode P&L even if the Delta hedge is perfect.

---

## 3. Simulation Experiments

The `main.ipynb` notebook runs three specific experiments to stress test common hedging assumptions:

### Experiment 1: The "Gamma Bleed" (Baseline)
*   **Scenario:** Spot drops 40% over 20 days; Volatility triples.
*   **Strategy:** Daily Delta-Hedging of a Short 1Y Put.
*   **Insight:** Even with daily rebalancing, the portfolio suffers significant losses due to **Gamma Bleed** (selling low/buying high) and the accumulation of transaction costs in a widening-spread environment.

### Experiment 2: The "Widowmaker" (Maturity Mismatch)
*   **Scenario:** Hedging a **5-Year Liability** (Short Put) using **1-Year Assets** (Long Puts).
*   **Strategy:** Neutralize initial Vega.
*   **Insight:** To match the high Vega of the 5Y option, the model must buy ~3x the notional in 1Y options. When the crash occurs, the explosive Gamma of the 1Y hedge leads to massive over-hedging and transaction costs, causing losses to **double** compared to a simple Delta hedge. This validates the need for strict **Tenor Bucketing**.

### Experiment 3: Hedging Frequency (Daily vs. Weekly)
*   **Scenario:** Comparing re-hedging intervals during a monotonic crash.
*   **Insight:** Counter-intuitively, **Weekly** hedging incurred *higher* transaction costs than Daily hedging in this specific scenario. By waiting 5 days to re-hedge, the model was forced to execute massive block trades exactly when volatility (and spreads) had peaked. This highlights the **Liquidity Feedback Loop**—lazy hedging can be expensive if you are forced to trade into a panic.

---

## 4. Project Structure

```text
market-risk-dynamic-hedging/
│
├── main.ipynb            # The Dashboard. Runs the simulations and visualizes P&L/Greeks.
│
└── src/
    ├── market_env.py     # Scenario Generator. Creates daily time-series for Spot, Vol, SOFR, and Spreads using pandas Business Dates.
    ├── instruments.py    # Pricing Engine. Implements Black-Scholes with dynamic time-to-maturity calculation (ACT/365).
    ├── hedging_engine.py # The Logic Core. Simulates the trader's daily re-hedging logic, Greeks aggregation, and cash management.
```

## 5. Technical Implementation Details

*   **Object-Oriented Design:** Instruments are stateless objects that calculate their own risk metrics based on the simulation environment's current date and state.
*   **Vectorization:** Market scenarios are generated as Pandas DataFrames, allowing for efficient iteration and state tracking.
*   **Funding Logic:** The engine applies asymmetric interest rates—earning the risk-free rate on positive cash, but paying `RiskFree + CreditSpread` on negative balances.

---

## 6. Future Enhancements for Enterprise Scale

*   **Grid Computing:** For a bank-wide book (thousands of trades), the `get_greeks` loop would be parallelized or replaced with a Taylor Expansion approximation for speed.
*   **Data Lineage:** Production implementation would require tight integration with the Finance/P&L system to ensure the "Day 0" snapshot matches official books.
