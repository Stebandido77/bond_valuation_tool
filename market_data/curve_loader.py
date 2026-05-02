"""
market_data.curve_loader
========================

Load zero curves from CSV / Excel files into ``ZeroCurve`` objects.

Expected schema (columns can be in any order, names are case-insensitive,
extra columns are ignored):

    curve_name, valuation_date, tenor, days, zero_rate, [discount_factor],
    [currency], [index]

Either ``zero_rate`` or ``discount_factor`` is required. If both are given,
``zero_rate`` takes precedence and ``discount_factor`` is recomputed for
sanity-check; a warning is collected in the returned report.

Rates can be given either as decimal (0.085) or percent (8.5). The loader
auto-detects: if ``max(|rate|) > 1.5`` it assumes percent and divides by 100.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from core.curves import CurvePoint, ZeroCurve
from market_data.interpolation import INTERPOLATORS, Interpolator, LinearInterpolator


_REQUIRED = {"curve_name", "valuation_date", "days"}
_RATE_OR_DF = {"zero_rate", "discount_factor"}
_OPTIONAL = {"tenor", "currency", "index"}


@dataclass
class LoadReport:
    curves: Dict[str, ZeroCurve] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    rows_read: int = 0
    rows_used: int = 0


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _parse_date(value) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        try:
            return pd.to_datetime(value, dayfirst=False).date()
        except Exception:
            return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        try:
            return pd.to_datetime(value, unit="d", origin="1899-12-30").date()
        except Exception:
            return None
    return None


def _detect_rate_scale(values: np.ndarray) -> float:
    """Return a divisor: 100.0 if values look like percent, else 1.0."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 1.0
    if np.nanmax(np.abs(finite)) > 1.5:
        return 100.0
    return 1.0


def load_curves(
    path: Union[str, Path],
    interpolator_name: str = "linear",
    sheet_name: Optional[str] = None,
) -> LoadReport:
    """Load one or more curves from a file.

    Parameters
    ----------
    path : str | Path
        Source file. Extension determines the reader (.csv, .xlsx, .xls).
    interpolator_name : str
        One of ``market_data.interpolation.INTERPOLATORS``.
    sheet_name : str | None
        Excel sheet to read. Defaults to the first sheet.
    """
    path = Path(path)
    report = LoadReport()
    if interpolator_name not in INTERPOLATORS:
        report.errors.append(f"Unknown interpolator: {interpolator_name}")
        return report
    interp_cls = INTERPOLATORS[interpolator_name]

    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        elif path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
            df = pd.read_excel(path, sheet_name=sheet_name or 0)
        else:
            report.errors.append(f"Unsupported extension: {path.suffix}")
            return report
    except Exception as exc:  # pragma: no cover - file IO
        report.errors.append(f"Failed to read {path}: {exc}")
        return report

    df = _normalize_columns(df)
    report.rows_read = len(df)

    missing = _REQUIRED - set(df.columns)
    if missing:
        report.errors.append(f"Missing required columns: {sorted(missing)}")
        return report
    if not (_RATE_OR_DF & set(df.columns)):
        report.errors.append(
            "Either 'zero_rate' or 'discount_factor' must be present."
        )
        return report

    if "zero_rate" in df.columns:
        scale = _detect_rate_scale(df["zero_rate"].to_numpy(dtype=float, na_value=np.nan))
        if scale != 1.0:
            report.warnings.append(
                "Zero rates appear to be in percent — divided by 100."
            )
        df["zero_rate"] = df["zero_rate"].astype(float) / scale

    by_curve = df.groupby("curve_name", dropna=True)
    for curve_name, group in by_curve:
        try:
            val_date_raw = group["valuation_date"].dropna().iloc[0]
        except IndexError:
            report.errors.append(f"Curve '{curve_name}': no valuation_date")
            continue
        val_date = _parse_date(val_date_raw)
        if val_date is None:
            report.errors.append(
                f"Curve '{curve_name}': cannot parse valuation_date '{val_date_raw}'"
            )
            continue

        points: list[CurvePoint] = []
        for _, row in group.iterrows():
            try:
                d = int(row["days"])
            except Exception:
                report.warnings.append(
                    f"Curve '{curve_name}': invalid days '{row.get('days')}', skipped."
                )
                continue
            if d < 0:
                continue
            tenor = str(row.get("tenor", "")) or f"{d}D"
            if "zero_rate" in df.columns and not pd.isna(row.get("zero_rate")):
                r = float(row["zero_rate"])
            elif "discount_factor" in df.columns and not pd.isna(row.get("discount_factor")):
                df_val = float(row["discount_factor"])
                if df_val <= 0:
                    report.warnings.append(
                        f"Curve '{curve_name}': non-positive DF at {d}d, skipped."
                    )
                    continue
                t = d / 365.0
                if t == 0:
                    r = 0.0
                else:
                    r = df_val ** (-1.0 / t) - 1.0  # ANN convention
            else:
                continue
            points.append(CurvePoint(tenor=tenor, days=d, zero_rate=r))

        if not points:
            report.errors.append(f"Curve '{curve_name}': no valid points")
            continue

        currency = "COP"
        if "currency" in group.columns:
            cur = group["currency"].dropna()
            if not cur.empty:
                currency = str(cur.iloc[0])

        curve = ZeroCurve(
            name=str(curve_name),
            valuation_date=val_date,
            points=points,
            convention="ANN",
            currency=currency,
            interpolator=interp_cls(),
        )
        report.curves[str(curve_name)] = curve
        report.rows_used += len(points)

    return report


def curves_to_dataframe(curves: Dict[str, ZeroCurve]) -> pd.DataFrame:
    """Flatten a dict of curves back into a tidy dataframe (for export)."""
    rows = []
    for name, curve in curves.items():
        for p in curve.points:
            rows.append(
                {
                    "curve_name": name,
                    "valuation_date": curve.valuation_date.isoformat(),
                    "tenor": p.tenor,
                    "days": p.days,
                    "zero_rate": p.zero_rate,
                    "discount_factor": curve.discount_factor(
                        curve.valuation_date.fromordinal(
                            curve.valuation_date.toordinal() + p.days
                        )
                    ),
                    "currency": curve.currency,
                }
            )
    return pd.DataFrame(rows)
