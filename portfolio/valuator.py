"""
portfolio.valuator
==================

Bulk valuation of a portfolio.

For every position the engine produces:

    - Yield-based valuation (when the row carries a YTM) and/or
    - Curve-based valuation (using a curve from a curve set, picked by the
      row's ``curve_name`` column or by a global default).

It then aggregates the results: total PV by currency, total DV01,
contribution by book / counterparty / instrument-type. The output is a
tidy ``pd.DataFrame`` plus a small summary dictionary, which the UI can
consume directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core.curves import ZeroCurve

from .loader import PortfolioPosition


@dataclass
class ValuationConfig:
    """Settings for portfolio valuation."""

    valuation_date: date
    curves: Dict[str, ZeroCurve] = field(default_factory=dict)
    default_curve_name: Optional[str] = None
    default_spread_bps: float = 0.0
    fallback_ytm: Optional[float] = None  # used when row lacks both curve and ytm
    method: str = "auto"                  # "yield" | "curve" | "auto" | "both"


def _row_curve_name(row: Dict[str, Any], default: Optional[str]) -> Optional[str]:
    val = row.get("curve_name")
    if val and not (isinstance(val, float) and pd.isna(val)):
        return str(val).strip()
    return default


def _row_ytm(row: Dict[str, Any]) -> Optional[float]:
    val = row.get("ytm")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return f / 100.0 if abs(f) > 1.5 else f


def _row_spread_bps(row: Dict[str, Any], default: float) -> float:
    val = row.get("spread_bps")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def value_portfolio(
    positions: List[PortfolioPosition],
    config: ValuationConfig,
) -> pd.DataFrame:
    """Run valuation across every position. Returns a tidy results frame."""
    rows: list[dict] = []
    for pos in positions:
        bond = pos.instrument
        raw = pos.raw_row
        record: Dict[str, Any] = {
            "trade_id": pos.trade_id,
            "isin": bond.isin,
            "instrument_type": str(raw.get("instrument_type", "")).upper(),
            "description": bond.description,
            "currency": bond.currency,
            "notional": bond.notional,
            "issue_date": bond.issue_date,
            "maturity_date": bond.maturity_date,
            "coupon_rate": bond.coupon_rate,
            "frequency": bond.frequency,
            "day_count": bond.day_count.value,
            "counterparty": pos.counterparty,
            "book": pos.book,
        }

        ytm = _row_ytm(raw)
        spread_bps = _row_spread_bps(raw, config.default_spread_bps)
        curve_name = _row_curve_name(raw, config.default_curve_name)
        curve: Optional[ZeroCurve] = (
            config.curves.get(curve_name) if curve_name else None
        )

        # Decide which method to run
        method = config.method
        if method == "auto":
            if curve is not None:
                method = "curve"
            elif ytm is not None:
                method = "yield"
            elif config.fallback_ytm is not None:
                method = "yield"
                ytm = config.fallback_ytm
            else:
                record["error"] = "no curve and no ytm available"
                rows.append(record)
                continue

        try:
            # Yield-based
            if method in ("yield", "both"):
                use_ytm = ytm if ytm is not None else config.fallback_ytm
                if use_ytm is None:
                    record["yield_error"] = "missing ytm"
                else:
                    res_y = bond.price_yield(config.valuation_date, use_ytm, spread_bps)
                    risk_y = bond.risk_yield(config.valuation_date, use_ytm + spread_bps * 1e-4)
                    record.update({
                        "yield_clean_pct": res_y.clean_price,
                        "yield_dirty_pct": res_y.dirty_price,
                        "yield_pv": res_y.pv,
                        "yield_dv01": risk_y.dv01,
                        "yield_mod_dur": risk_y.modified_duration,
                        "yield_mac_dur": risk_y.macaulay_duration,
                        "yield_convex": risk_y.convexity,
                        "yield_used": use_ytm,
                    })

            # Curve-based
            if method in ("curve", "both"):
                if curve is None:
                    record["curve_error"] = (
                        f"curve '{curve_name}' not in curve set"
                        if curve_name else "no curve_name on row and no default"
                    )
                else:
                    # re-anchor curve on requested valuation date
                    if curve.valuation_date != config.valuation_date:
                        anchored = ZeroCurve(
                            name=curve.name,
                            valuation_date=config.valuation_date,
                            points=list(curve.points),
                            convention=curve.convention,
                            currency=curve.currency,
                            interpolator=curve.interpolator,
                        )
                    else:
                        anchored = curve
                    res_c = bond.price_curve(config.valuation_date, anchored, spread_bps)
                    risk_c = bond.risk_curve(config.valuation_date, anchored, spread_bps)
                    record.update({
                        "curve_used": anchored.name,
                        "curve_clean_pct": res_c.clean_price,
                        "curve_dirty_pct": res_c.dirty_price,
                        "curve_pv": res_c.pv,
                        "curve_dv01": risk_c.dv01,
                        "curve_mod_dur": risk_c.modified_duration,
                        "curve_mac_dur": risk_c.macaulay_duration,
                        "curve_convex": risk_c.convexity,
                    })

        except Exception as exc:
            record["error"] = f"valuation failed: {exc}"

        rows.append(record)

    return pd.DataFrame(rows)


def aggregate(results: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Build the standard aggregation views used by the UI."""
    out: Dict[str, pd.DataFrame] = {}
    if results.empty:
        return out

    # Totals by currency
    pv_col = (
        "curve_pv" if "curve_pv" in results.columns
        else ("yield_pv" if "yield_pv" in results.columns else None)
    )
    dv_col = (
        "curve_dv01" if "curve_dv01" in results.columns
        else ("yield_dv01" if "yield_dv01" in results.columns else None)
    )

    grouped: Dict[str, pd.DataFrame] = {}
    if pv_col:
        agg_dict: Dict[str, Any] = {pv_col: "sum"}
        if dv_col:
            agg_dict[dv_col] = "sum"
        agg_dict["notional"] = "sum"

        for label, key in (("by_currency", "currency"),
                           ("by_book", "book"),
                           ("by_counterparty", "counterparty"),
                           ("by_type", "instrument_type")):
            if key in results.columns:
                grp = results.groupby(key, dropna=False).agg(agg_dict).reset_index()
                grp = grp.rename(columns={pv_col: "PV", dv_col: "DV01"} if dv_col else {pv_col: "PV"})
                grouped[label] = grp

    out.update(grouped)
    return out
