# Bond Valuation Workbench

A professional-grade fixed-income valuation tool with two workflows:

1. **Single Bond** — interactive analysis of one instrument: yield-vs-curve
   comparison, cashflow schedule, parallel and bucket DV01.
2. **Portfolio** — bulk valuation of an entire book from a CSV/Excel file,
   with totals aggregated by currency, book, counterparty and instrument
   type.

The tool is opinionated about correctness: pricing formulas are not
simplified, day-count conventions are explicit, risk metrics are computed
both analytically (under YTM) and numerically (under curve), and the
comparative panel makes the gap between the two methods auditable
trade-by-trade.

It supports the following instruments out of the box:

| Type             | Class                | Notes                                              |
|------------------|----------------------|----------------------------------------------------|
| TES Tasa Fija    | `TESTasaFija`        | NL/365, annual, COP                                |
| TES UVR          | `TESUVR`             | UVR-indexed principal, NL/365, annual              |
| TES IPC          | `TESIPC`             | `(1+IPC)(1+real)-1` coupons, NL/365, annual        |
| Corporate fija   | `CorporateFixedRate` | 30/360 semi-annual default, COP                    |
| Corporate IPC    | `CorporateIPC`       | 30/360 semi-annual default, COP                    |
| Global           | `GlobalBond`         | USD/EUR, 30/360 semi-annual default                |
| Zero-coupon      | `ZeroCouponBond`     | Single cashflow at maturity                        |
| Generic bullet   | `Bond`               | Anything else, fully parameterized                 |

A bundled catalog of common TES references resolves issue date, maturity,
coupon and convention from an ISIN — so portfolio rows only need to carry
position size and the relevant fixings. Unknown references fall back to
the row's own contractual data.

---

## Features

### Quantitative

- Clean / dirty price, accrued interest, full cashflow generation
- DV01, Macaulay & Modified duration, Convexity
- YTM solver (Newton–Raphson with bisection fallback)
- Day-count conventions: ACT/360, ACT/365, ACT/ACT (ISDA), 30/360, 30E/360, NL/365
- Coupon frequencies: annual, semi-annual, quarterly, monthly
- Issuer / liquidity spreads on top of either yield or curve

### Market data

- CSV / Excel curve loader with schema validation and percent-vs-decimal auto-detection
- Three interpolation strategies:
  - linear in zero rate (default)
  - log-linear in discount factor (piecewise-constant forwards)
  - natural cubic spline
- Multiple curves per file, picked at runtime (`TES_COP_ZERO`, `IBR_OIS`, ...)

### Risk

- Parallel curve shocks: ±1, ±10, ±50, ±100 bp
- Bucket / key-rate DV01 (per pillar)
- Yield vs curve comparative table (price, DV01, duration, convexity)

### UI

- Front-Office-style Streamlit interface
- Upload curve files directly from the browser
- Live cashflow table, curve preview, scenario charts
- Excel export with all sheets (cashflows, both valuations, curve, comparative)

---

## Project layout

```
bond_valuation_tool/
├── core/
│   ├── pricing.py          # yield- and curve-based engines + YTM solver
│   ├── risk_metrics.py     # DV01, durations, convexity, bucket DV01, scenarios
│   ├── curves.py           # ZeroCurve container with parallel & bucket shocks
│   ├── day_count.py        # ACT/360, ACT/365, ACT/ACT, 30/360, 30E/360, NL/365
│   └── cashflows.py        # bullet schedule generator (maturity-anchored)
│
├── instruments/
│   ├── bond.py                 # generic fixed-rate bullet bond
│   ├── tes.py                  # TES Tasa Fija, TES UVR, TES IPC
│   ├── corporate.py            # Corporate fija, Corporate IPC, Global bond
│   ├── inflation_linked.py     # UVR-indexed and (1+IPC)(1+real) linkers
│   ├── zero_coupon.py          # Zero-coupon / discount bonds
│   ├── tes_catalog.py          # bundled TES reference catalog
│   └── factory.py              # builds an instrument from a portfolio row
│
├── portfolio/
│   ├── loader.py           # CSV/Excel portfolio loader, schema validation
│   └── valuator.py         # bulk valuation + aggregations
│
├── market_data/
│   ├── curve_loader.py     # CSV / Excel reader with schema validation
│   └── interpolation.py    # linear, log-linear DF, cubic spline
│
├── ui/
│   ├── app.py              # Streamlit entry point — Single Bond + Portfolio
│   └── components.py       # theme + reusable widgets
│
├── utils/helpers.py
├── tests/
│   ├── test_pricing.py     # pricing & risk invariants
│   └── test_portfolio.py   # catalog, instruments, factory, end-to-end portfolio
├── data/
│   ├── sample_curve.csv          # TES_COP_ZERO + IBR_OIS + USD_BENCHMARK
│   └── portfolio_template.csv    # one example of every supported instrument
├── requirements.txt
├── run.sh / run.bat
└── README.md
```

---

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/<your-user>/bond_valuation_tool.git
cd bond_valuation_tool
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Running the workbench

The fastest path:

```bash
./run.sh                           # Linux / macOS
run.bat                            # Windows
```

This creates a virtualenv if needed, installs dependencies, and launches
Streamlit on `http://localhost:8501`.

Manually:

```bash
streamlit run ui/app.py
```

In the UI:

1. Define the bond in the sidebar (TES tasa fija, TES UVR, or generic).
2. Pick a valuation method: yield, curve, or comparative.
3. Click **Load sample curve** for an instant demo, or upload your own
   CSV / Excel curve.
4. Inspect cashflows, curve preview, parallel shocks, bucket DV01, and the
   yield-vs-curve comparative.
5. Export everything to Excel.

---

## Portfolio mode

The portfolio workflow takes a CSV or Excel file with one row per position
and produces a tidy results frame plus aggregations by currency / book /
counterparty / instrument type. The bundled template
`data/portfolio_template.csv` documents the layout and contains one example
of every supported instrument type.

### Portfolio file columns

| Column            | Required | Notes                                                                  |
|-------------------|----------|------------------------------------------------------------------------|
| `instrument_type` | yes      | `TES_TASA_FIJA`, `TES_UVR`, `TES_IPC`, `CORP_FIJA`, `CORP_IPC`, `GLOBAL`, `ZERO`, `GENERIC` |
| `notional`        | yes      | Position size in instrument currency / units (UVR for TES UVR)         |
| `ref`             | optional | TES reference for catalog lookup (e.g. `TFIT16181030`).                |
| `isin`            | optional | Falls back to `ref` when missing.                                      |
| `issue_date`      | cond.    | Required when `ref` is missing or unknown.                             |
| `maturity_date`   | cond.    | Required when `ref` is missing or unknown.                             |
| `coupon_rate`     | cond.    | Decimal (`0.075`) or percent (`7.5`) — auto-detected.                  |
| `frequency`       | optional | Defaults: 1 for TES, 2 for corporate / global.                         |
| `day_count`       | optional | Defaults: NL/365 for TES, 30/360 for corporate / global.               |
| `currency`        | optional | Defaults: COP for local, UVR for TES UVR, USD for Global.              |
| `ytm`             | optional | YTM for yield-based valuation. Decimal or percent.                     |
| `curve_name`      | optional | Curve to use for that row. Falls back to default if absent.            |
| `spread_bps`      | optional | Issuer / liquidity spread on top of the chosen curve.                  |
| `flat_inflation`  | optional | Flat IPC projection (decimal or percent) for IPC linkers.              |
| `uvr_fixing`      | optional | UVR fixing for COP conversion (TES UVR).                               |
| `counterparty`    | optional | Reporting field, used in aggregations.                                 |
| `book`            | optional | Reporting field, used in aggregations.                                 |
| `trade_id`        | optional | Free-form identifier.                                                  |
| `notes`           | optional | Free-form annotation.                                                  |

### TES catalog

The catalog ships with a set of common TES references (tasa fija, UVR, IPC)
in `instruments/tes_catalog.py`. When a portfolio row supplies a known
`ref`, contractual fields (issue date, maturity, coupon, frequency, day
count) are read from the catalog. Unknown refs fall back to whatever the
row provides; if both are missing, the row is reported as a load error
without aborting the rest of the portfolio.

To extend the catalog, edit `_BUILTIN_CATALOG` in `instruments/tes_catalog.py`
or load extra entries at runtime via
`load_external_catalog("path/to/catalog.csv")`.

---

## Curve file format

CSV or Excel with the following columns (case-insensitive, extra columns
ignored):

| Column            | Required | Notes                                                          |
|-------------------|----------|----------------------------------------------------------------|
| `curve_name`      | yes      | Multiple curves per file are supported.                        |
| `valuation_date`  | yes      | ISO `YYYY-MM-DD` recommended; common formats are auto-parsed.  |
| `tenor`           | optional | Free-form label (`1Y`, `30D`, ...). Used in the bucket panel.  |
| `days`            | yes      | Days from valuation date to pillar.                            |
| `zero_rate`       | yes\*    | Decimal (0.085) or percent (8.5) — auto-detected.              |
| `discount_factor` | yes\*    | Used only if `zero_rate` is missing.                           |
| `currency`        | optional | ISO three-letter code.                                         |
| `index`           | optional | Free-form index tag.                                           |

\* one of `zero_rate` / `discount_factor` must be present.

A working sample is bundled in `data/sample_curve.csv`.

---

## Programmatic usage

```python
from datetime import date
from instruments.tes import TESTasaFija
from market_data.curve_loader import load_curves

bond = TESTasaFija(
    isin="COTES_2032_07",
    issue_date=date(2024, 7, 26),
    maturity_date=date(2032, 7, 26),
    coupon_rate=0.0700,
    notional=1_000_000_000.0,
)

# Yield-based valuation
yld_res = bond.price_yield(valuation_date=date(2025, 9, 1), ytm=0.10)
print(f"Clean price (yield)  : {yld_res.clean_price:.4f}%")

# Curve-based valuation
report = load_curves("data/sample_curve.csv")
curve = report.curves["TES_COP_ZERO"]
crv_res = bond.price_curve(date(2025, 9, 1), curve)
print(f"Clean price (curve)  : {crv_res.clean_price:.4f}%")

# Risk
risk = bond.risk_curve(date(2025, 9, 1), curve)
print(f"DV01: {risk.dv01:,.2f}   ModDur: {risk.modified_duration:.4f}")
```

---

## Financial assumptions

- **Schedule**: bullet bonds, principal repaid at maturity. Schedules are
  generated by rolling backwards from maturity, which is the standard
  sovereign-market convention (e.g. TES tasa fija anchors on the
  day/month of maturity).
- **Yield discounting**: `(1 + y/m)^(-m·τ)` with `τ` in ACT/365 from
  valuation date to payment date.
- **Curve discounting**: zero rates are stored as ANN by default —
  `DF = (1 + r)^(-t)` with `t` in years over a 365-day basis. The CC
  convention is also supported on `ZeroCurve`.
- **Accrued interest**: linear (straight-line) on the running coupon
  period.
- **DV01 under curve**: numerical, central-difference at ±1 bp.
- **Bucket DV01**: pillar-by-pillar reshock with a 1 bp bump. Pillars are
  the input curve's own tenor grid — no interpolation onto a separate
  bucketing scheme.

---

## Testing

```bash
pytest -q
```

The bundled tests cover the pricing invariants every fixed-income library
must respect: at-the-money pricing at par, yield ↔ flat-curve agreement,
solver round-trip, DV01 sign and magnitude, convexity positivity, and the
duration of a zero-coupon bond.

---

## Roadmap

- Floating-rate notes anchored on IBR
- TES UVR full COP conversion pipeline (UVR fixings table)
- Non-parallel scenario engine (steepener / flattener / butterfly)
- Excel export with formatted templates (number formats, conditional
  highlighting)
- REST API around `core/*`

---

## License

MIT.
