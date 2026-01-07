# Quantitative Risk: Dynamic Hedging & Convexity Analysis

## 1. Executive Summary
This repository implements a **Path-Dependent Hedging Simulator** designed to stress-test hedging strategies under extreme liquidity constraints.

While traditional Risk models often focus on Day-1 Greeks, this framework answers the strategic question: **"What happens to a hedge over time when structural constraints (Maturity Mismatches, Risk Limits, Liquidity Dry-ups) collide with a market crash?"**

The core analysis focuses on the **"Convexity Trap"**—the structural failure that occurs when hedging long-dated liabilities with short-dated assets—and the "Luck vs. Skill" attribution of risk limits.

---

## 2. Key Analysis Modules (`main_narrative_intuition.ipynb`)

This notebook contains the primary narrative arc, broken down into three targeted experiments:

### Experiment 1: Model Validation (Taylor Expansion)
* **Objective:** Verify that the simulation engine's P&L attribution matches theoretical pricing models.
* **Methodology:** Compares the simulated P&L against a second-order Taylor Expansion ($\text{Delta} + \frac{1}{2}\text{Gamma} + \text{Vega}$).
* **Result:** Confirms the engine accurately captures Greeks, isolating the residual "Cross-Gamma" noise.

### Experiment 2: The "Convexity Trap" (Maturity Mismatch)
* **The Scenario:** A 5-Year Liability (Short Put) hedged with a 1-Year Asset (Long Put).
* **The Math:** * **Vega:** Scales with $\sqrt{T}$. To neutralize the 5Y Vega, we must buy **~2.2x** the notional in 1Y options.
    * **Gamma:** Scales with $1/\sqrt{T}$. The 1Y option is inherently more convex ("nervous").
    * **The Trap:** By leveraging quantity (2.2x) on a high-gamma instrument, we create a massive **Net Gamma Imbalance**.
* **Outcome:** The simulation proves that while the hedge works on paper (Gross P&L), the **Transaction Costs** (Churn) required to manage the 1Y Gamma creates a loss larger than the unhedged portfolio.

### Experiment 3: Risk Limits (Strict vs. "Lazy" Hedging)
* **The Question:** "Can we reduce churn by using Risk Limits (only re-hedging when $|\Delta| > \text{Limit}$?)"
* **The Finding:** * **Transaction Costs:** Savings were negligible (~$150) because the crash severity overwhelmed the limit.
    * **Net P&L:** Improved by ~$70,000.
    * **The Insight:** The improvement was **not** due to efficiency. It was **Path Dependent Luck**. By delaying the hedge ("Laziness"), the model effectively carried a short position overnight during a crash. In a V-shaped recovery, this same strategy would have resulted in maximum loss.

---

## 3. Technical Architecture

### A. The Engine (`src/hedging_engine.py`)
A discrete-event simulator that manages the lifecycle of the portfolio. Key features include:
* **Delta Thresholding:** Allows for "Lazy Hedging" simulation via the `delta_limit` parameter.
* **Dynamic Spreads:** Bid-Ask spreads are not static; they widen endogenously based on the Volatility regime (`Spread_Current = Spread_Base * Vol_Ratio`).
* **Funding Topology:** Separates "Cash Proceeds" (earning SOFR) from "Margin Loans" (paying SOFR + Credit Spread), capturing the cost of liquidity squeezes.

### B. The Market Environment (`src/market_env.py`)
Generates coherent stress scenarios where Spot, Volatility, and Rates move in correlated feedback loops.
* **Inverse Correlation:** Spot drops trigger Volatility spikes (Leverage Effect).
* **Curve Dynamics:** Simulates steepeners/flatteners by shocking Short (2Y) and Long (10Y) rates independently.

---

## 4. Project Structure

```text
market-risk-dynamic-hedging/
│
├── main_narrative_intuition.ipynb  # [NEW] The core analysis: Mismatch, Limits, and Attribution.
├── main.ipynb                      # Legacy dashboard for general Taper Tantrum scenarios.
│
└── src/
    ├── hedging_engine.py           # The Logic Core: Greeks, Re-balancing, P&L Attribution.
    ├── instruments.py              # Pricing Models: Black-Scholes and Yield Curve interpolation.
    ├── market_env.py               # Scenario Generator: Feedback loops and historical calibration.

```

## 5. Strategic Roadmap (Future Work)
Based on the findings in this PoC, the following modules are proposed for future development:

**Portfolio Aggregation:** Extending the engine to handle multi-instrument portfolios rather than single-option liabilities.

**Expected Shortfall (ES) Optimization:** Replacing mechanical Delta-Hedging with a "Variance vs. Cost" optimizer to mathematically solve the trade-off between tracking error and transaction costs.

**OTM Hedging Analysis:** Testing the cost-efficiency of Out-of-the-Money put spreads vs. At-the-Money linear hedges.

### 6. Disclaimer
This project is a quantitative research Proof of Concept. The scenarios and pricing models are simplified for performance and demonstration purposes.