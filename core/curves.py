"""
core.curves
===========

Zero-coupon discount curves.

A ``ZeroCurve`` is a tabulated set of (days, zero_rate) pairs anchored on a
``valuation_date``. It exposes:

    - discount factor lookup at any future date
    - zero rate lookup
    - parallel shocks (for DV01 / scenario analysis)
    - bucket shocks on a given pillar (for key-rate / bucket DV01)

Interpolation is delegated to ``market_data.interpolation`` so different
schemes (linear, log-linear on DF, cubic spline, etc.) can be plugged in
without touching pricing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import List, Optional

import numpy as np

from market_data.interpolation import Interpolator, LinearInterpolator


_DAY_BASIS = 365.0  # convention used to convert zero rate to discount factor


@dataclass(frozen=True)
class CurvePoint:
    tenor: str
    days: int
    zero_rate: float        # decimal, continuously-compounded if convention="CC"
                            # or annual-compounded if convention="ANN"

    def __post_init__(self):
        if self.days < 0:
            raise ValueError("days must be non-negative")


@dataclass
class ZeroCurve:
    """A zero-coupon curve anchored on ``valuation_date``.

    Parameters
    ----------
    name : str
        Curve identifier (e.g. ``"TES_COP"``, ``"IBR"``).
    valuation_date : date
        Anchor date. Day-zero discount factor is 1.
    points : list[CurvePoint]
        Pillar points. They will be sorted by ``days``.
    convention : {"CC", "ANN"}
        ``"CC"``: continuously-compounded zero rates  ->  DF = exp(-r * t)
        ``"ANN"``: annual-compounded zero rates       ->  DF = (1 + r) ** (-t)
    currency : str
        Three-letter ISO code for reporting.
    interpolator : Interpolator
        Strategy used to interpolate between pillars.
    """

    name: str
    valuation_date: date
    points: List[CurvePoint]
    convention: str = "ANN"
    currency: str = "COP"
    interpolator: Interpolator = field(default_factory=LinearInterpolator)

    def __post_init__(self):
        if not self.points:
            raise ValueError("ZeroCurve requires at least one pillar")
        self.points = sorted(self.points, key=lambda p: p.days)
        if self.convention not in ("CC", "ANN"):
            raise ValueError("convention must be 'CC' or 'ANN'")
        # de-duplicate by days, keeping the last occurrence
        seen: dict[int, CurvePoint] = {}
        for p in self.points:
            seen[p.days] = p
        self.points = sorted(seen.values(), key=lambda p: p.days)
        self._days_arr = np.array([p.days for p in self.points], dtype=float)
        self._rates_arr = np.array([p.zero_rate for p in self.points], dtype=float)

    # ------------------------------------------------------------------ #
    # Lookup
    # ------------------------------------------------------------------ #
    def zero_rate_at_days(self, days: float) -> float:
        if days <= 0:
            return float(self._rates_arr[0])
        return float(self.interpolator.interpolate(self._days_arr, self._rates_arr, days))

    def zero_rate(self, dt: date) -> float:
        return self.zero_rate_at_days((dt - self.valuation_date).days)

    def discount_factor(self, dt: date) -> float:
        days = (dt - self.valuation_date).days
        if days <= 0:
            return 1.0
        t = days / _DAY_BASIS
        r = self.zero_rate_at_days(days)
        if self.convention == "CC":
            return float(np.exp(-r * t))
        return float((1.0 + r) ** (-t))

    # ------------------------------------------------------------------ #
    # Shocks
    # ------------------------------------------------------------------ #
    def shifted(self, bps: float) -> "ZeroCurve":
        """Parallel shock in basis points (1 bp = 1e-4)."""
        new_points = [
            CurvePoint(tenor=p.tenor, days=p.days, zero_rate=p.zero_rate + bps * 1e-4)
            for p in self.points
        ]
        return replace(self, points=new_points)

    def bucket_shifted(self, pillar_days: int, bps: float) -> "ZeroCurve":
        """Shock a single pillar (key-rate / bucket DV01)."""
        new_points = []
        for p in self.points:
            if p.days == pillar_days:
                new_points.append(
                    CurvePoint(tenor=p.tenor, days=p.days, zero_rate=p.zero_rate + bps * 1e-4)
                )
            else:
                new_points.append(p)
        return replace(self, points=new_points)

    # ------------------------------------------------------------------ #
    # Convenience
    # ------------------------------------------------------------------ #
    def as_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        return self._days_arr.copy(), self._rates_arr.copy()

    def tenors(self) -> List[str]:
        return [p.tenor for p in self.points]
