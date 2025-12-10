"""
market_env.py

This module defines the "Market Environment" generator for the stress testing simulation.
It is responsible for constructing time-series data for multiple risk factors under stress conditions.

Key Responsibilities:

    1.  Scenario Generation: Creates daily time-series for Spot Prices, Volatility, Interest Rates (SOFR), 
    and Credit Spreads based on user-defined shock parameters.

    2.  Volatility Feedback Loop: Models the "Leverage Effect" (Inverse correlation), where a drop in 
    spot prices triggers an endogenous spike in volatility, widening bid-ask spreads in the hedging engine.

    3.  Time Management: Uses pandas Business Date ranges (Monday-Friday) to simulate realistic 
    trading calendars.

    4.  Historical Library: Contains preset configurations mimicking famous market crashes 
    (e.g., Taper Tantrum 2013) for benchmarking.

Classes:
- MarketEnvironment: The factory class for generating scenario DataFrames.
"""

import numpy as np
import pandas as pd

class MarketEnvironment:
    def __init__(self, 
                 spot_start=100.0, 
                 vol_start=0.20, 
                 sofr_start=0.04, 
                 spread_start=0.01):
        
        # current market condition. values to be shocked:
        self.S0 = float(spot_start)
        self.sigma0 = float(vol_start)
        self.r0 = float(sofr_start)
        self.cs0 = float(spread_start)

    def simulate_scenario(self, start_date, num_days, 
                          spot_ret, vol_mult, 
                          d_sofr, d_spread):
        """
        Generates a daily time series of market variables.

        :param start_day: when does the shcok begin? 
        :param num_days: for how many days is the shock scenario evolving? 
        :param spot_ret: Total % return of Spot (e.g., -0.10 for -10%)
        :param vol_mult: Volatility Multiplier (e.g., 2.0 means Vol increases by a factor of 2.0 if spot drops)
        :param d_sofr: Change in the SOFR rate, used for discounting 
        :param d_spread: Change in Credit Spread

        """
        # Generate Business Days (skip weekends)
        dates = pd.bdate_range(start=start_date, periods=num_days + 1)
        steps = len(dates)
        
        # Initialize Arrays
        spot = np.zeros(steps)
        vol = np.zeros(steps)
        sofr = np.zeros(steps)
        spread = np.zeros(steps)
        
        # Set Start Values 
        spot[0] = self.S0
        vol[0] = self.sigma0
        sofr[0] = self.r0
        spread[0] = self.cs0
        
        # Daily Increments
        spot_daily_ret = spot_ret / num_days
        r_sofr_step = d_sofr / num_days
        cs_step = d_spread / num_days
        
        current_spot = self.S0
        
        for i in range(1, steps):
            # 1. Evolve Spot
            current_spot = current_spot * (1 + spot_daily_ret)
            spot[i] = current_spot
            
            # 2. Evolve Rates & Spreads
            sofr[i] = sofr[i-1] + r_sofr_step
            spread[i] = spread[i-1] + cs_step
            
            # 3. Evolve Vol (Feedback Loop)
            # Logic: If Spot Drops, Vol Increases (Panic). 
            # the increase fator is emasured based on the drop from the price at the onset 
            pct_drop = (self.S0 - current_spot) / self.S0
            if pct_drop > 0: 
                vol[i] = self.sigma0 * (1 + (pct_drop * vol_mult))
            else:
                # If market rallies, vol stays flat or decays slightly
                vol[i] = max(0.05, self.sigma0 * 0.95) 

        return pd.DataFrame({
            'date': dates,
            'spot': spot,
            'vol': vol,
            'sofr': sofr,
            'credit_spread': spread
        }).set_index('date')
        
    # ==========================================
    # PRESET SCENARIOS (The "Library")
    # ==========================================
    def taper_tantrum_2013(self, start_date, days = 20):
        """
        Scenario: Bear Steepener.
        Narrative: Fed threatens to stop buying. Short end anchored, Long end explodes.
        """
        return self.simulate_custom_scenario(
            start_date = start_date, 
            num_days = days,
            spot_ret = -0.05,       # Equities drop slighlty 
            vol_mult = 1.5,         # Vol up moderately 
            d_sofr=0.0000,          # Fed held Overnight rates at 0% (d_sofr=0), but 10Y exploded
            d_spread = 0.005        # Repo/Credit spreads widen 50bps 
        )
    
    def trump_reflation_2016(self, start_date, days = 20):
        """
        Scenario: Bullish Bear Steepener.
        Narrative: Growth/Inflation expectations rise. Investors dump Long Duration Ts. 
        Equities Rally.
        """
        return self.simulate_scenario(
            start_date = start_date,
            num_days = days, 
            spot_ret = 0.10,        # Equities Rally 10% over days
            vol_mult = 0.0,         # Vol flat/down
            d_sofr = 0.0000,
            d_spread = -0.0010      # Spreads tighten 
        )

    def repo_crisis_2019(self, start_date, days = 5):
        """
        Scenario: Plumbing Break / Dislocation of Reps and FF rates.
        Narrative: Reserve scarcity. Short rates (Repo) spike violently.
        """
        return self.simulate_scenario(
            start_date = start_date,
            num_days = days,
            spot_ret = -0.02,           # equity market is mildly spooked
            vol_mult = 2.0,             # Vol spike due to liquidity fear 
            d_sofr=0.0500,              # SOFR spiked MASSIVELY (d_sofr=0.05)
            d_spread = 0.0300           # Spreads blow out 300 bps
        )
    
    def covid_crash_2020(self, start_date, days = 20):
        """
        Scenario: Deflationary Bust.
        Narrative: Dash for cash. Everything crashes. Rates to zero.
        """
        return self.simulate_custom_scenario(
            start_date = start_date,
            num_days = days, 
            spot_ret = -0.30,           # Equities crash 30%
            vol_mult = 4.0,             # Vol explodes (VIX 80)
            d_sofr = -0.0150,
            d_spread = 0.04             # credit spreads explode +400bps
        )
    
    def inflation_shock_2022(self, start_date , days = 20):
        """
        Scenario: Bear Flattener.
        Narrative: Fed hikes to kill inflation. Curve inverts. 
                    Fed will fight inflation at whatever the cost 
        """
        return self.simulate_scenario(
            start_date = start_date,
            num_days = days, 
            spot_ret = -0.15,           # Tech/Growth crash 
            vol_mult = 1.5,             # Vol spikes
            d_sofr = 0.0150,
            d_spread = 0.0050           # spreads widen moderately
        )
    
    def liberation_day_2025(self, start_date, days = 10):
        """
        Scenario:  Tariff Stagflation.
        Narrative: Inflation Up, Rates Up, Spreads Up, Growth Down.
        """
        return self.simulate_scenario(
            start_date = start_date,
            num_days = days, 
            spot_ret = -0.15,           # Equities frop 
            vol_mult = 2.0,             # Vol spikes 
            d_sofr=0.0025,              # Fed holds
            d_spread = 0.0200           # Importers, Exporters Credit Spread blow out 200 bps
        )
    
