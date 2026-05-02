"""
instruments.inflation_linked
============================

Inflation-linked bonds.

Two coupon mechanics are supported, which together cover the vast majority
of LATAM and global linker conventions:

    - ``UVRIndexed``: principal is indexed to the UVR (Colombia) or any
      analogous capital-indexed unit. The coupon is paid on the indexed
      principal. This is the TES UVR model.

    - ``RealPlusInflation``: cash coupon = (1 + inflation_rate) *
      (1 + real_coupon) - 1, applied per period. This is the TES IPC and
      most LATAM corporate-IPC linker model — coupon quoted as
      ``IPC + spread`` where IPC is the annual inflation rate over the
      coupon period.

Both classes inherit from ``Bond`` and override ``cashflows()`` to inject
the inflation projection. Pricing and risk metrics work transparently
because they only consume the cashflow schedule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from core.cashflows import CashFlow, build_cashflows
from core.day_count import DayCount

from .bond import Bond


@dataclass
class UVRIndexed(Bond):
    """Capital-indexed bond (TES UVR model).

    The bond is priced in UVR units. To convert to COP, multiply the PV by
    the UVR fixing of the valuation date. The class stores ``uvr_fixing``
    optionally for reporting convenience but does not use it inside the
    pricing engine.
    """

    uvr_fixing: Optional[float] = None
    frequency: int = 1
    day_count: DayCount = DayCount.NL_365
    currency: str = "UVR"

    def __post_init__(self):
        if not self.description:
            self.description = "TES UVR / UVR-Indexed Bond"

    def pv_in_cop(self, dirty_pct: float, uvr_value_cop: Optional[float] = None) -> float:
        uvr = uvr_value_cop if uvr_value_cop is not None else self.uvr_fixing
        if uvr is None:
            raise ValueError("Provide uvr_fixing on the instrument or pass uvr_value_cop")
        return self.notional * dirty_pct / 100.0 * uvr


@dataclass
class RealPlusInflation(Bond):
    """Inflation-linked bond with ``(1+inflation)(1+real) - 1`` coupons.

    This is the TES IPC and the typical Colombian corporate IPC linker.
    The cash coupon for period ``i`` is

        c_i = ((1 + inflation_proj[i]) * (1 + real_coupon)) - 1

    multiplied by the year-fraction and the notional. ``coupon_rate`` on
    the parent class plays the role of the real (spread) leg.

    Two modes of supplying the inflation projection are supported:

    1. ``flat_inflation``: a single annualized rate applied to every period.
    2. ``inflation_by_period``: a list with one rate per coupon period (in
       order). Useful when the user has a forecast curve.

    If neither is given, ``flat_inflation = 0`` is assumed and the bond
    behaves like a plain real-rate bond (useful for sensitivity analysis).
    """

    flat_inflation: Optional[float] = None
    inflation_by_period: Optional[List[float]] = None
    frequency: int = 1
    day_count: DayCount = DayCount.NL_365
    currency: str = "COP"

    def __post_init__(self):
        if not self.description:
            self.description = "Inflation-Linked Bond (Real + IPC)"

    def cashflows(self) -> List[CashFlow]:
        if self._cashflows is not None:
            return self._cashflows

        # Build a base schedule with zero coupon, then patch interest period
        # by period using the inflation projection.
        base = build_cashflows(
            issue_date=self.issue_date,
            maturity_date=self.maturity_date,
            frequency=self.frequency,
            coupon_rate=0.0,
            notional=self.notional,
            convention=self.day_count,
        )

        infl_arr = self._inflation_array(len(base))
        patched: list[CashFlow] = []
        for i, cf in enumerate(base):
            infl_period = infl_arr[i]
            # combined annualized rate, fisher-style
            combined = (1.0 + infl_period) * (1.0 + self.coupon_rate) - 1.0
            interest = self.notional * combined * cf.year_fraction
            patched.append(
                CashFlow(
                    period=cf.period,
                    accrual_start=cf.accrual_start,
                    accrual_end=cf.accrual_end,
                    payment_date=cf.payment_date,
                    year_fraction=cf.year_fraction,
                    coupon_rate=combined,
                    notional=self.notional,
                    interest=interest,
                    principal=cf.principal,
                )
            )

        self._cashflows = patched
        return patched

    def _inflation_array(self, n: int) -> list[float]:
        if self.inflation_by_period:
            arr = list(self.inflation_by_period)
            if len(arr) < n:
                # pad with the last value (usually long-term inflation expectation)
                arr = arr + [arr[-1]] * (n - len(arr))
            return arr[:n]
        flat = self.flat_inflation if self.flat_inflation is not None else 0.0
        return [flat] * n
