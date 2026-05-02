"""
instruments.bond
================

Generic fixed-rate bullet bond. Other instruments (TES tasa fija, TES UVR,
corporate fixed rate, etc.) inherit from this class and tweak only the bits
that differ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from core.cashflows import CashFlow, build_cashflows
from core.curves import ZeroCurve
from core.day_count import DayCount
from core.pricing import (
    PricingResult,
    price_with_curve,
    price_with_yield,
    solve_ytm,
)
from core.risk_metrics import (
    RiskMetrics,
    bucket_dv01,
    curve_risk_metrics,
    parallel_scenarios,
    yield_risk_metrics,
)


@dataclass
class Bond:
    """A bullet fixed-rate bond.

    Parameters
    ----------
    isin : str
        Identifier — purely descriptive, not used in math.
    issue_date, maturity_date : date
        Bond life span.
    coupon_rate : float
        Annualized coupon rate, decimal (e.g. 0.07 for 7%).
    frequency : int
        Coupons per year. 1 = annual (typical for TES tasa fija).
    notional : float
        Face value in the bond currency.
    day_count : DayCount
        Accrual convention.
    currency : str
        ISO three-letter code.
    """

    isin: str
    issue_date: date
    maturity_date: date
    coupon_rate: float
    frequency: int = 1
    notional: float = 100_000_000.0
    day_count: DayCount = DayCount.ACT_365
    currency: str = "COP"
    description: str = ""

    _cashflows: Optional[List[CashFlow]] = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------ #
    # Cashflows
    # ------------------------------------------------------------------ #
    def cashflows(self) -> List[CashFlow]:
        if self._cashflows is None:
            self._cashflows = build_cashflows(
                issue_date=self.issue_date,
                maturity_date=self.maturity_date,
                frequency=self.frequency,
                coupon_rate=self.coupon_rate,
                notional=self.notional,
                convention=self.day_count,
            )
        return self._cashflows

    # ------------------------------------------------------------------ #
    # Pricing
    # ------------------------------------------------------------------ #
    def price_yield(
        self,
        valuation_date: date,
        ytm: float,
        spread_bps: float = 0.0,
    ) -> PricingResult:
        return price_with_yield(
            self.cashflows(), valuation_date, ytm, self.frequency, spread_bps
        )

    def price_curve(
        self,
        valuation_date: date,
        curve: ZeroCurve,
        spread_bps: float = 0.0,
    ) -> PricingResult:
        return price_with_curve(self.cashflows(), valuation_date, curve, spread_bps)

    def implied_ytm(
        self,
        valuation_date: date,
        dirty_price: float,
        initial_guess: float = 0.08,
    ) -> float:
        return solve_ytm(
            self.cashflows(), valuation_date, dirty_price, self.frequency, initial_guess
        )

    # ------------------------------------------------------------------ #
    # Risk
    # ------------------------------------------------------------------ #
    def risk_yield(self, valuation_date: date, ytm: float) -> RiskMetrics:
        return yield_risk_metrics(
            self.cashflows(), valuation_date, ytm, self.frequency
        )

    def risk_curve(
        self,
        valuation_date: date,
        curve: ZeroCurve,
        spread_bps: float = 0.0,
    ) -> RiskMetrics:
        return curve_risk_metrics(
            self.cashflows(), valuation_date, curve, spread_bps
        )

    def bucket_dv01(
        self,
        valuation_date: date,
        curve: ZeroCurve,
        spread_bps: float = 0.0,
    ) -> dict:
        return bucket_dv01(self.cashflows(), valuation_date, curve, spread_bps)

    def parallel_scenarios(
        self,
        valuation_date: date,
        curve: ZeroCurve,
        bps_list: List[float],
        spread_bps: float = 0.0,
    ) -> dict:
        return parallel_scenarios(
            self.cashflows(), valuation_date, curve, bps_list, spread_bps
        )

    # ------------------------------------------------------------------ #
    # Misc
    # ------------------------------------------------------------------ #
    def label(self) -> str:
        return f"{self.isin} {self.coupon_rate*100:.3f}% {self.maturity_date.isoformat()}"
