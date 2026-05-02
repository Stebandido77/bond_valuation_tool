"""
instruments.factory
===================

Build a concrete instrument from a generic portfolio row.

The factory accepts a dict-like row with at least an instrument-type
identifier and the contractual fields required by that type, and returns
the appropriate ``Bond`` subclass. It is the bridge between the portfolio
loader (``portfolio.loader``) and the pricing engines.

Resolution order for a TES row:

    1. If ``ref`` is supplied and matches the catalog, take contractual
       terms from the catalog. Anything else on the row (notional, IPC
       projection, UVR fixing) is taken from the row.
    2. If the catalog has no entry, fall back to whatever the row provides.
       Missing required fields raise a clear ``InstrumentBuildError``.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Mapping, Optional

import pandas as pd

from core.day_count import DayCount

from .bond import Bond
from .corporate import CorporateFixedRate, CorporateIPC, GlobalBond
from .inflation_linked import RealPlusInflation, UVRIndexed
from .tes import TESIPC, TESTasaFija, TESUVR
from .tes_catalog import TESReference, get_reference
from .zero_coupon import ZeroCouponBond


SUPPORTED_TYPES = {
    "TES_TASA_FIJA": "TES tasa fija (COP)",
    "TES_UVR": "TES UVR",
    "TES_IPC": "TES IPC",
    "TES_GLOBAL": "TES Global (USD/EUR)",
    "CORP_FIJA": "Corporate fixed rate (COP)",
    "CORP_IPC": "Corporate IPC-linked",
    "GLOBAL": "Global / hard-currency fixed rate",
    "ZERO": "Zero-coupon bond",
    "GENERIC": "Generic fixed-rate bond",
}


class InstrumentBuildError(ValueError):
    """Raised when a portfolio row cannot be turned into an instrument."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise InstrumentBuildError("missing date")
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    try:
        return pd.to_datetime(value).date()
    except Exception as exc:
        raise InstrumentBuildError(f"cannot parse date: {value!r}") from exc


def _to_float(value: Any, name: str, required: bool = True, default: float = 0.0) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        if required:
            raise InstrumentBuildError(f"missing required field '{name}'")
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise InstrumentBuildError(f"cannot parse '{name}' as number: {value!r}") from exc


def _detect_rate_scale(value: float) -> float:
    """Return ``value`` interpreted as decimal (handles 7.5 -> 0.075)."""
    return value / 100.0 if abs(value) > 1.5 else value


def _to_int(value: Any, name: str, default: int) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise InstrumentBuildError(f"cannot parse '{name}' as integer: {value!r}") from exc


def _to_day_count(value: Any, default: DayCount) -> DayCount:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return default
    s = str(value).strip().upper()
    aliases = {
        "ACT/360": DayCount.ACT_360,
        "ACT360": DayCount.ACT_360,
        "ACT/365": DayCount.ACT_365,
        "ACT365": DayCount.ACT_365,
        "ACT/ACT": DayCount.ACT_ACT,
        "ACTACT": DayCount.ACT_ACT,
        "30/360": DayCount.THIRTY_360,
        "30360": DayCount.THIRTY_360,
        "30E/360": DayCount.THIRTY_E_360,
        "30E360": DayCount.THIRTY_E_360,
        "NL/365": DayCount.NL_365,
        "NL365": DayCount.NL_365,
    }
    return aliases.get(s, default)


# ---------------------------------------------------------------------------
# Build dispatcher
# ---------------------------------------------------------------------------
def build_instrument(row: Mapping[str, Any]) -> Bond:
    """Construct a Bond subclass from a portfolio row.

    Required fields:
        ``instrument_type``: one of SUPPORTED_TYPES keys (case-insensitive)
        ``notional``: face value of the position

    Conditionally required (depending on type):
        ``maturity_date``, ``coupon_rate`` for non-catalog rows
        ``issue_date`` for non-catalog rows
        ``ref`` for TES catalog lookup
        ``currency``, ``frequency``, ``day_count`` (with sensible defaults)

    Optional (linker-specific):
        ``flat_inflation`` or ``inflation_by_period``
        ``uvr_fixing``
    """
    raw_type = str(row.get("instrument_type", "")).strip().upper().replace(" ", "_")
    if raw_type not in SUPPORTED_TYPES:
        raise InstrumentBuildError(
            f"unknown instrument_type: {raw_type!r}. Supported: {list(SUPPORTED_TYPES)}"
        )

    notional = _to_float(row.get("notional"), "notional")
    isin_raw = row.get("isin")
    ref_raw = row.get("ref")
    # Treat NaN / "nan" / "" as missing
    def _clean(v):
        if v is None:
            return ""
        if isinstance(v, float) and pd.isna(v):
            return ""
        s = str(v).strip()
        return "" if s.lower() == "nan" else s
    isin = _clean(isin_raw) or _clean(ref_raw) or "BOND"
    description = str(row.get("description", "") or "").strip()
    if description.lower() == "nan":
        description = ""

    # Catalog lookup for TES references
    cat: Optional[TESReference] = None
    if raw_type.startswith("TES_"):
        ref_str = str(row.get("ref", row.get("isin", ""))).strip()
        if ref_str:
            cat = get_reference(ref_str)

    # Common contractual fields with catalog fallback
    def _field(name: str, cat_attr: Optional[str], parser, *, default=None, required=True):
        val = row.get(name)
        if (val is None or (isinstance(val, float) and pd.isna(val)) or val == "") and cat is not None and cat_attr is not None:
            return getattr(cat, cat_attr)
        if (val is None or (isinstance(val, float) and pd.isna(val)) or val == "") and not required:
            return default
        return parser(val)

    if raw_type == "TES_TASA_FIJA":
        issue = _field("issue_date", "issue_date", _to_date)
        maturity = _field("maturity_date", "maturity_date", _to_date)
        coupon = _detect_rate_scale(
            _field("coupon_rate", "coupon_rate", lambda v: _to_float(v, "coupon_rate"))
        )
        freq = _field(
            "frequency", "frequency",
            lambda v: _to_int(v, "frequency", 1), default=1, required=False
        )
        dcc = _field(
            "day_count", "day_count",
            lambda v: _to_day_count(v, DayCount.NL_365),
            default=DayCount.NL_365, required=False,
        )
        return TESTasaFija(
            isin=isin or (cat.ref if cat else "TES"),
            issue_date=issue, maturity_date=maturity,
            coupon_rate=coupon, frequency=freq, notional=notional,
            day_count=dcc, currency="COP", description=description or (cat.description if cat else ""),
        )

    if raw_type == "TES_UVR":
        issue = _field("issue_date", "issue_date", _to_date)
        maturity = _field("maturity_date", "maturity_date", _to_date)
        coupon = _detect_rate_scale(
            _field("coupon_rate", "coupon_rate", lambda v: _to_float(v, "coupon_rate"))
        )
        freq = _field(
            "frequency", "frequency",
            lambda v: _to_int(v, "frequency", 1), default=1, required=False
        )
        dcc = _field(
            "day_count", "day_count",
            lambda v: _to_day_count(v, DayCount.NL_365),
            default=DayCount.NL_365, required=False,
        )
        uvr_fixing = _to_float(row.get("uvr_fixing"), "uvr_fixing", required=False, default=0.0) or None
        return TESUVR(
            isin=isin or (cat.ref if cat else "TES_UVR"),
            issue_date=issue, maturity_date=maturity,
            coupon_rate=coupon, frequency=freq, notional=notional,
            day_count=dcc, currency="UVR",
            description=description or (cat.description if cat else ""),
        )

    if raw_type == "TES_IPC":
        issue = _field("issue_date", "issue_date", _to_date)
        maturity = _field("maturity_date", "maturity_date", _to_date)
        spread = _detect_rate_scale(
            _field("coupon_rate", "coupon_rate", lambda v: _to_float(v, "coupon_rate"))
        )
        freq = _field(
            "frequency", "frequency",
            lambda v: _to_int(v, "frequency", 1), default=1, required=False
        )
        dcc = _field(
            "day_count", "day_count",
            lambda v: _to_day_count(v, DayCount.NL_365),
            default=DayCount.NL_365, required=False,
        )
        flat_infl = row.get("flat_inflation")
        if flat_infl is not None and not (isinstance(flat_infl, float) and pd.isna(flat_infl)) and flat_infl != "":
            flat_infl = _detect_rate_scale(_to_float(flat_infl, "flat_inflation"))
        else:
            flat_infl = None
        return TESIPC(
            isin=isin or (cat.ref if cat else "TES_IPC"),
            issue_date=issue, maturity_date=maturity,
            coupon_rate=spread, frequency=freq, notional=notional,
            day_count=dcc, currency="COP",
            flat_inflation=flat_infl,
            description=description or (cat.description if cat else ""),
        )

    if raw_type == "TES_GLOBAL":
        # Global TES (sovereign hard currency). Catalog provides ISIN-keyed
        # contractual data; currency comes from the catalog (USD/EUR).
        issue = _field("issue_date", "issue_date", _to_date)
        maturity = _field("maturity_date", "maturity_date", _to_date)
        coupon = _detect_rate_scale(
            _field("coupon_rate", "coupon_rate", lambda v: _to_float(v, "coupon_rate"))
        )
        freq = _field(
            "frequency", "frequency",
            lambda v: _to_int(v, "frequency", 2), default=2, required=False,
        )
        dcc = _field(
            "day_count", "day_count",
            lambda v: _to_day_count(v, DayCount.THIRTY_360),
            default=DayCount.THIRTY_360, required=False,
        )
        currency = (cat.currency if cat else
                    str(row.get("currency", "USD")).strip() or "USD")
        return GlobalBond(
            isin=isin or (cat.ref if cat else "TES_GLOBAL"),
            issue_date=issue, maturity_date=maturity,
            coupon_rate=coupon, frequency=freq, notional=notional,
            day_count=dcc, currency=currency,
            description=description or (cat.description if cat else ""),
        )

    if raw_type == "CORP_FIJA":
        issue = _to_date(row["issue_date"])
        maturity = _to_date(row["maturity_date"])
        coupon = _detect_rate_scale(_to_float(row["coupon_rate"], "coupon_rate"))
        freq = _to_int(row.get("frequency"), "frequency", 2)
        dcc = _to_day_count(row.get("day_count"), DayCount.THIRTY_360)
        currency = str(row.get("currency", "COP")).strip() or "COP"
        return CorporateFixedRate(
            isin=isin, issue_date=issue, maturity_date=maturity,
            coupon_rate=coupon, frequency=freq, notional=notional,
            day_count=dcc, currency=currency, description=description,
        )

    if raw_type == "CORP_IPC":
        issue = _to_date(row["issue_date"])
        maturity = _to_date(row["maturity_date"])
        spread = _detect_rate_scale(_to_float(row["coupon_rate"], "coupon_rate"))
        freq = _to_int(row.get("frequency"), "frequency", 2)
        dcc = _to_day_count(row.get("day_count"), DayCount.THIRTY_360)
        flat_infl = row.get("flat_inflation")
        if flat_infl is not None and not (isinstance(flat_infl, float) and pd.isna(flat_infl)) and flat_infl != "":
            flat_infl = _detect_rate_scale(_to_float(flat_infl, "flat_inflation"))
        else:
            flat_infl = None
        return CorporateIPC(
            isin=isin, issue_date=issue, maturity_date=maturity,
            coupon_rate=spread, frequency=freq, notional=notional,
            day_count=dcc, currency="COP",
            flat_inflation=flat_infl, description=description,
        )

    if raw_type == "GLOBAL":
        issue = _to_date(row["issue_date"])
        maturity = _to_date(row["maturity_date"])
        coupon = _detect_rate_scale(_to_float(row["coupon_rate"], "coupon_rate"))
        freq = _to_int(row.get("frequency"), "frequency", 2)
        dcc = _to_day_count(row.get("day_count"), DayCount.THIRTY_360)
        currency = str(row.get("currency", "USD")).strip() or "USD"
        return GlobalBond(
            isin=isin, issue_date=issue, maturity_date=maturity,
            coupon_rate=coupon, frequency=freq, notional=notional,
            day_count=dcc, currency=currency, description=description,
        )

    if raw_type == "ZERO":
        issue = _to_date(row.get("issue_date") or row.get("maturity_date"))
        maturity = _to_date(row["maturity_date"])
        dcc = _to_day_count(row.get("day_count"), DayCount.ACT_365)
        currency = str(row.get("currency", "COP")).strip() or "COP"
        return ZeroCouponBond(
            isin=isin, issue_date=issue, maturity_date=maturity,
            coupon_rate=0.0, frequency=1, notional=notional,
            day_count=dcc, currency=currency, description=description,
        )

    if raw_type == "GENERIC":
        issue = _to_date(row["issue_date"])
        maturity = _to_date(row["maturity_date"])
        coupon = _detect_rate_scale(_to_float(row["coupon_rate"], "coupon_rate"))
        freq = _to_int(row.get("frequency"), "frequency", 1)
        dcc = _to_day_count(row.get("day_count"), DayCount.ACT_365)
        currency = str(row.get("currency", "COP")).strip() or "COP"
        return Bond(
            isin=isin, issue_date=issue, maturity_date=maturity,
            coupon_rate=coupon, frequency=freq, notional=notional,
            day_count=dcc, currency=currency, description=description,
        )

    raise InstrumentBuildError(f"unhandled instrument_type: {raw_type}")
