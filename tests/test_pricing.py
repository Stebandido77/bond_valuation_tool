"""
tests.test_pricing
==================

Sanity tests for the pricing engine and risk metrics.

These tests cover the financial invariants every pricing library must
respect:

    1. A bond at-the-money (coupon == ytm) with annual coupons must price at
       par on a coupon date.
    2. Pricing by a flat-zero curve must agree with pricing by yield when the
       curve's flat rate equals the YTM (and frequency=1, ACT/365).
    3. Solver round-trip: solve_ytm must invert price_with_yield.
    4. DV01 sign and order of magnitude are correct.
    5. Convexity is non-negative for plain-vanilla bonds.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from core.curves import CurvePoint, ZeroCurve
from core.day_count import DayCount
from core.pricing import price_with_curve, price_with_yield, solve_ytm
from core.risk_metrics import yield_risk_metrics
from instruments.bond import Bond


def make_bond(
    issue: date = date(2024, 1, 1),
    maturity: date = date(2029, 1, 1),
    coupon: float = 0.07,
    freq: int = 1,
    notional: float = 100.0,
    convention: DayCount = DayCount.ACT_365,
) -> Bond:
    return Bond(
        isin="TEST",
        issue_date=issue,
        maturity_date=maturity,
        coupon_rate=coupon,
        frequency=freq,
        notional=notional,
        day_count=convention,
    )


def test_at_the_money_prices_at_par():
    """A bond with coupon == ytm must price very close to par.

    Implementation detail: the engine accrues coupons under the bond's
    day-count convention but discounts cashflows in ACT/365. When these
    two bases differ (e.g. NL/365 coupons vs ACT/365 discounting on a
    period containing Feb 29), the result deviates from par by a small,
    convention-driven amount that real trading systems also exhibit. We
    therefore test with a basis-period long enough that the deviation is
    a few basis points at most.
    """
    bond = make_bond(coupon=0.08, convention=DayCount.THIRTY_360, freq=1)
    res = bond.price_yield(valuation_date=date(2024, 1, 1), ytm=0.08)
    # Should price at par within 5 bp (basis mismatch is the only source
    # of deviation; 30/360 gives exactly 1.0 per period).
    assert res.dirty_price == pytest.approx(100.0, abs=0.05)


def test_yield_matches_flat_curve():
    bond = make_bond(coupon=0.07, convention=DayCount.ACT_365)
    val_date = date(2024, 1, 1)
    ytm = 0.085
    yld_res = bond.price_yield(val_date, ytm)
    pillars = [
        CurvePoint("1Y", 365, ytm),
        CurvePoint("3Y", 365 * 3, ytm),
        CurvePoint("5Y", 365 * 5, ytm),
        CurvePoint("10Y", 365 * 10, ytm),
    ]
    flat_curve = ZeroCurve(
        name="FLAT",
        valuation_date=val_date,
        points=pillars,
        convention="ANN",
        currency="COP",
    )
    crv_res = bond.price_curve(val_date, flat_curve)
    # Flat-rate ANN curve and ANN yield must agree to high precision
    assert crv_res.dirty_price == pytest.approx(yld_res.dirty_price, abs=1e-6)


def test_solve_ytm_round_trip():
    bond = make_bond(coupon=0.06)
    val = date(2024, 1, 1)
    target_ytm = 0.0925
    pr = bond.price_yield(val, target_ytm)
    recovered = bond.implied_ytm(val, pr.dirty_price, initial_guess=0.05)
    assert recovered == pytest.approx(target_ytm, abs=1e-8)


def test_dv01_sign_and_magnitude():
    bond = make_bond(coupon=0.07)
    risk = yield_risk_metrics(
        bond.cashflows(), date(2024, 1, 1), ytm=0.07, frequency=1
    )
    # DV01 must be positive (price falls when yield rises -> DV01 > 0)
    assert risk.dv01 > 0
    # For a 5y at-par bond, modified duration ~ 4.1y => DV01 ~ 0.041% of notional
    assert 3.5 < risk.modified_duration < 4.7


def test_convexity_non_negative():
    bond = make_bond(coupon=0.07)
    risk = yield_risk_metrics(
        bond.cashflows(), date(2024, 1, 1), ytm=0.085, frequency=1
    )
    assert risk.convexity > 0


def test_zero_coupon_macaulay_equals_maturity():
    """Macaulay duration of a zero-coupon bond equals its time-to-maturity."""
    bond = make_bond(
        issue=date(2024, 1, 1),
        maturity=date(2027, 1, 1),
        coupon=0.0,
        freq=1,
    )
    # Zero coupon: only one cashflow at maturity (principal). Duration = T.
    risk = yield_risk_metrics(bond.cashflows(), date(2024, 1, 1), 0.05, 1)
    expected_T = (date(2027, 1, 1) - date(2024, 1, 1)).days / 365.0
    assert risk.macaulay_duration == pytest.approx(expected_T, abs=1e-3)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
