# Market Risk Dynamic Hedging & Stress Testing Framework (PoC)

## 1. Executive Summary
This repository serves as a **Proof of Concept (PoC)** for a modernized Market Risk stress testing framework. Unlike traditional VaR models that often rely on instantaneous shocks, this framework simulates **Path-Dependent Risks** over a multi-day horizon.

The core objective is to quantify the **"Cost of Survival"**—the losses incurred from re-hedging a portfolio during a liquidity crisis, driven by widening bid-ask spreads, volatility spikes, and funding squeezes.

## 2. Technical Methodology & Nuances

### A. The Feedback Loop (Volatility & Liquidity)
Standard stress tests often shock Spot and Volatility independently. This framework models the **endogenous relationship** between them:
*   **Inverse Correlation:** As Spot prices drop, Volatility is programmed to spike (the "Leverage Effect").
*   **Liquidity Haircuts:** Transaction costs are not static. The engine dynamically widens the Bid-Ask Spread proportional to the volatility spike:
    `Spread_Current = Spread_Base * (Vol_Current / Vol_Base)`

### B. Multi-Curve Dynamics
To accurately price Swaps and Options under stress, the `MarketEnvironment` explicitly separates the yield curve into three components:
1.  **Overnight (SOFR):** Drives the Floating Leg of swaps and Option Discounting.
2.  **Short Rate (2Y):** Drives the front-end of the curve expectation.
3.  **Long Rate (10Y):** Drives the long-end (Duration/Inflation).

This allows for the testing of complex curve shapes, such as **Bear Flatteners** (Fed hikes, long end lags) or **Bear Steepeners** (Term premium blowout).

### C. The Hedging Engine (P&L Attribution)
The simulation tracks three distinct sources of P&L leakage often missed in static tests:
1.  **Gamma Bleed:** The loss incurred by "Buying High, Selling Low" to maintain a Delta-Neutral position in a Short Gamma portfolio.
2.  **Transaction Costs:** The realized cost of crossing the spread during re-balancing.
3.  **Funding Liquidity Risk:** The simulation accounts for **Credit Spreads**. When the portfolio borrows cash to fund a hedge, it pays `SOFR + CreditSpread`. In a crisis (e.g., Repo Spike), this funding cost explodes, simulating a "Cash Squeeze."

---

## 3. Project Structure

```text
market-risk-dynamic-hedging/
│
├── main.ipynb            # The Presentation Layer. Runs the Taper Tantrum simulation and visualizes P&L.
│
└── src/
    ├── market_env.py     # Scenario Generator. Contains the "Historical Library" (2013, 2016, 2019, 2020, 2022, 2025) and Custom Engine.
    ├── instruments.py    # Pricing Models. Implements Black-Scholes for Options and Interpolated Zero-Curves for Swaps.
    ├── hedging_engine.py # The Logic Core. Simulates the trader's daily re-hedging logic, P&L, and cash management.
```
### 4. Scenario Library

The `MarketEnvironment` class includes presets for historical and hypothetical stress events:

*   **`taper_tantrum_2013`:** A classic **Bear Steepener**. Short rates stay anchored, but Long rates and Term Premia explode. Liquidity spreads widen moderately.
*   **`repo_crisis_2019`:** A **Plumbing Dislocation**. Overnight SOFR/Repo rates spike aggressively while the rest of the curve lags. Tests the portfolio's sensitivity to funding costs.
*   **`covid_crash_2020`:** A **Deflationary Bust**. Equities crash, Volatility explodes, and Rates collapse to zero.
*   **`liberation_day_2025` (Hypothetical):** A **Stagflation/Trade War** scenario. Models a breakdown in correlations where Rates rise (Inflation defense) while Equities fall (Growth shock), combined with a blowout in Credit Spreads.

---

## 5. Visualizing the Output

Running `main.ipynb` generates a dashboard with three critical panels:

### Panel 1: Hedged vs. Unhedged P&L
*   **Red Line (Unhedged):** Shows the catastrophic loss of a "Short Put" position in a crash.
*   **Blue Line (Hedged):** Shows the mitigated profile. However, the line drifts downward over time. This drift represents the **Gamma Bleed**—the unavoidable cost of hedging curvature in a volatile market.

### Panel 2: Transaction Costs (Liquidity)
*   **Black Line:** The Bid-Ask spread (in bps). Notice it rises as Volatility increases.
*   **Orange Bars:** The daily realized transaction cost. This quantifies the "Liquidity Tax" paid to the market to exit risk.

### Panel 3: Funding Costs (Credit Squeeze)
*   **Purple Bars:** The daily interest paid/earned on the cash account.
*   **Green Line:** The Credit Spread.
*   **Interpretation:** In scenarios like the **Repo Crisis**, high Credit Spreads cause a "Funding Drag," significantly eroding returns on levered positions.
