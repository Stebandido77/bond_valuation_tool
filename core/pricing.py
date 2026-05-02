"""
core.pricing
============

Pricing engines.

Two valuation methods are supported:

    1. Yield-based pricing (a flat YTM, optionally bumped by a credit spread).
    2. Curve-based pricing (zero curve + parallel spread).

Both engines operate on the same ``CashFlow`` schedule and produce the same
result type so they can be compared apples-to-apples downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import numpy as np

from .cashflows import CashFlow, accrued_interest
from .curves import ZeroCurve


@dataclass
class PricingResult:
    """Output of a pricing run."""

    valuation_date: date
    dirty_price: float          # PV of remaining cashflows, expressed as %% of notional
    clean_price: float          # dirty - accrued
    accrued: float              # accrued interest, %% of notional
    pv: float                   # PV in currency units (notional * dirty / 100)
    notional: float
    method: str                 # "yield" or "curve"
    ytm: Optional[float] = None # populated when method == "yield"
    used_curve: Optional[str] = None
    spread_bps: float = 0.0


# ---------------------------------------------------------------------------
# Yield-based pricing
# ---------------------------------------------------------------------------
def price_with_yield(
    flows: List[CashFlow],
    valuation_date: date,
    ytm: float,
    frequency: int,
    spread_bps: float = 0.0,
) -> PricingResult:
    """Price a bond using a flat yield-to-maturity.

    The discount factor for a cashflow paid on date ``T`` is

        DF(T) = (1 + (ytm + spread) / m) ** (-m * tau)

    where ``m`` is the coupon frequency and ``tau`` is the time in years
    between the valuation date and the payment date, computed with ACT/365.
    """
    if not flows:
        raise ValueError("No cashflows to price")
    if frequency <= 0:
        raise ValueError("frequency must be positive")

    rate = ytm + spread_bps * 1e-4
    notional = flows[0].notional

    pv_currency = 0.0
    for cf in flows:
        if cf.payment_date <= valuation_date:
            continue
        tau = (cf.payment_date - valuation_date).days / 365.0
        df = (1.0 + rate / frequency) ** (-frequency * tau)
        pv_currency += cf.total * df

    dirty_pct = pv_currency / notional * 100.0
    accrued_pct = accrued_interest(flows, valuation_date) / notional * 100.0
    clean_pct = dirty_pct - accrued_pct

    return PricingResult(
        valuation_date=valuation_date,
        dirty_price=dirty_pct,
        clean_price=clean_pct,
        accrued=accrued_pct,
        pv=pv_currency,
        notional=notional,
        method="yield",
        ytm=ytm,
        spread_bps=spread_bps,
    )


# ---------------------------------------------------------------------------
# Curve-based pricing
# ---------------------------------------------------------------------------
def price_with_curve(
    flows: List[CashFlow],
    valuation_date: date,
    curve: ZeroCurve,
    spread_bps: float = 0.0,
) -> PricingResult:
    """Price a bond by discounting each cashflow with a zero curve.

    A flat ``spread_bps`` is added to every zero rate before computing the
    discount factor. This is enough to model issuer / liquidity spreads on
    top of a benchmark curve.
    """
    if not flows:
        raise ValueError("No cashflows to price")

    notional = flows[0].notional
    shocked = curve.shifted(spread_bps) if spread_bps != 0.0 else curve

    pv_currency = 0.0
    for cf in flows:
        if cf.payment_date <= valuation_date:
            continue
        df = shocked.discount_factor(cf.payment_date)
        pv_currency += cf.total * df

    dirty_pct = pv_currency / notional * 100.0
    accrued_pct = accrued_interest(flows, valuation_date) / notional * 100.0
    clean_pct = dirty_pct - accrued_pct

    return PricingResult(
        valuation_date=valuation_date,
        dirty_price=dirty_pct,
        clean_price=clean_pct,
        accrued=accrued_pct,
        pv=pv_currency,
        notional=notional,
        method="curve",
        used_curve=curve.name,
        spread_bps=spread_bps,
    )


# ---------------------------------------------------------------------------
# YTM solver (Newton-Raphson with bisection fallback)
# ---------------------------------------------------------------------------
def solve_ytm(
    flows: List[CashFlow],
    valuation_date: date,
    target_dirty_price: float,
    frequency: int,
    initial_guess: float = 0.08,
    tol: float = 1e-10,
    max_iter: int = 100,
) -> float:
    """Solve for the yield that reproduces ``target_dirty_price`` (%% of notional).

    Uses Newton-Raphson on the price function with an analytical derivative,
    falling back to bisection if Newton steps misbehave.
    """
    if not flows:
        raise ValueError("No cashflows")
    notional = flows[0].notional
    target_pv = target_dirty_price / 100.0 * notional

    future = [
        cf for cf in flows if cf.payment_date > valuation_date
    ]
    if not future:
        raise ValueError("All cashflows are in the past")

    taus = np.array(
        [(cf.payment_date - valuation_date).days / 365.0 for cf in future]
    )
    amounts = np.array([cf.total for cf in future])

    def pv(rate: float) -> float:
        df = (1.0 + rate / frequency) ** (-frequency * taus)
        return float(np.sum(amounts * df))

    def dpv(rate: float) -> float:
        # d/dy of (1 + y/m)^(-m*t) = -t * (1 + y/m)^(-m*t - 1)
        df_minus = (1.0 + rate / frequency) ** (-frequency * taus - 1.0)
        return float(-np.sum(amounts * taus * df_minus))

    y = initial_guess
    for _ in range(max_iter):
        f = pv(y) - target_pv
        if abs(f) < tol:
            return y
        d = dpv(y)
        if d == 0 or not np.isfinite(d):
            break
        step = f / d
        # damp to keep yield in a sane range
        if abs(step) > 0.5:
            step = 0.5 * np.sign(step)
        y -= step
        if y <= -0.5:
            y = -0.49

    # bisection fallback
    lo, hi = -0.5, 5.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if pv(mid) > target_pv:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < tol:
            return mid
    return 0.5 * (lo + hi)
