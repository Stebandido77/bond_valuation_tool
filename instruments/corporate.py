"""
instruments.corporate
=====================

Corporate and global fixed-rate bonds.

Three convenience subclasses are provided:

    - ``CorporateFixedRate``: peso-denominated corporate fixed rate.
      Defaults to 30/360, semi-annual coupons (the most common LATAM
      corporate convention).

    - ``CorporateIPC``: corporate inflation-linked. Thin alias around
      ``RealPlusInflation`` with corporate defaults (semi-annual,
      30/360 — many Colombian IPC corporates pay semi-annually).

    - ``GlobalBond``: USD / EUR / GBP fixed-rate bond. Defaults to 30/360
      semi-annual (US convention) but accepts overrides for sterling
      (ACT/365) or euro-denominated paper (ACT/ACT).

These exist purely for ergonomics — you can always build a plain
``Bond`` directly with whatever conventions you need.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.day_count import DayCount

from .bond import Bond
from .inflation_linked import RealPlusInflation


@dataclass
class CorporateFixedRate(Bond):
    """COP corporate fixed-rate bond (default semi-annual, 30/360)."""

    frequency: int = 2
    day_count: DayCount = DayCount.THIRTY_360
    currency: str = "COP"

    def __post_init__(self):
        if not self.description:
            self.description = "Corporate Fixed-Rate Bond"


@dataclass
class CorporateIPC(RealPlusInflation):
    """COP corporate IPC-linked bond."""

    frequency: int = 2
    day_count: DayCount = DayCount.THIRTY_360
    currency: str = "COP"

    def __post_init__(self):
        if not self.description:
            self.description = "Corporate IPC-Linked Bond"


@dataclass
class GlobalBond(Bond):
    """Global / hard-currency fixed-rate bond.

    Defaults reflect the US-style convention (30/360 semi-annual, USD).
    Override ``currency`` and ``day_count`` for sterling / euro paper.
    """

    frequency: int = 2
    day_count: DayCount = DayCount.THIRTY_360
    currency: str = "USD"

    def __post_init__(self):
        if not self.description:
            self.description = f"Global Fixed-Rate Bond ({self.currency})"
