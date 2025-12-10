"""
instruments.py

This module defines the financial instruments used in the market risk stress testing simulation.
It encapsulates the pricing logic (Black-Scholes-Merton) and risk sensitivities (Greeks).

Key Responsibilities:
1.  **Contract Definition**: Stores static data like Strike Price and Expiry Date.
2.  **Dynamic Pricing**: Calculates Fair Value based on current market conditions (Spot, Vol, Rates).
3.  **Risk Metrics**: Calculates Delta, Gamma, and Vega for the Hedging Engine.
4.  **Time Management**: Handles day-count conventions (ACT/365) to determine remaining time to maturity  
based on the simulation's current date.

Classes:
- EuropeanOption: Represents a standard vanilla option contract.
"""


import numpy as np 
from scipy.stats import norm 
import pandas as pd 

class EuropeanOption : 
    def __init__(self, strike, expiry_date, option_type = 'call'):
        self.strike = strike
        self.expiry_date = pd.to_datetime(expiry_date)
        self.option_type = option_type.lower()
    
    # the user gives the current date and this method will calculate time to maturity
    # the output from this method will be efd to .price() and greek methods as time to expiry 
    def get_time_to_maturity(self, current_date):
        current_date = pd.to_datetime(current_date)

        #calculate time to maturity in days 
        days_remaining = (self.expiry_date - current_date).days

        # if expired 
        if days_remaining < 0.0: 
            return 0.0
        
        # convert to years (ACT/365 convention)
        return days_remaining / 365 
    

    def _calculate_d1_d2(self, S, T, r, sigma):
        """Internal helper for Black-Scholes d1/d2 terms."""
        if T <= 1e-6: 
            return 0.0, 0.0
        d1 = (np.log(S / self.strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return d1, d2
    

    def price(self, S, current_date, r, sigma):
        
        """Calculates the theoretical price using Black-Scholes.
        :param S: Spot price of the underlying
        :param current_date: the evalution date 
        :param r: Risk-free interest rate (0.05 for 5%)
        :param sigma: Volatility (e.g. 0.2 for 20%)
        """
        
        T = self.get_time_to_maturity(current_date)
        
        if T <= 1e-6:
            # Intrinsic Value at expiry
            if self.option_type == 'call':
                return max(0.0, S - self.strike)
            else:
                return max(0.0, self.strike - S)
        
        d1, d2 = self._calculate_d1_d2(S, T, r, sigma)
        
        if self.option_type == 'call':
            price = S * norm.cdf(d1) - self.strike * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = self.strike * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
        return price


    def delta(self, S, current_date, r, sigma):
        """Calculates Delta (Sensitivity to Spot)."""
        # calculate time to mat.
        T = self.get_time_to_maturity(current_date)
        
        if T < 1e-6:
            # At expiry, Delta is 1 if the option is ITM and it's zero 0 if OTM:
            if self.option_type == 'call':
                return 1.0 if S > self.strike else 0.0
            else:
                return -1.0 if S < self.strike else 0.0
        
        d1, _ = self._calculate_d1_d2(S, T, r, sigma)
        
        if self.option_type == 'call':
            # N(d1)
            return norm.cdf(d1)
        else:
            # N(d1) - 1
            return norm.cdf(d1) - 1.0


    def gamma(self, S, current_date, r, sigma):
        """
        Calculates Gamma (Sensitivity of Delta to Spot).
        """
        
        T = self.get_time_to_maturity(current_date)
    
        # Gamma explodes at expiry when ATM, 
        # but is 0 or clsoe to zero when not ATM. 
        # For simulation stability, we set it to zero at expiry
        if T < 1e-6: 
            return 0.0  
        d1, _ = self._calculate_d1_d2(S, T, r, sigma)

        # Gamma Formula : N'(d1) / ( S* sigma * sqrt(T))

        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        return gamma 


    def vega(self, S, current_date, r, sigma):
        """Calculates Vega (Sensitivity to Volatility)."""
        T = self.get_time_to_maturity(current_date)

        if T <= 1e-6: 
            return 0.0
        
        d1, _  = self._calculate_d1_d2(S,T, r, sigma)

        # Vega Formula: S * sqrt(T) * N'(d1)
        # Raw value is used for math 

        vega = S * np.sqrt(T) * norm.pdf(d1)

        # scalin to be "per 1% change" 
        return vega / 100.0        
