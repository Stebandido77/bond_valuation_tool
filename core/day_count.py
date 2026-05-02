"""
core.day_count
==============

Day count conventions for fixed income pricing.

Implements the most common conventions used in sovereign and corporate bond
markets:

    - ACT/360
    - ACT/365 (Fixed)
    - ACT/ACT (ISDA)
    - 30/360 (Bond Basis, US)
    - 30E/360 (Eurobond)
    - NL/365 (used by some local-currency sovereign markets, including TES
      tasa fija under MHCP / BVC conventions for accrual)

All functions take two ``datetime.date`` objects and return the year
fraction as ``float``. They are pure and side-effect free so they can be
vectorized at the caller level if needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Callable


class DayCount(str, Enum):
    """Supported day count conventions."""

    ACT_360 = "ACT/360"
    ACT_365 = "ACT/365"
    ACT_ACT = "ACT/ACT"
    THIRTY_360 = "30/360"
    THIRTY_E_360 = "30E/360"
    NL_365 = "NL/365"


# ---------------------------------------------------------------------------
# Individual conventions
# ---------------------------------------------------------------------------
def _act_360(start: date, end: date) -> float:
    return (end - start).days / 360.0


def _act_365(start: date, end: date) -> float:
    return (end - start).days / 365.0


def _act_act_isda(start: date, end: date) -> float:
    """ACT/ACT ISDA: splits the period across calendar years."""
    if start == end:
        return 0.0
    if start > end:
        return -_act_act_isda(end, start)

    if start.year == end.year:
        denom = 366.0 if _is_leap(start.year) else 365.0
        return (end - start).days / denom

    # period spans more than one year
    yf = 0.0
    # fragment in the start year
    end_of_start_year = date(start.year, 12, 31)
    denom_start = 366.0 if _is_leap(start.year) else 365.0
    yf += ((end_of_start_year - start).days + 1) / denom_start
    # full intermediate years
    for y in range(start.year + 1, end.year):
        yf += 1.0
    # fragment in the end year
    start_of_end_year = date(end.year, 1, 1)
    denom_end = 366.0 if _is_leap(end.year) else 365.0
    yf += (end - start_of_end_year).days / denom_end
    return yf


def _thirty_360(start: date, end: date) -> float:
    """30/360 Bond Basis (US)."""
    d1 = min(start.day, 30)
    d2 = end.day
    if d1 == 30 and d2 == 31:
        d2 = 30
    days = (
        360 * (end.year - start.year)
        + 30 * (end.month - start.month)
        + (d2 - d1)
    )
    return days / 360.0


def _thirty_e_360(start: date, end: date) -> float:
    """30E/360 Eurobond."""
    d1 = min(start.day, 30)
    d2 = min(end.day, 30)
    days = (
        360 * (end.year - start.year)
        + 30 * (end.month - start.month)
        + (d2 - d1)
    )
    return days / 360.0


def _nl_365(start: date, end: date) -> float:
    """NL/365 (No Leap): Feb 29 is removed from the day count."""
    days = (end - start).days
    # subtract Feb-29s contained in the interval
    leaps = 0
    for y in range(start.year, end.year + 1):
        if _is_leap(y):
            feb29 = date(y, 2, 29)
            if start < feb29 <= end:
                leaps += 1
    return (days - leaps) / 365.0


def _is_leap(y: int) -> bool:
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
_DISPATCH: dict[DayCount, Callable[[date, date], float]] = {
    DayCount.ACT_360: _act_360,
    DayCount.ACT_365: _act_365,
    DayCount.ACT_ACT: _act_act_isda,
    DayCount.THIRTY_360: _thirty_360,
    DayCount.THIRTY_E_360: _thirty_e_360,
    DayCount.NL_365: _nl_365,
}


def year_fraction(start: date, end: date, convention: DayCount) -> float:
    """Compute the year fraction between two dates under ``convention``.

    Parameters
    ----------
    start, end : date
        Period start and end. ``start <= end`` is the natural case but the
        function also returns a negative value if reversed (for ACT/ACT it is
        explicit; for the others it falls out of the formulas).
    convention : DayCount
        One of the supported conventions.
    """
    if convention not in _DISPATCH:
        raise ValueError(f"Unsupported day count convention: {convention}")
    return _DISPATCH[convention](start, end)


@dataclass(frozen=True)
class DayCountAdapter:
    """Lightweight wrapper to bind a convention to repeated calls."""

    convention: DayCount

    def yf(self, start: date, end: date) -> float:
        return year_fraction(start, end, self.convention)
