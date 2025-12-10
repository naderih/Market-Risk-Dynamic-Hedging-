"""
hedging_engine.py

This module contains the core logic for the Dynamic Hedging Simulation. 
It mimics the behavior of a trading desk managing a portfolio of derivatives under stress.

Key Responsibilities:
    1.  Portfolio Aggregation: Calculates aggregated Greeks (Delta, Gamma, Vega) for a basket of instruments.
    2.  Hierarchical Hedging Loop: Implements a specific order of operations for re-hedging:
        - First, hedge Gamma (Curvature) using short-dated options.
        - Second, hedge Vega (Volatility) using long-dated options.
        - Third, hedge residual Delta (Direction) using the underlying asset.
    3.  Friction Modeling: Calculates transaction costs (bid-ask spreads) that widen dynamically 
        as volatility increases during the stress scenario.
    4.  Cash Management: Tracks the funding cost (interest paid/earned) on the cash balance 
        required to maintain the hedges, incorporating Credit Spreads.

Classes:
- PortfolioManager: A container for instruments to aggregate risk.
- HedgingSimulation: The time-stepping engine that executes the strategy.

"""

import pandas as pd
import numpy as np

class PortfolioManager:
    def __init__(self):
        self.positions = []

    def add_position(self, instrument, quantity):
        self.positions.append({'instrument': instrument, 'qty': quantity})

    def get_greeks(self, S, vol, current_date, r):
        """
        Aggregates Greeks for all positions in the portfolio.
        Returns a dictionary: {'price', 'delta', 'gamma', 'vega'}
        
            It loops through every trade in the portfolio.
            Calculates Price, Delta, Gamma, and Vega 
            (It passes the current Spot, Vol, Date, and Discount Rate to the instrument to get the answer).
            It sums them all up to tell us the Net Risk of the entire book 
            (e.g., "We are Short 5,000 Delta and Short 2,000 Vega")
        """
        # starting with a baseline dictionary
        greeks = {'price': 0.0, 'delta': 0.0, 'gamma': 0.0, 'vega': 0.0}
        
        for pos in self.positions:
            inst = pos['instrument']
            qty = pos['qty']
            
            # Calculate metrics for this instrument
            greeks['price'] += inst.price(S, current_date, r, vol) * qty
            greeks['delta'] += inst.delta(S, current_date, r, vol) * qty
            greeks['gamma'] += inst.gamma(S, current_date, r, vol) * qty
            greeks['vega']  += inst.vega(S, current_date, r, vol) * qty
                
        return greeks

class HedgingSimulation:
    """
    Our Trader Algo
    Inputs: It takes the Portfolio (from Part 1), the Market Scenario (the crash data), 
    and (optionally) two hedging instruments (a Gamma hedge option and a Vega hedge option).
    it also takes a rehedge interval. 1 means daily rehedging. 
    """
    def __init__(self, portfolio, market_scenario_df, 
                 gamma_hedge_inst=None, 
                 vega_hedge_inst=None, 
                 rehedge_interval = 1):
        
        self.portfolio = portfolio
        self.scenario_df = market_scenario_df
        self.gamma_inst = gamma_hedge_inst
        self.vega_inst = vega_hedge_inst
        self.rehedge_interval = rehedge_interval
        
        # Simulation State
        
        self.cash = 0.0
        self.pos_stock = 0.0
        self.pos_gamma_hedge = 0.0
        self.pos_vega_hedge = 0.0
        
        # Transaction Cost Parameters
        self.base_vol = market_scenario_df['vol'].iloc[0]
        self.stock_spread_bps = 5.0      # Base spread for stock
        self.option_spread_bps = 100.0   # Base spread for options


        # --- PRE-HEDGE LOGIC ---
        """
        The Pre-Hedge:
        Before the simulation starts (Day 0), the portfolio might be extremely risky.
        We run a "Day 0" calculation to buy/sell hedges to make the portfolio Neutral (Risk-Free).
        We assume we borrowed money to pay for these initial hedges, so self.cash starts negative
        """
        
        initial_scenario_row = self.scenario_df.iloc[0]
        S = initial_scenario_row['spot']
        vol = initial_scenario_row['vol']
        date = self.scenario_df.index[0]
        r = initial_scenario_row['sofr']
        
        # 1. Get Initial Risk View
        initial_portfolio_view = PortfolioManager()
        for p in self.portfolio.positions: 
            initial_portfolio_view.add_position(p['instrument'], p['qty'])
        initial_greeks = initial_portfolio_view.get_greeks(S, vol, date, r)
        
        # 2. Establish Gamma Hedge (if instrument provided)
        if self.gamma_inst: # checking if a gamma hedge instrument is provided 
            # calculate the gamma for our gamma hedge instrument
            unit_gamma = self.gamma_inst.gamma(S, date, r, vol) 
            # gamma of the gamma hedge instrument should not be zero 
            if abs(unit_gamma) > 1e-9:
                # calclate how many units of our gamma hedge instruments we need 
                # we have our day 0 gamma, and gamma of the hedge instrument. 
                # we can calculate the gamma hedge position i.e. number of contracts in the gamma hedge instrument
                self.pos_gamma_hedge = -initial_greeks['gamma'] / unit_gamma
        
        # 3. Establish Vega Hedge (if instrument provided)
        if self.vega_inst:
            # 2nd layer: The Gamma hedge we just added above 
            # has its own Vega. We must account for it.
            added_vega_from_gamma_hedge = 0
            if self.gamma_inst: 
                added_vega_from_gamma_hedge = self.pos_gamma_hedge * self.gamma_inst.vega(S, date, r, vol)
            
            # calculate the vega of our vega-hedge instrument 
            unit_vega = self.vega_inst.vega(S, date, r, vol)
            # it must be greater than 0
            if abs(unit_vega) > 1e-9:
                # the position in the vega hedge instrument is determined by our initial position's vega 
                # and our added vega from gall ahedge 
                self.pos_vega_hedge = -(initial_greeks['vega'] + added_vega_from_gamma_hedge) / unit_vega

        # 4. Establish Delta Hedge (The Clean Up)
        # Calculate Delta coming from the base portfolio AND the new hedges
        added_delta_g = 0
        added_delta_v = 0
        
        # calculate added delta from our gamma hedge 
        if self.gamma_inst: 
            added_delta_g = self.pos_gamma_hedge * self.gamma_inst.delta(S, date, r, vol)
        
        # calculate added delta from our vega hedge
        if self.vega_inst: 
            added_delta_v = self.pos_vega_hedge * self.vega_inst.delta(S, date, r, vol)
        
        # now calculate the position in the underlying needed to make the portfolio delta-neutral 
        self.pos_stock = -(initial_greeks['delta'] + added_delta_g + added_delta_v)
        
        #------------------------------------------------------
        #### Ok! portoflio is delta-, gamma-, and vega- hedged
        #------------------------------------------------------
        
        
        # Now we need to calculate our cash position from the hedges we used above:
        # 5. Initialize Cash
        # Assume we borrowed/paid cash to enter these initial long hedge positions
        # and we received cash to enter initial short positions 
        # Logic = n_position * position_price
        if self.gamma_inst: 
            cost_gamma = self.pos_gamma_hedge * self.gamma_inst.price(S, date, r, vol)
        else:
            cost_gamma = 0

        if self.vega_inst: 
            cost_vega = self.pos_vega_hedge * self.vega_inst.price(S, date, r, vol) 
        else: 
            cost_vega = 0
        
        # assuming delta-hedged position 
        cost_stock = self.pos_stock * S
        
        # total cash is negative sum of costs of our gamma, vega, and delta hedge 
        self.cash = -(cost_gamma + cost_vega + cost_stock)

    # class initializer finished 
    # ---------------------------------------------


    def _get_spread_cost(self, notional, current_vol, is_option=False):
        """
        Calculates transaction costs for a specific transaction based on a 'Liquidity Haircut' model.
        notional: 
        Spreads widen proportionally to the increase in volatility.
            Logic: Cost = Size of Trade * Price * (Spread / 2)
            It uses a multiplier based on Volatility.
                If Volatility is 20% (Normal), spread is standard.
                If Volatility spikes to 80% (Panic), the spread widens by 4x.
            This ensures that trading during a crash is much more expensive than trading during calm markets.
        
        When cash is geenrated from Shorting: 
            Assumption: the cash is invested overnight and earns risk-free rate (SOFR).
        When cash is needed for buying: 
            it's borrowed from the market. 
            Assumption: Because the bank has credit risk, they borrow at SOFR + Credit Spread. 
        This helper function calculates the transaction cost for the borrowed cash
        """

        # multiplier scales as volatility grows 
        multiplier = current_vol / self.base_vol
        
        if is_option: 
            base = self.option_spread_bps 
        else:
            base = self.stock_spread_bps
        
        spread_decimal = (base * multiplier) / 10000.0
        
        # total spread cost of the specific hedge trade 
        return abs(notional) * (spread_decimal / 2.0)

    def run(self):
        results = []
        dt = 1/252.0 
        step_counter = 0 
        # now we are ready to go row by row of our sceario
        for date, row in self.scenario_df.iterrows():
            #capture the risk factors at each date 
            S = row['spot']
            vol = row['vol']
            sofr = row['sofr']
            spread = row['credit_spread']

            # 1. Accrue Funding (Interest) on Cash Balance
            # If Cash < 0, we pay (SOFR + Credit Spread). If Cash > 0, we earn SOFR.
            if self.cash < 0:
                rate = sofr + spread 
            else: 
                rate = sofr
            
            # the intrest earned or paid 
            funding = self.cash * rate * dt
            # update the cash position 
            self.cash += funding
            
            # Initialize costs for this step (default 0 if we don't trade i.e rehedging inerval != 1)
            cost_spread_gamma = 0
            cost_spread_vega = 0
            cost_spread_delta = 0
            
            if step_counter % self.rehedge_interval == 0:

                # 2. Construct Current Portfolio View (Base + Existing Hedges)
                # initialize a snapshot portfolio (empty now)
                current_portfolio_view = PortfolioManager()
            
                # update the snapshot view by our positions  
                for p in self.portfolio.positions: 
                    current_portfolio_view.add_position(p['instrument'], p['qty'])
            
                # if we are gamma hedging, add the gamma hedge instruemnt and num of positions to the snapshot
                if self.pos_gamma_hedge != 0: 
                    current_portfolio_view.add_position(self.gamma_inst, self.pos_gamma_hedge)
                # similar for vega 
                if self.pos_vega_hedge != 0: 
                    current_portfolio_view.add_position(self.vega_inst, self.pos_vega_hedge)
            
                # Get Net Greeks before re-balancing: 
                # get_greeks goes over every position in the portfolio 
                # and give us the greek for the whole portfolio
                port_greeks = current_portfolio_view.get_greeks(S, vol, date, sofr)
            
            #----------------------------------------------------------------------------
            # --- TRADING LOGIC CASCADE ---
            # Ok now we have calculated the portfolio greeks. we have the snapshot. 
            # we have the hedge instrument. 
            # we can hedge in order Gamma, Vega, Delta 

            # Step A: Re-Hedge Gamma
                if self.gamma_inst:
                    # calculate gamma of the provided gamma hedge instrument
                    unit_gamma = self.gamma_inst.gamma(S, date, sofr, vol)
                    if abs(unit_gamma) > 1e-9:
                        # Target Net Gamma = 0. The current 'port_greeks' includes existing hedges.
                        # So we need to trade exactly -NetGamma to neutralize it.
                        trade_qty = -port_greeks['gamma'] / unit_gamma
                        
                        # calculate the price for each unit of gamma-hedge instruemnt 
                        price = self.gamma_inst.price(S, date, sofr, vol)
                        # spread cost                  
                        cost_spread_gamma = self._get_spread_cost(trade_qty * price * 100, vol, is_option=True)
                        # update cash account by (spot trade cost + the spread cost)
                        self.cash -= (trade_qty * price) + cost_spread_gamma

                        # update our gamma hedge position 
                        self.pos_gamma_hedge += trade_qty
                        
                        # Ok! our gamma is hedged. we now move up the hedge ladder. 
                        # our gamma hedge added to our vega and to our delta 
                        # so we need to update those two greeks in our snapshot before starting to hedge vega and delta
                        # => Update our Greek view for the next steps (Delta/Vega changed!)
                        port_greeks['vega'] += trade_qty * self.gamma_inst.vega(S, date, sofr, vol)
                        port_greeks['delta'] += trade_qty * self.gamma_inst.delta(S, date, sofr, vol)

                # Step B: Re-Hedge Vega
                # the logic is similar to our gamma hedgin above
                if self.vega_inst:
                    unit_vega = self.vega_inst.vega(S, date, sofr, vol)
                    if abs(unit_vega) > 1e-9:
                        trade_qty = -port_greeks['vega'] / unit_vega
                        
                        price = self.vega_inst.price(S, date, sofr, vol)
                        cost_spread_vega = self._get_spread_cost(trade_qty * price * 100, vol, is_option=True)
                        self.cash -= (trade_qty * price) + cost_spread_vega
                        self.pos_vega_hedge += trade_qty
                        
                        # Update Delta view
                        port_greeks['delta'] += trade_qty * self.vega_inst.delta(S, date, sofr, vol)

                # Step C: Re-Hedge Delta (Final Cleanup)
                # The 'port_greeks' now contains the Delta of the Base Port + Gamma Hedge + Vega Hedge.
                # We need to adjust our Stock position to neutralize this.
                # Total Target Stock = -NetDeltaDerivatives
                target_stock = -port_greeks['delta']
                
                # The trade is the difference between Target and Current underlying hedge 
                stock_trade = target_stock - self.pos_stock
                
                # let's get the spread cost of the hedge trade 
                cost_spread_delta = self._get_spread_cost(stock_trade * S, vol, is_option=False)
                # the effect on cash if from our spot trade + the spread costs 
                self.cash -= (stock_trade * S) + cost_spread_delta
                self.pos_stock = target_stock

            # --- VALUATION & REPORTING (Daily)---
            
            # Value the Base (no hedge) Portfolio
            val_base = PortfolioManager()
            for p in self.portfolio.positions: 
                val_base.add_position(p['instrument'], p['qty'])
            pv_base = val_base.get_greeks(S, vol, date, sofr)['price']
            
            # Value the Hedges
            pv_hedges = 0
            if self.gamma_inst: 
                pv_hedges += self.pos_gamma_hedge * self.gamma_inst.price(S, date, sofr, vol)
            if self.vega_inst: 
                pv_hedges += self.pos_vega_hedge * self.vega_inst.price(S, date, sofr, vol)
            
            pv_hedges += self.pos_stock * S
            # Total P&L = Derivatives + Stock + Cash
            total_pnl = pv_base + pv_hedges + self.cash

            results.append({
                'date': date,
                'spot': S,
                'total_pnl': total_pnl,
                'stock_pos': self.pos_stock,
                'gamma_hedge_pos': self.pos_gamma_hedge,
                'vega_hedge_pos': self.pos_vega_hedge,
                'txn_costs': cost_spread_delta + cost_spread_gamma + cost_spread_vega,
                'funding_cost': funding
            })

            step_counter +=1 

        return pd.DataFrame(results).set_index('date')

