"""
instruments.tes
===============

TES (Títulos de Tesorería) — Colombian sovereign bonds.

Two flavours are supported:

    - ``TESTasaFija``: peso-denominated fixed rate, annual coupon, NL/365
      accrual (no-leap basis). Maturity-anchored schedule.
    - ``TESUVR``: UVR-denominated (real) fixed rate. The notional is indexed
      to the UVR. The valuation here is in UVR units; conversion to COP is
      done by multiplying by the UVR fixing of the valuation date — supplied
      by the caller, kept out of the pricing engine.

Both classes are thin specializations of ``Bond`` that fix the conventions
the market uses by default. They can still be overridden if needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from core.day_count import DayCount

from .bond import Bond
from .inflation_linked import RealPlusInflation


@dataclass
class TESTasaFija(Bond):
    """TES tasa fija (COP)."""

    frequency: int = 1
    day_count: DayCount = DayCount.NL_365
    currency: str = "COP"

    def __post_init__(self):
        if not self.description:
            self.description = "TES Tasa Fija"


@dataclass
class TESUVR(Bond):
    """TES UVR (real-rate, indexed to UVR).

    ``notional`` here is in UVR units. To express results in COP, multiply
    PVs by the UVR fixing of the valuation date.
    """

    frequency: int = 1
    day_count: DayCount = DayCount.NL_365
    currency: str = "UVR"

    def __post_init__(self):
        if not self.description:
            self.description = "TES UVR"

    def pv_in_cop(self, dirty_price_pct: float, uvr_value_cop: float) -> float:
        """Convert a dirty price (% of UVR notional) into COP using a UVR fixing."""
        return self.notional * dirty_price_pct / 100.0 * uvr_value_cop


@dataclass
class TESIPC(RealPlusInflation):
    """TES IPC — Colombian sovereign inflation-linked bond.

    Quoted as ``IPC + spread``, where ``IPC`` is annual inflation over the
    coupon period. ``coupon_rate`` carries the spread; the inflation
    projection is supplied via ``flat_inflation`` or ``inflation_by_period``.
    """

    frequency: int = 1
    day_count: DayCount = DayCount.NL_365
    currency: str = "COP"

    def __post_init__(self):
        if not self.description:
            self.description = "TES IPC"
