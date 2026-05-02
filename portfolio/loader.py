"""
portfolio.loader
================

Load a portfolio file (CSV or Excel) and turn it into a list of
``PortfolioPosition`` objects ready for valuation.

The expected layout — codified by the bundled template
``data/portfolio_template.csv`` — is intentionally one row per position
with every field needed to build the instrument plus position-level
metadata (counterparty, book, etc.).

A portfolio file can mix instrument types in a single sheet — TES
references will be resolved against the catalog, generic rows must carry
their own contractual data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from instruments.bond import Bond
from instruments.factory import (
    InstrumentBuildError,
    SUPPORTED_TYPES,
    build_instrument,
)


# Required columns for any portfolio row
_REQUIRED_COLS = {"instrument_type", "notional"}

# Recommended columns (warned if missing)
_RECOMMENDED_COLS = {
    "ref", "isin", "issue_date", "maturity_date", "coupon_rate",
    "frequency", "day_count", "currency", "counterparty", "book",
}


@dataclass
class PortfolioPosition:
    """A single position with the built instrument and trade metadata."""

    instrument: Bond
    counterparty: str = ""
    book: str = ""
    trade_id: str = ""
    notes: str = ""
    raw_row: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioLoadReport:
    positions: List[PortfolioPosition] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rows_read: int = 0
    rows_loaded: int = 0


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def load_portfolio(
    path: Union[str, Path],
    sheet_name: Optional[str] = None,
) -> PortfolioLoadReport:
    """Load a portfolio from a CSV or Excel file."""
    path = Path(path)
    report = PortfolioLoadReport()

    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        elif path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
            df = pd.read_excel(path, sheet_name=sheet_name or 0)
        else:
            report.errors.append(
                {"row": -1, "error": f"Unsupported extension: {path.suffix}"}
            )
            return report
    except Exception as exc:
        report.errors.append({"row": -1, "error": f"Failed to read {path}: {exc}"})
        return report

    df = _normalize_columns(df)
    report.rows_read = len(df)

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        report.errors.append(
            {"row": -1, "error": f"Missing required columns: {sorted(missing)}"}
        )
        return report

    for missing_rec in _RECOMMENDED_COLS - set(df.columns):
        report.warnings.append(f"Recommended column missing: '{missing_rec}'")

    for idx, row in df.iterrows():
        try:
            inst = build_instrument(row.to_dict())
        except InstrumentBuildError as exc:
            report.errors.append({"row": int(idx), "error": str(exc), "raw": row.to_dict()})
            continue
        except Exception as exc:
            report.errors.append({"row": int(idx), "error": f"unexpected: {exc}", "raw": row.to_dict()})
            continue

        position = PortfolioPosition(
            instrument=inst,
            counterparty=str(row.get("counterparty", "") or "").strip(),
            book=str(row.get("book", "") or "").strip(),
            trade_id=str(row.get("trade_id", "") or "").strip(),
            notes=str(row.get("notes", "") or "").strip(),
            raw_row=row.to_dict(),
        )
        report.positions.append(position)
        report.rows_loaded += 1

    return report


def supported_instrument_types() -> Dict[str, str]:
    return dict(SUPPORTED_TYPES)
