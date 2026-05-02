"""
ui.app
======

Bloomberg Terminal-style bond valuation workbench.

Layout philosophy:
    - Minimal sidebar: only mode switch + valuation date
    - All instrument/method inputs live in the main area, organized in
      horizontal panels — like a Bloomberg DES screen
    - Dense tile grids for results, terminal-amber for active values
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.curves import ZeroCurve  # noqa: E402
from core.day_count import DayCount  # noqa: E402
from instruments.bond import Bond  # noqa: E402
from instruments.corporate import (  # noqa: E402
    CorporateFixedRate, CorporateIPC, GlobalBond,
)
from instruments.tes import TESIPC, TESTasaFija, TESUVR  # noqa: E402
from instruments.tes_catalog import all_references  # noqa: E402
from instruments.zero_coupon import ZeroCouponBond  # noqa: E402
from market_data.curve_loader import curves_to_dataframe, load_curves  # noqa: E402
from market_data.interpolation import INTERPOLATORS  # noqa: E402
from portfolio.loader import load_portfolio  # noqa: E402
from portfolio.valuator import ValuationConfig, aggregate, value_portfolio  # noqa: E402
from ui.components import (  # noqa: E402
    header, inject_theme, section, styled_dataframe, subsection, tile_grid,
)
from utils.helpers import (  # noqa: E402
    cashflows_to_df, fmt_currency, fmt_pct, to_csv_bytes, to_excel_bytes,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="BVW Terminal",
    page_icon="▸",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()


# ---------------------------------------------------------------------------
# Sidebar — minimal
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div style="color:#ffa500; font-weight:700; font-size:13px; letter-spacing:2px; '
        'padding:6px 0 14px 0; border-bottom:1px solid #2a2a2a; margin-bottom:14px;">'
        '▸ BVW TERMINAL</div>',
        unsafe_allow_html=True,
    )
    workspace = st.radio(
        "MODE",
        ["Single Bond", "Portfolio"],
        index=0,
        label_visibility="visible",
    )
    valuation_date = st.date_input(
        "VALUATION DATE", value=date.today(),
        label_visibility="visible",
    )
    st.markdown("---")
    st.markdown(
        '<div style="font-size:9px; color:#555; letter-spacing:1px; padding:8px 0;">'
        'BOND VALUATION WORKBENCH<br>'
        'OPEN-SOURCE QUANT TOOLING<br>'
        'V1.0</div>',
        unsafe_allow_html=True,
    )

if "curves" not in st.session_state:
    st.session_state["curves"] = {}


# ---------------------------------------------------------------------------
# Curve loader (shared, compact)
# ---------------------------------------------------------------------------
def render_curve_loader() -> dict:
    section("Market Data · Zero Curves")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        uploaded = st.file_uploader(
            "UPLOAD CURVE FILE (CSV/XLSX)",
            type=["csv", "xlsx", "xls"], key="curve_upload",
            label_visibility="collapsed",
        )
    with c2:
        interp_choice = st.selectbox(
            "INTERPOLATION", options=list(INTERPOLATORS.keys()), index=0,
            label_visibility="visible",
        )
    with c3:
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        if st.button("LOAD SAMPLES", use_container_width=True, key="load_sample"):
            sample = ROOT / "data" / "sample_curve.csv"
            if sample.exists():
                report = load_curves(sample, interpolator_name=interp_choice)
                st.session_state["curves"].update(report.curves)

    if uploaded is not None:
        tmp = ROOT / "data" / f"_uploaded_{uploaded.name}"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(uploaded.read())
        report = load_curves(tmp, interpolator_name=interp_choice)
        st.session_state["curves"].update(report.curves)
        for e in report.errors:
            st.error(e)
        for w in report.warnings:
            st.warning(w)

    if st.session_state["curves"]:
        names = list(st.session_state["curves"].keys())
        loaded_html = ' &nbsp;·&nbsp; '.join(
            f'<span style="color:#00d4ff;">{n}</span>' for n in names
        )
        st.markdown(
            f'<div style="font-size:10px; color:#666; letter-spacing:1px; padding:4px 0;">'
            f'LOADED CURVES: {loaded_html}</div>',
            unsafe_allow_html=True,
        )
    return st.session_state["curves"]


# ===========================================================================
#  SINGLE BOND MODE
# ===========================================================================
def run_single_bond_mode() -> None:
    header("BVW · BOND VALUATION", "single instrument analysis", "QUANT")

    # ===== TES CATALOG QUICK SELECTOR =====
    section("TES Catalog · Quick Lookup")
    cat_all = all_references()
    cat_options = ["— Custom / Manual entry —"] + sorted([
        f"{r.ref}  ·  {r.kind}  ·  {r.description}" for r in cat_all.values()
    ])
    sel_col1, sel_col2 = st.columns([3, 1])
    with sel_col1:
        catalog_choice = st.selectbox(
            "SELECT REFERENCE FROM CATALOG (TYPE TO SEARCH)",
            options=cat_options, index=0,
            help="Pick a TES reference to autofill ISIN, dates, coupon, frequency and day count.",
        )
    with sel_col2:
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        if st.button("CLEAR SELECTION", use_container_width=True):
            st.session_state["_catalog_pick"] = None
            st.rerun()

    # Resolve picked reference
    picked_ref = None
    if catalog_choice and not catalog_choice.startswith("—"):
        ref_id = catalog_choice.split("·")[0].strip()
        picked_ref = cat_all.get(ref_id)

    # Defaults — overridden if catalog reference picked
    today = date.today()
    if picked_ref is not None:
        kind_to_label = {
            "TASA_FIJA": "TES Tasa Fija (COP)", "UVR": "TES UVR",
            "IPC": "TES IPC", "GLOBAL": "Global Bond (USD/EUR)",
        }
        default_bond_type = kind_to_label.get(picked_ref.kind, "Generic Fixed-Rate Bond")
        default_isin = picked_ref.ref
        default_issue = picked_ref.issue_date
        default_maturity = picked_ref.maturity_date
        default_coupon = picked_ref.coupon_rate * 100
        default_frequency = picked_ref.frequency
        default_currency = picked_ref.currency
        default_dcc = picked_ref.day_count
    else:
        default_bond_type = "TES Tasa Fija (COP)"
        default_isin = "DEMO_BOND_2030"
        default_issue = date(today.year - 2, today.month, 1)
        default_maturity = date(today.year + 5, today.month, 1)
        default_coupon = 7.00
        default_frequency = 1
        default_currency = "COP"
        default_dcc = DayCount.NL_365

    # ===== INSTRUMENT PANEL =====
    section("Instrument Definition")
    bond_types = [
        "TES Tasa Fija (COP)", "TES UVR", "TES IPC",
        "Corporate Fixed Rate (COP)", "Corporate IPC",
        "Global Bond (USD/EUR)", "Zero-Coupon Bond",
        "Generic Fixed-Rate Bond",
    ]
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1:
        # Use the catalog default + key tied to selection so widget refreshes
        bond_type_label = st.selectbox(
            "BOND TYPE", bond_types,
            index=bond_types.index(default_bond_type),
            key=f"bt_{catalog_choice}",
        )
    with r1c2:
        isin = st.text_input("ISIN / ID", value=default_isin, key=f"isin_{catalog_choice}")
    with r1c3:
        notional = st.number_input(
            "NOTIONAL", min_value=1.0, value=100_000_000.0, step=1_000_000.0,
            format="%.0f",
        )
    with r1c4:
        currency = st.text_input("CURRENCY", value=default_currency, key=f"cur_{catalog_choice}")

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        issue_date = st.date_input("ISSUE DATE", value=default_issue, key=f"id_{catalog_choice}")
    with r2c2:
        maturity_date = st.date_input("MATURITY DATE", value=default_maturity, key=f"md_{catalog_choice}")
    with r2c3:
        coupon_pct = st.number_input(
            "COUPON RATE (%)", min_value=0.0, max_value=50.0,
            value=float(default_coupon), step=0.25, format="%.4f",
            key=f"cp_{catalog_choice}",
            help="For inflation-linked bonds (TES IPC / Corporate IPC) this is the real spread.",
        )
    with r2c4:
        freq_options = [1, 2, 4, 12]
        frequency = st.selectbox(
            "FREQUENCY", options=freq_options,
            index=freq_options.index(default_frequency) if default_frequency in freq_options else 0,
            format_func=lambda x: {1: "Annual", 2: "Semi-Annual", 4: "Quarterly", 12: "Monthly"}[x],
            key=f"fq_{catalog_choice}",
        )

    r3c1, r3c2, r3c3, r3c4 = st.columns(4)
    with r3c1:
        dcc_values = [c.value for c in DayCount]
        convention_label = st.selectbox(
            "DAY COUNT", options=dcc_values,
            index=dcc_values.index(default_dcc.value),
            key=f"dc_{catalog_choice}",
        )
        convention = DayCount(convention_label)
    flat_inflation_pct = None
    with r3c2:
        if bond_type_label in ("TES IPC", "Corporate IPC"):
            flat_inflation_pct = st.number_input(
                "INFLATION PROJ. (%)", min_value=0.0, max_value=50.0, value=5.5, step=0.25, format="%.4f",
            )
        else:
            st.markdown("&nbsp;", unsafe_allow_html=True)
    # placeholders
    with r3c3:
        st.markdown("&nbsp;", unsafe_allow_html=True)
    with r3c4:
        st.markdown("&nbsp;", unsafe_allow_html=True)

    # ===== METHOD & PRICING INPUTS =====
    section("Pricing Method")
    m1, m2, m3, m4 = st.columns([2, 1, 1, 1])
    with m1:
        method = st.radio(
            "METHOD", ["Yield (manual)", "Curve (market data)", "Both — comparative"],
            index=2, horizontal=True,
        )
    with m2:
        yld_pct = st.number_input("YTM (%)", min_value=-50.0, max_value=50.0, value=8.50, step=0.25, format="%.4f")
    with m3:
        spread_yield_bps = st.number_input("YIELD SPREAD (bps)", min_value=-1000.0, max_value=1000.0, value=0.0, step=5.0)
    with m4:
        spread_curve_bps = st.number_input("CURVE SPREAD (bps)", min_value=-1000.0, max_value=1000.0, value=0.0, step=5.0)

    # ===== CURVE LOADER =====
    curves = render_curve_loader()
    selected_curve_name = None
    if curves:
        selected_curve_name = st.selectbox("ACTIVE CURVE FOR PRICING", options=list(curves.keys()), index=0)

    # ===== BUILD INSTRUMENT =====
    common = dict(
        isin=isin, issue_date=issue_date, maturity_date=maturity_date,
        coupon_rate=coupon_pct / 100.0, frequency=int(frequency), notional=float(notional),
        day_count=convention,
    )
    try:
        if bond_type_label == "TES Tasa Fija (COP)":
            bond: Bond = TESTasaFija(currency="COP", **common)
        elif bond_type_label == "TES UVR":
            bond = TESUVR(currency="UVR", **common)
        elif bond_type_label == "TES IPC":
            bond = TESIPC(currency="COP",
                          flat_inflation=flat_inflation_pct / 100.0 if flat_inflation_pct else None,
                          **common)
        elif bond_type_label == "Corporate Fixed Rate (COP)":
            bond = CorporateFixedRate(currency=currency or "COP", **common)
        elif bond_type_label == "Corporate IPC":
            bond = CorporateIPC(currency="COP",
                                flat_inflation=flat_inflation_pct / 100.0 if flat_inflation_pct else None,
                                **common)
        elif bond_type_label == "Global Bond (USD/EUR)":
            bond = GlobalBond(currency=currency or "USD", **common)
        elif bond_type_label == "Zero-Coupon Bond":
            zc_common = {k: v for k, v in common.items() if k != "coupon_rate"}
            bond = ZeroCouponBond(currency=currency or "COP", **zc_common)
        else:
            bond = Bond(currency=currency or "COP", **common)
    except Exception as exc:
        st.error(f"INSTRUMENT BUILD FAILED: {exc}")
        st.stop()

    # ===== PRICE =====
    flows = bond.cashflows()
    yld_res = bond.price_yield(valuation_date, yld_pct / 100.0, spread_yield_bps)
    yld_risk = bond.risk_yield(valuation_date, yld_pct / 100.0 + spread_yield_bps * 1e-4)

    curve_res = None
    curve_risk = None
    active_curve = None
    if selected_curve_name:
        active_curve = curves[selected_curve_name]
        if active_curve.valuation_date != valuation_date:
            active_curve = ZeroCurve(
                name=active_curve.name, valuation_date=valuation_date,
                points=list(active_curve.points), convention=active_curve.convention,
                currency=active_curve.currency, interpolator=active_curve.interpolator,
            )
        curve_res = bond.price_curve(valuation_date, active_curve, spread_curve_bps)
        curve_risk = bond.risk_curve(valuation_date, active_curve, spread_curve_bps)

    # ===== RESULTS =====
    section("Valuation Results")

    def render_tiles(label: str, res, risk, tone: str = "amber") -> None:
        subsection(label)
        tile_grid([
            {"label": "Clean Price", "value": fmt_pct(res.clean_price, 4), "tone": tone},
            {"label": "Dirty Price", "value": fmt_pct(res.dirty_price, 4), "tone": tone},
            {"label": "Accrued",     "value": fmt_pct(res.accrued, 4)},
            {"label": "PV", "value": fmt_currency(res.pv, bond.currency, 0), "tone": "cyan"},
            {"label": "DV01", "value": fmt_currency(risk.dv01, bond.currency, 0), "sub": "PER 1 BP"},
            {"label": "Mod Duration", "value": f"{risk.modified_duration:.4f}", "sub": "YEARS"},
            {"label": "Mac Duration", "value": f"{risk.macaulay_duration:.4f}", "sub": "YEARS"},
            {"label": "Convexity",    "value": f"{risk.convexity:.4f}"},
        ], columns_per_row=4)

    if method in ("Yield (manual)", "Both — comparative"):
        render_tiles("By Yield (YTM)", yld_res, yld_risk, tone="amber")
    if method in ("Curve (market data)", "Both — comparative"):
        if curve_res is not None:
            render_tiles("By Curve (Market Data)", curve_res, curve_risk, tone="cyan")
        else:
            st.info("LOAD AND SELECT A CURVE TO ENABLE CURVE-BASED VALUATION")

    # Comparative table
    comp_df = None
    if method == "Both — comparative" and curve_res is not None:
        section("Comparative · Yield vs Curve")
        rows = [
            ("Clean Price",    yld_res.clean_price, curve_res.clean_price, "%"),
            ("Dirty Price",    yld_res.dirty_price, curve_res.dirty_price, "%"),
            ("Accrued",        yld_res.accrued,     curve_res.accrued,     "%"),
            ("PV",             yld_res.pv,          curve_res.pv,          bond.currency),
            ("DV01",           yld_risk.dv01,       curve_risk.dv01,       bond.currency),
            ("Modified Dur.",  yld_risk.modified_duration, curve_risk.modified_duration, "years"),
            ("Convexity",      yld_risk.convexity,  curve_risk.convexity,  ""),
        ]
        comp_df = pd.DataFrame([
            {"Metric": n, "Yield-based": a, "Curve-based": b,
             "Δ (curve − yield)": b - a, "Unit": u}
            for n, a, b, u in rows
        ])
        styled_dataframe(
            comp_df.style.format({
                "Yield-based": "{:,.4f}", "Curve-based": "{:,.4f}", "Δ (curve − yield)": "{:,.4f}",
            }),
            height=290,
        )

    # ===== TABS =====
    tab_cf, tab_curve, tab_scen, tab_export = st.tabs([
        "CASHFLOWS", "CURVE", "SCENARIOS · BUCKET DV01", "EXPORTS",
    ])

    with tab_cf:
        section("Cashflow Schedule")
        cf_df = cashflows_to_df(flows)
        styled_dataframe(cf_df.style.format({
            "Year Fraction": "{:.6f}", "Coupon Rate": "{:.4%}",
            "Notional": "{:,.2f}", "Interest": "{:,.2f}",
            "Principal": "{:,.2f}", "Total Cashflow": "{:,.2f}",
        }), height=420)

    with tab_curve:
        section("Active Zero Curve")
        if selected_curve_name:
            curve = curves[selected_curve_name]
            df_pts = pd.DataFrame([
                {"Tenor": p.tenor, "Days": p.days, "Zero Rate (%)": p.zero_rate * 100}
                for p in curve.points
            ])
            c1, c2 = st.columns([1, 2])
            with c1:
                tile_grid([
                    {"label": "Curve Name", "value": curve.name, "tone": "cyan"},
                    {"label": "Anchor Date", "value": curve.valuation_date.isoformat()},
                    {"label": "Currency", "value": curve.currency},
                    {"label": "Convention", "value": curve.convention},
                ], columns_per_row=2)
                styled_dataframe(df_pts.style.format({"Zero Rate (%)": "{:.4f}"}), height=350)
            with c2:
                st.line_chart(df_pts.set_index("Days")[["Zero Rate (%)"]], height=440)
        else:
            st.info("NO CURVE SELECTED")

    with tab_scen:
        section("Parallel Shocks")
        if curve_res is not None:
            scen_bps = [-100, -50, -10, -1, 0, 1, 10, 50, 100]
            prices = bond.parallel_scenarios(valuation_date, active_curve, scen_bps, spread_curve_bps)
            scen_df = pd.DataFrame([
                {"Shock (bps)": s, "Dirty Price (%)": prices[float(s)],
                 "ΔPrice vs base (%)": prices[float(s)] - prices[0.0]}
                for s in scen_bps
            ])
            c1, c2 = st.columns([1, 2])
            with c1:
                styled_dataframe(scen_df.style.format({
                    "Dirty Price (%)": "{:.6f}", "ΔPrice vs base (%)": "{:+.6f}",
                }), height=320)
            with c2:
                st.line_chart(scen_df.set_index("Shock (bps)")[["Dirty Price (%)"]], height=320)

            section("Bucket DV01 · Per Pillar")
            bdv = bond.bucket_dv01(valuation_date, active_curve, spread_curve_bps)
            bdv_df = pd.DataFrame([{"Tenor": k, "DV01 (per 1bp)": v} for k, v in bdv.items()])
            c3, c4 = st.columns([1, 2])
            with c3:
                styled_dataframe(bdv_df.style.format({"DV01 (per 1bp)": "{:,.2f}"}), height=320)
            with c4:
                st.bar_chart(bdv_df.set_index("Tenor"), height=320)
        else:
            st.info("LOAD A CURVE TO COMPUTE SCENARIOS AND BUCKET DV01")

    with tab_export:
        section("Downloads")
        cf_df = cashflows_to_df(flows)
        yield_summary = pd.DataFrame([
            {"Metric": "Clean Price (%)", "Value": yld_res.clean_price},
            {"Metric": "Dirty Price (%)", "Value": yld_res.dirty_price},
            {"Metric": "Accrued (%)", "Value": yld_res.accrued},
            {"Metric": "PV", "Value": yld_res.pv},
            {"Metric": "DV01", "Value": yld_risk.dv01},
            {"Metric": "Modified Duration", "Value": yld_risk.modified_duration},
            {"Metric": "Macaulay Duration", "Value": yld_risk.macaulay_duration},
            {"Metric": "Convexity", "Value": yld_risk.convexity},
        ])
        sheets = [("Cashflows", cf_df), ("Yield Valuation", yield_summary)]
        if curve_res is not None:
            curve_summary = pd.DataFrame([
                {"Metric": "Clean Price (%)", "Value": curve_res.clean_price},
                {"Metric": "Dirty Price (%)", "Value": curve_res.dirty_price},
                {"Metric": "Accrued (%)", "Value": curve_res.accrued},
                {"Metric": "PV", "Value": curve_res.pv},
                {"Metric": "DV01", "Value": curve_risk.dv01},
                {"Metric": "Modified Duration", "Value": curve_risk.modified_duration},
                {"Metric": "Macaulay Duration", "Value": curve_risk.macaulay_duration},
                {"Metric": "Convexity", "Value": curve_risk.convexity},
            ])
            sheets.append(("Curve Valuation", curve_summary))
            sheets.append((
                "Curve Points",
                curves_to_dataframe({selected_curve_name: curves[selected_curve_name]}),
            ))
            if comp_df is not None:
                sheets.append(("Comparative", comp_df))

        excel_bytes = to_excel_bytes(sheets)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                "▼ EXCEL · ALL SHEETS", data=excel_bytes,
                file_name=f"bond_valuation_{bond.isin}_{valuation_date.isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "▼ CASHFLOWS CSV", data=to_csv_bytes(cf_df),
                file_name=f"cashflows_{bond.isin}.csv", mime="text/csv",
                use_container_width=True,
            )
        with c3:
            if selected_curve_name:
                st.download_button(
                    "▼ CURVE CSV",
                    data=to_csv_bytes(curves_to_dataframe({selected_curve_name: curves[selected_curve_name]})),
                    file_name=f"curve_{selected_curve_name}.csv", mime="text/csv",
                    use_container_width=True,
                )

    # ===== EXPANDABLE TES CATALOG TABLE =====
    with st.expander("▸ TES CATALOG · FULL REFERENCE TABLE", expanded=False):
        cat_df = pd.DataFrame([
            {
                "Reference": r.ref, "Kind": r.kind, "Description": r.description,
                "Issue": r.issue_date, "Maturity": r.maturity_date,
                "Coupon": r.coupon_rate, "Freq": r.frequency,
                "Day Count": r.day_count.value, "CCY": r.currency,
            }
            for r in sorted(cat_all.values(), key=lambda r: (r.kind, r.maturity_date))
        ])
        st.markdown(
            f'<div style="font-size:10px; color:#888; letter-spacing:1px; margin-bottom:6px;">'
            f'{len(cat_df)} REFERENCES &nbsp;·&nbsp; '
            f'{(cat_df["Kind"] == "TASA_FIJA").sum()} TASA FIJA &nbsp;·&nbsp; '
            f'{(cat_df["Kind"] == "UVR").sum()} UVR &nbsp;·&nbsp; '
            f'{(cat_df["Kind"] == "IPC").sum()} IPC &nbsp;·&nbsp; '
            f'{(cat_df["Kind"] == "GLOBAL").sum()} GLOBAL'
            f'</div>',
            unsafe_allow_html=True,
        )
        styled_dataframe(
            cat_df.style.format({"Coupon": "{:.4%}"}),
            height=400,
        )


# ===========================================================================
#  PORTFOLIO MODE
# ===========================================================================
def run_portfolio_mode() -> None:
    header("BVW · PORTFOLIO VALUATION", "bulk pricing & aggregations", "RISK")

    # ===== TOP CONFIG ROW =====
    section("Portfolio Configuration")
    p1, p2, p3 = st.columns(3)
    with p1:
        valuation_method = st.selectbox(
            "VALUATION METHOD",
            ["Auto (curve if available, else yield)", "Curve only", "Yield only", "Both (comparative)"],
            index=0,
        )
        method_map = {
            "Auto (curve if available, else yield)": "auto",
            "Curve only": "curve", "Yield only": "yield",
            "Both (comparative)": "both",
        }
    with p2:
        default_spread_bps = st.number_input(
            "DEFAULT SPREAD (bps)", min_value=-1000.0, max_value=1000.0, value=0.0, step=5.0,
        )
    with p3:
        fallback_ytm_pct = st.number_input(
            "FALLBACK YTM (%)", min_value=-50.0, max_value=50.0, value=10.0, step=0.25,
        )

    # ===== CURVES =====
    curves = render_curve_loader()

    # ===== PORTFOLIO FILE =====
    section("Portfolio File")
    pf1, pf2, pf3 = st.columns([2, 1, 1])
    with pf1:
        port_file = st.file_uploader(
            "UPLOAD PORTFOLIO (CSV/XLSX)",
            type=["csv", "xlsx", "xls"], key="portfolio_upload",
            label_visibility="collapsed",
        )
    with pf2:
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        st.download_button(
            "▼ TEMPLATE",
            data=(ROOT / "data" / "portfolio_template.csv").read_bytes(),
            file_name="portfolio_template.csv", mime="text/csv",
            use_container_width=True,
        )
    with pf3:
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        if st.button("LOAD SAMPLE PORTFOLIO", use_container_width=True):
            st.session_state["_use_sample_portfolio"] = True

    portfolio_path = None
    if port_file is not None:
        tmp = ROOT / "data" / f"_uploaded_{port_file.name}"
        tmp.write_bytes(port_file.read())
        portfolio_path = tmp
    elif st.session_state.get("_use_sample_portfolio"):
        portfolio_path = ROOT / "data" / "portfolio_template.csv"

    if portfolio_path is None:
        st.info("UPLOAD A PORTFOLIO FILE OR LOAD THE SAMPLE TO BEGIN")
        with st.expander("▸ BUILT-IN TES CATALOG"):
            cat = all_references()
            cat_df = pd.DataFrame([
                {
                    "Reference": r.ref, "Kind": r.kind, "Description": r.description,
                    "Issue": r.issue_date, "Maturity": r.maturity_date,
                    "Coupon": r.coupon_rate, "Freq": r.frequency,
                    "Day Count": r.day_count.value, "Currency": r.currency,
                }
                for r in cat.values()
            ])
            styled_dataframe(cat_df.style.format({"Coupon": "{:.4%}"}), height=380)
        return

    port_report = load_portfolio(portfolio_path)
    if port_report.errors:
        st.error(f"{len(port_report.errors)} ROW(S) FAILED TO LOAD")
        with st.expander("▸ SHOW ERRORS"):
            styled_dataframe(pd.DataFrame(port_report.errors), height=180)
    if port_report.warnings:
        for w in port_report.warnings:
            st.warning(w)
    if not port_report.positions:
        st.error("NO POSITIONS LOADED — CHECK FILE LAYOUT")
        return

    # ===== VALUE PORTFOLIO =====
    cfg = ValuationConfig(
        valuation_date=valuation_date, curves=curves,
        default_spread_bps=default_spread_bps,
        fallback_ytm=fallback_ytm_pct / 100.0,
        method=method_map[valuation_method],
    )
    results = value_portfolio(port_report.positions, cfg)

    # ===== TOP-LINE METRICS =====
    section("Portfolio Summary")
    pv_col = "curve_pv" if "curve_pv" in results.columns else "yield_pv"
    dv_col = "curve_dv01" if "curve_dv01" in results.columns else "yield_dv01"
    cards = [
        {"label": "Positions", "value": str(len(port_report.positions)), "tone": "cyan"},
        {"label": "Loaded", "value": f"{port_report.rows_loaded}/{port_report.rows_read}",
         "sub": "ROWS"},
    ]
    if pv_col in results.columns:
        for cur in sorted(results["currency"].dropna().unique()):
            sub = results[results["currency"] == cur]
            pv_total = sub[pv_col].sum() if pv_col in sub.columns else 0.0
            dv_total = sub[dv_col].sum() if dv_col in sub.columns else 0.0
            cards.append({
                "label": f"PV · {cur}", "value": fmt_currency(pv_total, cur, 0),
                "sub": f"{len(sub)} POS", "tone": "amber",
            })
            cards.append({
                "label": f"DV01 · {cur}", "value": fmt_currency(dv_total, cur, 0),
                "sub": "PER 1 BP", "tone": "green",
            })
    tile_grid(cards, columns_per_row=4)

    # ===== TABS =====
    tab_pos, tab_agg, tab_raw, tab_exp = st.tabs([
        "POSITIONS", "AGGREGATIONS", "RAW DATA · ISSUES", "EXPORTS",
    ])

    with tab_pos:
        section("Position Results")
        display_cols = [c for c in [
            "trade_id", "isin", "instrument_type", "description",
            "counterparty", "book", "currency", "notional", "maturity_date", "coupon_rate",
            "yield_clean_pct", "yield_dirty_pct", "yield_pv", "yield_dv01", "yield_mod_dur",
            "curve_used", "curve_clean_pct", "curve_dirty_pct", "curve_pv", "curve_dv01", "curve_mod_dur",
            "yield_error", "curve_error", "error",
        ] if c in results.columns]
        styled_dataframe(
            results[display_cols].style.format({
                "notional": "{:,.0f}", "coupon_rate": "{:.4%}",
                "yield_clean_pct": "{:.4f}", "yield_dirty_pct": "{:.4f}",
                "yield_pv": "{:,.0f}", "yield_dv01": "{:,.2f}", "yield_mod_dur": "{:.4f}",
                "curve_clean_pct": "{:.4f}", "curve_dirty_pct": "{:.4f}",
                "curve_pv": "{:,.0f}", "curve_dv01": "{:,.2f}", "curve_mod_dur": "{:.4f}",
            }, na_rep="—"),
            height=480,
        )

    with tab_agg:
        agg_views = aggregate(results)
        if not agg_views:
            st.info("AGGREGATIONS REQUIRE AT LEAST ONE SUCCESSFUL VALUATION")
        else:
            for name, df_agg in agg_views.items():
                section(name.replace("_", " "))
                fmt = {c: "{:,.2f}" for c in df_agg.columns
                       if c not in ("currency", "book", "counterparty", "instrument_type")}
                styled_dataframe(df_agg.style.format(fmt), height=240)

    with tab_raw:
        section("Portfolio Raw Data")
        raw_df = pd.DataFrame([p.raw_row for p in port_report.positions])
        styled_dataframe(raw_df, height=380)
        if port_report.errors:
            section("Load Errors")
            styled_dataframe(pd.DataFrame(port_report.errors), height=180)

    with tab_exp:
        section("Downloads")
        sheets = [("Positions", results)]
        for name, df_agg in aggregate(results).items():
            sheets.append((name[:31], df_agg))
        excel_bytes = to_excel_bytes(sheets)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "▼ EXCEL · ALL SHEETS", data=excel_bytes,
                file_name=f"portfolio_valuation_{valuation_date.isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "▼ POSITIONS CSV", data=to_csv_bytes(results),
                file_name=f"positions_{valuation_date.isoformat()}.csv",
                mime="text/csv", use_container_width=True,
            )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
if workspace == "Single Bond":
    run_single_bond_mode()
else:
    run_portfolio_mode()
