"""Black-Scholes option pricing and implied volatility calculation.

Uses standard BS formula for European options. MO options are European-style
(CFFEX index options).
"""
import math
from math import log, sqrt, exp
from scipy.stats import norm


def _d1(S, K, T, r, sigma):
    """Calculate d1 in Black-Scholes formula."""
    return (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))


def _d2(S, K, T, r, sigma):
    """Calculate d2 in Black-Scholes formula."""
    return _d1(S, K, T, r, sigma) - sigma * sqrt(T)


def bs_price(S, K, T, r, sigma, option_type='call'):
    """Calculate Black-Scholes European option price.

    Args:
        S: Underlying price
        K: Strike price
        T: Time to expiry in years (e.g. 30/365)
        r: Risk-free rate (annual, e.g. 0.02)
        sigma: Volatility (annual, e.g. 0.25)
        option_type: 'call' or 'put'
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        # Intrinsic value for expired options
        if option_type == 'call':
            return max(S - K, 0.0)
        return max(K - S, 0.0)

    d1 = _d1(S, K, T, r, sigma)
    d2 = d1 - sigma * sqrt(T)

    if option_type == 'call':
        return S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
    else:
        return K * exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_vega(S, K, T, r, sigma, option_type='call'):
    """Calculate vega (sensitivity to volatility). Same for calls and puts."""
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    return S * norm.pdf(d1) * sqrt(T)


def bs_iv(price, S, K, T, r, option_type='call', tol=1e-8, max_iter=1000):
    """Calculate implied volatility using Newton-Raphson method.

    Returns:
        Implied volatility (float) or None if convergence fails.
    """
    if T <= 1e-6:
        return None
    if S <= 0 or K <= 0 or price <= 0:
        return None

    # Intrinsic value check
    if option_type == 'call':
        intrinsic = max(S - K * exp(-r * T), 0)
    else:
        intrinsic = max(K * exp(-r * T) - S, 0)

    if price < intrinsic - 0.01:
        # Price below intrinsic — bad data
        return None

    sigma = 0.3  # Initial guess
    for _ in range(max_iter):
        try:
            p = bs_price(S, K, T, r, sigma, option_type)
            v = bs_vega(S, K, T, r, sigma, option_type)
        except (ValueError, OverflowError, ZeroDivisionError):
            return None

        diff = p - price
        if abs(diff) < tol:
            return sigma

        if v < 1e-12:
            # Vega too small, try bisection fallback
            return _bs_iv_bisection(price, S, K, T, r, option_type, tol, max_iter=50)

        sigma = sigma - diff / v

    # Fallback to bisection
    return _bs_iv_bisection(price, S, K, T, r, option_type, tol, max_iter=100)


def _bs_iv_bisection(price, S, K, T, r, option_type='call', tol=1e-8, max_iter=100):
    """Bisection method fallback for IV calculation."""
    sigma_low = 0.001
    sigma_high = 5.0

    for _ in range(max_iter):
        sigma_mid = (sigma_low + sigma_high) / 2.0
        try:
            p = bs_price(S, K, T, r, sigma_mid, option_type)
        except (ValueError, OverflowError):
            sigma_high = sigma_mid
            continue

        if abs(p - price) < tol:
            return sigma_mid

        if p > price:
            sigma_high = sigma_mid
        else:
            sigma_low = sigma_mid

        if sigma_high - sigma_low < tol:
            return sigma_mid

    return None


def bs_greeks(S, K, T, r, sigma, option_type='call'):
    """Calculate option Greeks.

    Returns dict with delta, gamma, theta, vega, rho.
    """
    if T <= 1e-6 or sigma <= 0:
        return {'delta': None, 'gamma': None, 'theta': None, 'vega': None, 'rho': None}

    try:
        d1 = _d1(S, K, T, r, sigma)
        d2 = d1 - sigma * sqrt(T)
        sqrt_T = sqrt(T)
    except (ValueError, ZeroDivisionError):
        return {'delta': None, 'gamma': None, 'theta': None, 'vega': None, 'rho': None}

    pdf_d1 = norm.pdf(d1)
    cdf_d1 = norm.cdf(d1)
    cdf_d2 = norm.cdf(d2)

    if option_type == 'call':
        delta = cdf_d1
        theta = (
            -(S * pdf_d1 * sigma) / (2 * sqrt_T)
            - r * K * exp(-r * T) * cdf_d2
        )
    else:
        delta = cdf_d1 - 1
        theta = (
            -(S * pdf_d1 * sigma) / (2 * sqrt_T)
            + r * K * exp(-r * T) * norm.cdf(-d2)
        )

    theta /= 365.0  # Annual to daily

    gamma = pdf_d1 / (S * sigma * sqrt_T)
    vega = S * pdf_d1 * sqrt_T
    rho = (
        K * T * exp(-r * T) * cdf_d2
        if option_type == 'call'
        else -K * T * exp(-r * T) * norm.cdf(-d2)
    )

    return {
        'delta': delta,
        'gamma': gamma,
        'theta': theta,
        'vega': vega,
        'rho': rho,
    }
