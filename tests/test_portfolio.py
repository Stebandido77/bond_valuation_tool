"""
tests.test_portfolio
====================

Tests for the new instrument types, the catalog, and the portfolio loader.
"""

from __future__ import annotations

from datetime import date

import pytest

from instruments.corporate import CorporateFixedRate, CorporateIPC, GlobalBond
from instruments.factory import InstrumentBuildError, build_instrument
from instruments.inflation_linked import RealPlusInflation
from instruments.tes import TESIPC, TESTasaFija
from instruments.tes_catalog import all_references, get_reference
from instruments.zero_coupon import ZeroCouponBond
from portfolio.loader import load_portfolio
from portfolio.valuator import ValuationConfig, aggregate, value_portfolio
from market_data.curve_loader import load_curves


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
def test_catalog_returns_known_reference():
    ref = get_reference("TFIT16181030")
    assert ref is not None
    assert ref.kind == "TASA_FIJA"
    assert ref.maturity_date == date(2030, 10, 30)
    assert ref.coupon_rate == pytest.approx(0.075)


def test_catalog_unknown_returns_none():
    assert get_reference("DOES_NOT_EXIST") is None


def test_catalog_lookup_is_case_insensitive():
    assert get_reference("tfit16181030") is not None


# ---------------------------------------------------------------------------
# IPC linker mechanics
# ---------------------------------------------------------------------------
def test_ipc_linker_increases_with_inflation():
    """At higher flat inflation, every cash coupon must be larger."""
    base_kwargs = dict(
        isin="TEST_IPC",
        issue_date=date(2024, 1, 1),
        maturity_date=date(2029, 1, 1),
        coupon_rate=0.04,
        notional=100.0,
    )
    low_infl = RealPlusInflation(flat_inflation=0.02, **base_kwargs)
    high_infl = RealPlusInflation(flat_inflation=0.08, **base_kwargs)
    flows_low = low_infl.cashflows()
    flows_high = high_infl.cashflows()
    for cf_l, cf_h in zip(flows_low, flows_high):
        assert cf_h.interest > cf_l.interest


def test_ipc_zero_inflation_equals_real_only():
    """With flat_inflation=0 the bond reduces to a plain real-rate bond."""
    bond_ipc = RealPlusInflation(
        isin="TEST_IPC",
        issue_date=date(2024, 1, 1),
        maturity_date=date(2027, 1, 1),
        coupon_rate=0.04, notional=100.0, flat_inflation=0.0,
    )
    bond_plain = TESTasaFija(
        isin="TEST_PLAIN",
        issue_date=date(2024, 1, 1),
        maturity_date=date(2027, 1, 1),
        coupon_rate=0.04, notional=100.0,
    )
    res_ipc = bond_ipc.price_yield(date(2024, 1, 1), 0.04)
    res_plain = bond_plain.price_yield(date(2024, 1, 1), 0.04)
    assert res_ipc.dirty_price == pytest.approx(res_plain.dirty_price, abs=1e-8)


# ---------------------------------------------------------------------------
# Zero-coupon
# ---------------------------------------------------------------------------
def test_zero_coupon_has_one_cashflow():
    bond = ZeroCouponBond(
        isin="ZC", issue_date=date(2024, 1, 1), maturity_date=date(2027, 1, 1),
        notional=1000.0,
    )
    flows = bond.cashflows()
    # accruals are still discretized by frequency=1 so we always have one period
    assert len(flows) == 3
    # all interest cashflows must be zero
    assert all(cf.interest == 0.0 for cf in flows)
    # principal lives only on the last flow
    assert flows[-1].principal == 1000.0
    assert sum(cf.principal for cf in flows[:-1]) == 0.0


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def test_factory_resolves_tes_via_catalog():
    row = {
        "instrument_type": "TES_TASA_FIJA",
        "ref": "TFIT16181030",
        "notional": 1_000_000.0,
    }
    inst = build_instrument(row)
    assert isinstance(inst, TESTasaFija)
    assert inst.maturity_date == date(2030, 10, 30)
    assert inst.coupon_rate == pytest.approx(0.075)


def test_factory_falls_back_to_row_data_when_catalog_missing():
    row = {
        "instrument_type": "TES_TASA_FIJA",
        "ref": "UNKNOWN_REF",
        "issue_date": "2024-06-01",
        "maturity_date": "2030-06-01",
        "coupon_rate": 0.085,
        "notional": 1_000_000.0,
    }
    inst = build_instrument(row)
    assert inst.maturity_date == date(2030, 6, 1)
    assert inst.coupon_rate == pytest.approx(0.085)


def test_factory_handles_percent_coupon_input():
    """Pasting 8.5 instead of 0.085 must be auto-detected and rescaled."""
    row = {
        "instrument_type": "CORP_FIJA",
        "isin": "TEST",
        "issue_date": "2024-01-01",
        "maturity_date": "2029-01-01",
        "coupon_rate": 8.5,  # percent
        "notional": 1_000_000.0,
    }
    inst = build_instrument(row)
    assert inst.coupon_rate == pytest.approx(0.085)


def test_factory_rejects_unknown_type():
    with pytest.raises(InstrumentBuildError):
        build_instrument({"instrument_type": "FRN", "notional": 1.0})


# ---------------------------------------------------------------------------
# End-to-end portfolio
# ---------------------------------------------------------------------------
def test_end_to_end_portfolio_template(tmp_path):
    """Load the bundled template and value it without errors."""
    from pathlib import Path
    template = Path(__file__).resolve().parent.parent / "data" / "portfolio_template.csv"
    sample_curves = Path(__file__).resolve().parent.parent / "data" / "sample_curve.csv"

    curves = load_curves(sample_curves).curves
    report = load_portfolio(template)

    assert report.rows_loaded > 0
    assert len(report.errors) == 0, f"unexpected errors: {report.errors}"

    cfg = ValuationConfig(
        valuation_date=date(2025, 9, 1),
        curves=curves,
        method="auto",
        fallback_ytm=0.10,
    )
    results = value_portfolio(report.positions, cfg)
    # No row-level error column
    if "error" in results.columns:
        assert results["error"].isna().all(), results[results["error"].notna()][["trade_id", "error"]]

    # Aggregations work
    agg = aggregate(results)
    assert "by_currency" in agg
    assert "by_book" in agg

    # Total PV must be > 0 in COP
    cop_total = agg["by_currency"].set_index("currency").loc["COP", "PV"]
    assert cop_total > 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
