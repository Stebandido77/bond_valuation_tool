"""
utils.helpers
=============

Small generic helpers used across the package.
"""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd

from core.cashflows import CashFlow


def cashflows_to_df(flows: List[CashFlow]) -> pd.DataFrame:
    """Tidy DataFrame view of a cashflow schedule."""
    return pd.DataFrame(
        [
            {
                "Period": cf.period,
                "Accrual Start": cf.accrual_start,
                "Accrual End": cf.accrual_end,
                "Payment Date": cf.payment_date,
                "Year Fraction": cf.year_fraction,
                "Coupon Rate": cf.coupon_rate,
                "Notional": cf.notional,
                "Interest": cf.interest,
                "Principal": cf.principal,
                "Total Cashflow": cf.total,
            }
            for cf in flows
        ]
    )


def fmt_currency(value: float, currency: str = "COP", decimals: int = 0) -> str:
    if not np.isfinite(value):
        return "—"
    return f"{currency} {value:,.{decimals}f}"


def fmt_pct(value: float, decimals: int = 4) -> str:
    if not np.isfinite(value):
        return "—"
    return f"{value:.{decimals}f}%"


def fmt_rate(value: float, decimals: int = 4) -> str:
    if not np.isfinite(value):
        return "—"
    return f"{value*100:.{decimals}f}%"


def to_excel_bytes(named_frames: Iterable[Tuple[str, pd.DataFrame]]) -> bytes:
    """Pack one or more DataFrames into an Excel file in memory."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, frame in named_frames:
            safe = name[:31] or "Sheet"
            frame.to_excel(writer, index=False, sheet_name=safe)
    return buf.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def parse_date_input(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return pd.to_datetime(value).date()
