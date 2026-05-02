"""
core.cashflows
==============

Cashflow generation for fixed-rate bullet bonds.

The generator produces a forward-looking schedule from issue date to maturity
using a fixed coupon frequency. Stubs (front-stub or back-stub) are handled
by anchoring the schedule on the maturity date and rolling backwards, which
matches the convention used in most sovereign markets — including TES tasa
fija whose coupons are anchored on maturity day/month.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from .day_count import DayCount, year_fraction


@dataclass(frozen=True)
class CashFlow:
    """A single bond cash flow."""

    period: int
    accrual_start: date
    accrual_end: date
    payment_date: date
    year_fraction: float
    coupon_rate: float        # annualized, decimal
    notional: float
    interest: float
    principal: float

    @property
    def total(self) -> float:
        return self.interest + self.principal


def _add_months(d: date, months: int) -> date:
    """Add an integer number of months, clamping the day if needed."""
    m_index = d.month - 1 + months
    year = d.year + m_index // 12
    month = m_index % 12 + 1
    # clamp day
    if month == 2:
        last = 29 if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0 else 28
    elif month in (4, 6, 9, 11):
        last = 30
    else:
        last = 31
    return date(year, month, min(d.day, last))


def generate_schedule(
    issue_date: date,
    maturity_date: date,
    frequency: int,
) -> List[date]:
    """Generate accrual period boundaries (issue ... maturity).

    Parameters
    ----------
    issue_date, maturity_date : date
        Bond start and end of life.
    frequency : int
        Coupons per year (1, 2, 4, or 12 are typical).

    Returns
    -------
    list[date]
        Sorted list of dates including the issue date and the maturity date.
        Stubs are placed at the front, which is the convention for rolling
        backwards from maturity.
    """
    if frequency <= 0:
        raise ValueError("frequency must be a positive integer")
    if maturity_date <= issue_date:
        raise ValueError("maturity_date must be strictly after issue_date")

    months_per_period = 12 // frequency
    if 12 % frequency != 0:
        raise ValueError(
            "Only frequencies that divide 12 evenly are supported "
            "(1, 2, 3, 4, 6, 12)."
        )

    dates: list[date] = [maturity_date]
    cursor = maturity_date
    while True:
        cursor = _add_months(cursor, -months_per_period)
        if cursor <= issue_date:
            break
        dates.append(cursor)
    dates.append(issue_date)
    dates.reverse()
    return dates


def build_cashflows(
    issue_date: date,
    maturity_date: date,
    frequency: int,
    coupon_rate: float,
    notional: float,
    convention: DayCount,
) -> List[CashFlow]:
    """Build the full cash flow schedule of a bullet fixed-rate bond.

    The principal is repaid on the last cashflow.
    """
    schedule = generate_schedule(issue_date, maturity_date, frequency)
    flows: list[CashFlow] = []
    for i in range(1, len(schedule)):
        start = schedule[i - 1]
        end = schedule[i]
        yf = year_fraction(start, end, convention)
        interest = notional * coupon_rate * yf
        principal = notional if i == len(schedule) - 1 else 0.0
        flows.append(
            CashFlow(
                period=i,
                accrual_start=start,
                accrual_end=end,
                payment_date=end,
                year_fraction=yf,
                coupon_rate=coupon_rate,
                notional=notional,
                interest=interest,
                principal=principal,
            )
        )
    return flows


def accrued_interest(
    flows: List[CashFlow],
    valuation_date: date,
) -> float:
    """Linear accrued interest on the running coupon period."""
    for cf in flows:
        if cf.accrual_start < valuation_date <= cf.accrual_end:
            full = cf.interest
            if cf.year_fraction <= 0:
                return 0.0
            elapsed = (valuation_date - cf.accrual_start).days
            total = (cf.accrual_end - cf.accrual_start).days
            if total <= 0:
                return 0.0
            return full * elapsed / total
    return 0.0
