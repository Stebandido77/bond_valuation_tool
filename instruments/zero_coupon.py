"""
instruments.zero_coupon
=======================

Zero-coupon / discount bonds.

A single cashflow at maturity equal to the notional. Modeled as a Bond
with coupon_rate = 0 and frequency = 1. Useful for:

    - TES Globales separados (STRIPS)
    - Letras del Tesoro
    - Stripped components of any bullet bond
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.day_count import DayCount

from .bond import Bond


@dataclass
class ZeroCouponBond(Bond):
    """Zero-coupon bond. ``coupon_rate`` is forced to 0."""

    coupon_rate: float = 0.0
    frequency: int = 1
    day_count: DayCount = DayCount.ACT_365
    currency: str = "COP"

    def __post_init__(self):
        # Force coupon = 0 even if caller passes something else
        object.__setattr__(self, "coupon_rate", 0.0)
        if not self.description:
            self.description = "Zero-Coupon Bond"
