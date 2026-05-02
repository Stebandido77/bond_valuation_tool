"""
core.risk_metrics
=================

Risk metrics for fixed income instruments.

The metrics implemented here follow the textbook definitions used by most
front-office systems:

    DV01            =  -dPV/dy         (per 1 bp)
    Macaulay Dur.   =  Σ t_i · w_i      with w_i = PV(CF_i) / PV
    Modified Dur.   =  Macaulay / (1 + y/m)
    Convexity       =  Σ t_i · (t_i + 1/m) · w_i / (1 + y/m)^2

For curve-based pricing, DV01 is computed numerically by reshocking the
curve and revaluing — which is exactly what trading systems do, and the
only consistent way to handle non-flat curves and spreads.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

import numpy as np

from .cashflows import CashFlow
from .curves import ZeroCurve
from .pricing import price_with_curve, price_with_yield


@dataclass
class RiskMetrics:
    dv01: float                 # currency units per 1 bp
    macaulay_duration: float    # years
    modified_duration: float    # years
    convexity: float            # years²
    pv01: float                 # alias for DV01 (some systems differentiate)


# ---------------------------------------------------------------------------
# Yield-based risk
# ---------------------------------------------------------------------------
def yield_risk_metrics(
    flows: List[CashFlow],
    valuation_date: date,
    ytm: float,
    frequency: int,
) -> RiskMetrics:
    """Analytical risk metrics under a flat YTM."""
    future = [cf for cf in flows if cf.payment_date > valuation_date]
    if not future:
        return RiskMetrics(0.0, 0.0, 0.0, 0.0, 0.0)

    taus = np.array(
        [(cf.payment_date - valuation_date).days / 365.0 for cf in future]
    )
    amounts = np.array([cf.total for cf in future])
    df = (1.0 + ytm / frequency) ** (-frequency * taus)
    pv_components = amounts * df
    pv = float(pv_components.sum())
    if pv <= 0:
        return RiskMetrics(0.0, 0.0, 0.0, 0.0, 0.0)

    weights = pv_components / pv
    macaulay = float((taus * weights).sum())
    modified = macaulay / (1.0 + ytm / frequency)
    convex = float(
        (taus * (taus + 1.0 / frequency) * weights).sum()
        / (1.0 + ytm / frequency) ** 2
    )

    # DV01 ≈ modified duration * PV * 1bp
    dv01 = modified * pv * 1e-4
    return RiskMetrics(
        dv01=dv01,
        macaulay_duration=macaulay,
        modified_duration=modified,
        convexity=convex,
        pv01=dv01,
    )


# ---------------------------------------------------------------------------
# Curve-based risk
# ---------------------------------------------------------------------------
def curve_risk_metrics(
    flows: List[CashFlow],
    valuation_date: date,
    curve: ZeroCurve,
    spread_bps: float = 0.0,
    bump_bps: float = 1.0,
) -> RiskMetrics:
    """Numerical risk metrics by central-difference reshock of the curve."""
    base = price_with_curve(flows, valuation_date, curve, spread_bps)
    up = price_with_curve(flows, valuation_date, curve.shifted(bump_bps), spread_bps)
    dn = price_with_curve(flows, valuation_date, curve.shifted(-bump_bps), spread_bps)

    # central difference -> sensitivity per 1bp
    dv01 = -(up.pv - dn.pv) / (2.0 * bump_bps)
    convex = (up.pv + dn.pv - 2.0 * base.pv) / (bump_bps * 1e-4) ** 2 / base.pv \
        if base.pv > 0 else 0.0

    # approximate durations from DV01
    pv = base.pv
    if pv <= 0:
        return RiskMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
    modified = dv01 / (pv * 1e-4)
    # Macaulay can't be recovered without a yield reference; we use the
    # cashflow-weighted time as a robust proxy under the curve.
    future = [cf for cf in flows if cf.payment_date > valuation_date]
    taus = np.array([(cf.payment_date - valuation_date).days / 365.0 for cf in future])
    pvs = np.array([
        cf.total * curve.shifted(spread_bps).discount_factor(cf.payment_date)
        for cf in future
    ])
    macaulay = float((taus * pvs).sum() / pvs.sum()) if pvs.sum() > 0 else 0.0

    return RiskMetrics(
        dv01=dv01,
        macaulay_duration=macaulay,
        modified_duration=modified,
        convexity=convex,
        pv01=dv01,
    )


# ---------------------------------------------------------------------------
# Bucket / Key-rate DV01
# ---------------------------------------------------------------------------
def bucket_dv01(
    flows: List[CashFlow],
    valuation_date: date,
    curve: ZeroCurve,
    spread_bps: float = 0.0,
    bump_bps: float = 1.0,
) -> Dict[str, float]:
    """Per-pillar DV01.

    Returns a mapping ``tenor -> DV01`` where DV01 is the change in PV
    (currency units) for a 1-bp shock isolated to that pillar.
    """
    base = price_with_curve(flows, valuation_date, curve, spread_bps)
    out: Dict[str, float] = {}
    for p in curve.points:
        up = price_with_curve(
            flows, valuation_date, curve.bucket_shifted(p.days, bump_bps), spread_bps
        )
        out[p.tenor] = -(up.pv - base.pv) / bump_bps
    return out


# ---------------------------------------------------------------------------
# Scenario shocks
# ---------------------------------------------------------------------------
def parallel_scenarios(
    flows: List[CashFlow],
    valuation_date: date,
    curve: ZeroCurve,
    bps_list: List[float],
    spread_bps: float = 0.0,
) -> Dict[float, float]:
    """Return ``{shock_in_bps -> dirty_price}`` for a set of parallel shocks."""
    out: Dict[float, float] = {}
    for s in bps_list:
        res = price_with_curve(flows, valuation_date, curve.shifted(s), spread_bps)
        out[float(s)] = res.dirty_price
    return out
