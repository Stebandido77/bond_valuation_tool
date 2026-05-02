"""
instruments.tes_catalog
=======================

Catalog of TES (Colombian sovereign) reference bonds.

Three families are covered, all currently outstanding (live) at the time
this catalog was assembled (late 2025 / early 2026):

    - TES Tasa Fija (COP)  — peso-denominated nominal-rate bullets.
    - TES UVR             — UVR-indexed real-rate bullets.
    - TES IPC             — inflation-linked, (1+IPC)(1+real)-1 coupons.
    - TES Globales        — hard-currency sovereign bullets (USD / EUR).

The data is illustrative and built from public sources: DGCPTN
issuance announcements, BVC reference data, and Grupo Aval's TES portal.
Production users should validate ISINs and contractual terms against DCV
before relying on this catalog.

Lookup is done via ``get_reference(ref)`` which is case-insensitive and
checks the user-supplied catalog first (added at runtime via
``register_reference`` or ``load_external_catalog``) before falling back
to the bundled data.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Optional

from core.day_count import DayCount


@dataclass(frozen=True)
class TESReference:
    """Contractual reference data for a TES bond."""

    ref: str                  # identifier (local code or ISIN)
    kind: str                 # "TASA_FIJA", "UVR", "IPC", or "GLOBAL"
    issue_date: date
    maturity_date: date
    coupon_rate: float        # decimal; real for IPC/UVR, nominal for TF & Global
    frequency: int = 1
    day_count: DayCount = DayCount.NL_365
    currency: str = "COP"     # "COP", "UVR", "USD", "EUR"
    description: str = ""


# ---------------------------------------------------------------------------
# Built-in catalog
# ---------------------------------------------------------------------------
_BUILTIN_CATALOG: Dict[str, TESReference] = {

    # ===================== TES TASA FIJA (COP) =====================
    # Local code convention: TFITxxYYMMDD where xx = original tenor years.
    # Issue dates are the official launch dates from DGCPTN announcements;
    # if the exact launch date is uncertain, we use the "tap" / re-opening
    # date — coupon and maturity are the contractually relevant fields.

    "TFIT16240724": TESReference(
        ref="TFIT16240724", kind="TASA_FIJA",
        issue_date=date(2008, 7, 24), maturity_date=date(2024, 7, 24),
        coupon_rate=0.10, description="TES Tasa Fija 10.00% Jul/2024",
    ),
    "TFIT15260826": TESReference(
        ref="TFIT15260826", kind="TASA_FIJA",
        issue_date=date(2011, 8, 26), maturity_date=date(2026, 8, 26),
        coupon_rate=0.075, description="TES Tasa Fija 7.50% Ago/2026",
    ),
    "TFIT16280428": TESReference(
        ref="TFIT16280428", kind="TASA_FIJA",
        issue_date=date(2012, 4, 28), maturity_date=date(2028, 4, 28),
        coupon_rate=0.06, description="TES Tasa Fija 6.00% Abr/2028",
    ),
    "TFIT16181030": TESReference(
        ref="TFIT16181030", kind="TASA_FIJA",
        issue_date=date(2014, 10, 30), maturity_date=date(2030, 10, 30),
        coupon_rate=0.075, description="TES Tasa Fija 7.50% Oct/2030",
    ),
    "TFIT15290632": TESReference(
        ref="TFIT15290632", kind="TASA_FIJA",
        issue_date=date(2017, 6, 29), maturity_date=date(2032, 6, 29),
        coupon_rate=0.07, description="TES Tasa Fija 7.00% Jun/2032",
    ),
    "TFIT15300925": TESReference(
        ref="TFIT15300925", kind="TASA_FIJA",
        issue_date=date(2018, 9, 25), maturity_date=date(2030, 9, 18),
        coupon_rate=0.0775, description="TES Tasa Fija 7.75% Sep/2030",
    ),
    "TFIT15341024": TESReference(
        ref="TFIT15341024", kind="TASA_FIJA",
        issue_date=date(2019, 10, 24), maturity_date=date(2034, 10, 24),
        coupon_rate=0.0725, description="TES Tasa Fija 7.25% Oct/2034",
    ),
    "TFIT15330825": TESReference(
        ref="TFIT15330825", kind="TASA_FIJA",
        issue_date=date(2020, 8, 25), maturity_date=date(2033, 8, 25),
        coupon_rate=0.0675, description="TES Tasa Fija 6.75% Ago/2033",
    ),
    "TFIT16360925": TESReference(
        ref="TFIT16360925", kind="TASA_FIJA",
        issue_date=date(2021, 9, 25), maturity_date=date(2036, 9, 25),
        coupon_rate=0.07, description="TES Tasa Fija 7.00% Sep/2036",
    ),
    "TFIT16270727": TESReference(
        ref="TFIT16270727", kind="TASA_FIJA",
        issue_date=date(2022, 7, 27), maturity_date=date(2027, 7, 27),
        coupon_rate=0.07, description="TES Tasa Fija 7.00% Jul/2027",
    ),
    "TFIT16380917": TESReference(
        ref="TFIT16380917", kind="TASA_FIJA",
        issue_date=date(2023, 9, 17), maturity_date=date(2038, 9, 17),
        coupon_rate=0.09, description="TES Tasa Fija 9.00% Sep/2038",
    ),
    "TFIT16500626": TESReference(
        ref="TFIT16500626", kind="TASA_FIJA",
        issue_date=date(2024, 6, 26), maturity_date=date(2050, 6, 26),
        coupon_rate=0.105, description="TES Tasa Fija 10.50% Jun/2050",
    ),
    "TFIT16290925": TESReference(
        ref="TFIT16290925", kind="TASA_FIJA",
        issue_date=date(2024, 9, 25), maturity_date=date(2029, 9, 25),
        coupon_rate=0.105, description="TES Tasa Fija 10.50% Sep/2029",
    ),
    "TFIT16400125": TESReference(
        ref="TFIT16400125", kind="TASA_FIJA",
        issue_date=date(2025, 1, 22), maturity_date=date(2040, 1, 25),
        coupon_rate=0.115, description="TES Tasa Fija 11.50% Ene/2040",
    ),

    # ===================== TES UVR =====================
    "TUVT11240419": TESReference(
        ref="TUVT11240419", kind="UVR",
        issue_date=date(2013, 4, 19), maturity_date=date(2024, 4, 19),
        coupon_rate=0.0325, currency="UVR",
        description="TES UVR 3.25% Abr/2024",
    ),
    "TUVT17250225": TESReference(
        ref="TUVT17250225", kind="UVR",
        issue_date=date(2008, 2, 25), maturity_date=date(2025, 2, 25),
        coupon_rate=0.0475, currency="UVR",
        description="TES UVR 4.75% Feb/2025",
    ),
    "TUVT11270216": TESReference(
        ref="TUVT11270216", kind="UVR",
        issue_date=date(2016, 2, 16), maturity_date=date(2027, 2, 16),
        coupon_rate=0.035, currency="UVR",
        description="TES UVR 3.50% Feb/2027",
    ),
    "TUVT20330322": TESReference(
        ref="TUVT20330322", kind="UVR",
        issue_date=date(2013, 3, 22), maturity_date=date(2033, 3, 22),
        coupon_rate=0.03, currency="UVR",
        description="TES UVR 3.00% Mar/2033",
    ),
    "TUVT20350318": TESReference(
        ref="TUVT20350318", kind="UVR",
        issue_date=date(2015, 3, 18), maturity_date=date(2035, 3, 18),
        coupon_rate=0.0475, currency="UVR",
        description="TES UVR 4.75% Mar/2035",
    ),
    "TUVT20370225": TESReference(
        ref="TUVT20370225", kind="UVR",
        issue_date=date(2017, 2, 25), maturity_date=date(2037, 2, 25),
        coupon_rate=0.0375, currency="UVR",
        description="TES UVR 3.75% Feb/2037",
    ),
    "TUVT20490225": TESReference(
        ref="TUVT20490225", kind="UVR",
        issue_date=date(2019, 2, 25), maturity_date=date(2049, 2, 25),
        coupon_rate=0.0425, currency="UVR",
        description="TES UVR 4.25% Feb/2049",
    ),
    "TUVT20520225": TESReference(
        ref="TUVT20520225", kind="UVR",
        issue_date=date(2022, 2, 25), maturity_date=date(2052, 2, 25),
        coupon_rate=0.04, currency="UVR",
        description="TES UVR 4.00% Feb/2052",
    ),

    # ===================== TES IPC =====================
    # IPC linkers: spread on top of CPI, NL/365 annual coupons.

    "TIPC15170725": TESReference(
        ref="TIPC15170725", kind="IPC",
        issue_date=date(2010, 7, 25), maturity_date=date(2025, 7, 25),
        coupon_rate=0.04, description="TES IPC + 4.00% Jul/2025",
    ),
    "TIPC15280727": TESReference(
        ref="TIPC15280727", kind="IPC",
        issue_date=date(2013, 7, 27), maturity_date=date(2028, 7, 27),
        coupon_rate=0.0375, description="TES IPC + 3.75% Jul/2028",
    ),
    "TIPC15330327": TESReference(
        ref="TIPC15330327", kind="IPC",
        issue_date=date(2018, 3, 27), maturity_date=date(2033, 3, 27),
        coupon_rate=0.035, description="TES IPC + 3.50% Mar/2033",
    ),

    # ===================== TES GLOBALES (USD) =====================
    # Sovereign bullet bonds in hard currency. ISINs are the public Bloomberg
    # / Reuters references for COLOM (Republic of Colombia) issuances.
    # 30/360 semi-annual is the standard global-bond convention.

    "US195325DZ31": TESReference(
        ref="US195325DZ31", kind="GLOBAL",
        issue_date=date(2018, 6, 26), maturity_date=date(2031, 1, 28),
        coupon_rate=0.04875, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 4.875% Ene/2031",
    ),
    "US195325CK74": TESReference(
        ref="US195325CK74", kind="GLOBAL",
        issue_date=date(2014, 1, 28), maturity_date=date(2026, 1, 28),
        coupon_rate=0.045, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 4.50% Ene/2026",
    ),
    "US195325BB95": TESReference(
        ref="US195325BB95", kind="GLOBAL",
        issue_date=date(2010, 9, 18), maturity_date=date(2027, 9, 18),
        coupon_rate=0.0625, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 6.125% Sep/2027",
    ),
    "US195325DL45": TESReference(
        ref="US195325DL45", kind="GLOBAL",
        issue_date=date(2017, 4, 25), maturity_date=date(2029, 4, 25),
        coupon_rate=0.04500, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 4.50% Mar/2029",
    ),
    "US195325DV28": TESReference(
        ref="US195325DV28", kind="GLOBAL",
        issue_date=date(2017, 1, 28), maturity_date=date(2032, 1, 28),
        coupon_rate=0.05625, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 5.625% Ene/2032",
    ),
    "US195325BG82": TESReference(
        ref="US195325BG82", kind="GLOBAL",
        issue_date=date(2010, 4, 23), maturity_date=date(2037, 4, 25),
        coupon_rate=0.0775, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 7.375% Sep/2037",
    ),
    "US195325CU56": TESReference(
        ref="US195325CU56", kind="GLOBAL",
        issue_date=date(2014, 5, 27), maturity_date=date(2045, 2, 26),
        coupon_rate=0.05625, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 5.625% Feb/2045",
    ),
    "US195325DM28": TESReference(
        ref="US195325DM28", kind="GLOBAL",
        issue_date=date(2017, 6, 14), maturity_date=date(2049, 5, 15),
        coupon_rate=0.06125, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 6.125% May/2049",
    ),
    "US195325EJ87": TESReference(
        ref="US195325EJ87", kind="GLOBAL",
        issue_date=date(2020, 9, 16), maturity_date=date(2051, 1, 28),
        coupon_rate=0.0500, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 5.00% Ene/2051",
    ),
    "US195325EL34": TESReference(
        ref="US195325EL34", kind="GLOBAL",
        issue_date=date(2021, 4, 13), maturity_date=date(2061, 1, 28),
        coupon_rate=0.04125, frequency=2, day_count=DayCount.THIRTY_360,
        currency="USD", description="COLOM Global USD 4.125% Ene/2061",
    ),

    # ===================== TES GLOBALES (EUR) =====================
    "XS1500641879": TESReference(
        ref="XS1500641879", kind="GLOBAL",
        issue_date=date(2016, 10, 18), maturity_date=date(2026, 11, 7),
        coupon_rate=0.025, frequency=1, day_count=DayCount.ACT_ACT,
        currency="EUR", description="COLOM Global EUR 2.50% Nov/2026",
    ),
    "XS1996062043": TESReference(
        ref="XS1996062043", kind="GLOBAL",
        issue_date=date(2019, 5, 8), maturity_date=date(2031, 5, 8),
        coupon_rate=0.0250, frequency=1, day_count=DayCount.ACT_ACT,
        currency="EUR", description="COLOM Global EUR 2.50% May/2031",
    ),
}


# ---------------------------------------------------------------------------
# Runtime user catalog (overlays built-in)
# ---------------------------------------------------------------------------
_USER_CATALOG: Dict[str, TESReference] = {}


def get_reference(ref: str) -> Optional[TESReference]:
    """Return a TES reference if known, else ``None``.

    Lookup order: user-supplied catalog first, then built-in catalog.
    Comparison is case-insensitive and ignores leading/trailing whitespace.
    """
    if not ref:
        return None
    key = ref.strip().upper()
    if key in _USER_CATALOG:
        return _USER_CATALOG[key]
    return _BUILTIN_CATALOG.get(key)


def all_references() -> Dict[str, TESReference]:
    """All known references (user catalog overlays built-in)."""
    out = dict(_BUILTIN_CATALOG)
    out.update(_USER_CATALOG)
    return out


def references_by_kind(kind: str) -> Dict[str, TESReference]:
    """Filter the catalog by kind ('TASA_FIJA', 'UVR', 'IPC', 'GLOBAL')."""
    k = kind.strip().upper()
    return {r: ref for r, ref in all_references().items() if ref.kind == k}


def live_references(as_of: date) -> Dict[str, TESReference]:
    """Return only references whose maturity is strictly after ``as_of``."""
    return {r: ref for r, ref in all_references().items() if ref.maturity_date > as_of}


def register_reference(ref: TESReference) -> None:
    """Add or override a reference at runtime."""
    _USER_CATALOG[ref.ref.strip().upper()] = ref


def load_external_catalog(path: str | Path) -> int:
    """Load extra references from a CSV file. Returns rows inserted.

    Expected columns: ref, kind, issue_date, maturity_date, coupon_rate,
    [frequency], [day_count], [currency], [description].
    """
    path = Path(path)
    inserted = 0
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                ref = TESReference(
                    ref=row["ref"].strip(),
                    kind=row["kind"].strip().upper(),
                    issue_date=date.fromisoformat(row["issue_date"]),
                    maturity_date=date.fromisoformat(row["maturity_date"]),
                    coupon_rate=float(row["coupon_rate"]),
                    frequency=int(row.get("frequency", 1) or 1),
                    day_count=DayCount(row.get("day_count", "NL/365") or "NL/365"),
                    currency=row.get("currency", "COP") or "COP",
                    description=row.get("description", "") or "",
                )
                register_reference(ref)
                inserted += 1
            except Exception:
                continue
    return inserted
