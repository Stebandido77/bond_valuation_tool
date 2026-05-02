"""
ui.components
=============

Bloomberg Terminal-style components.

Design language:
    - Pure black background, amber (#ffa500) for highlights and active values
    - Monospace numerics, dense layouts, hard rules between sections
    - Color codes: amber=primary, cyan=secondary headers, green=positive,
      red=negative, dim white for labels
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
TERMINAL_CSS = """
<style>
    /* ===== Global ===== */
    .stApp {
        background-color: #000000;
        color: #c9d1d9;
    }
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 1rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
        max-width: 100% !important;
    }

    /* Hide default streamlit chrome we don't need */
    [data-testid="stHeader"] { display: none; }
    .stDeployButton { display: none; }
    footer { display: none; }
    #MainMenu { display: none; }

    /* ===== Typography ===== */
    body, .stApp {
        font-family: 'IBM Plex Mono', 'JetBrains Mono', 'Consolas', 'Monaco', monospace;
    }
    /* Apply monospace to text content, but NEVER to material icons or svgs */
    .stMarkdown, .stTextInput, .stNumberInput, .stDateInput, .stSelectbox,
    .stRadio, .stButton, .stDownloadButton, .stTabs, .stMetric,
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"],
    [data-testid="stMetricDelta"], [data-testid="stCaptionContainer"],
    .stDataFrame {
        font-family: 'IBM Plex Mono', 'JetBrains Mono', 'Consolas', 'Monaco', monospace;
    }
    /* Material icons MUST keep their original font (Streamlit uses them in
       expanders, file uploader buttons, sliders, etc.) */
    [class*="material-symbols"], [class*="material-icons"],
    .material-symbols-outlined, .material-symbols-rounded,
    span[data-testid="stIconMaterial"],
    [data-testid="stExpander"] svg, [data-testid="stExpander"] [class*="icon"] {
        font-family: 'Material Symbols Outlined', 'Material Symbols Rounded',
                     'Material Icons', sans-serif !important;
    }

    /* ===== Sidebar ===== */
    section[data-testid="stSidebar"] {
        background-color: #0a0a0a;
        border-right: 1px solid #2a2a2a;
        width: 220px !important;
        min-width: 220px !important;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0.5rem;
    }
    section[data-testid="stSidebar"] .stRadio > label,
    section[data-testid="stSidebar"] .stSelectbox > label,
    section[data-testid="stSidebar"] .stTextInput > label,
    section[data-testid="stSidebar"] .stNumberInput > label,
    section[data-testid="stSidebar"] .stDateInput > label {
        font-size: 9px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: #888;
    }

    /* ===== Header bar ===== */
    .term-header {
        background: #000;
        border-bottom: 2px solid #ffa500;
        padding: 6px 10px;
        margin: -8px -20px 12px -20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 11px;
    }
    .term-title {
        color: #ffa500;
        font-weight: 700;
        font-size: 14px;
        letter-spacing: 1.5px;
    }
    .term-status {
        color: #00ff7f;
        font-size: 10px;
        letter-spacing: 1px;
    }
    .term-status .blink {
        animation: blink 1.5s infinite;
    }
    @keyframes blink {
        50% { opacity: 0.3; }
    }

    /* ===== Section headers (cyan tags like Bloomberg) ===== */
    .term-section {
        background: linear-gradient(90deg, #1a1a00 0%, transparent 100%);
        border-left: 3px solid #ffa500;
        padding: 4px 10px;
        margin: 14px 0 8px 0;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #ffa500;
    }
    .term-subsection {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #00d4ff;
        margin: 10px 0 4px 0;
        border-bottom: 1px dotted #2a2a2a;
        padding-bottom: 4px;
    }

    /* ===== Metric tiles (terminal-style) ===== */
    .term-tile {
        background: #0a0a0a;
        border: 1px solid #1a1a1a;
        border-left: 2px solid #ffa500;
        padding: 8px 12px;
        font-family: 'IBM Plex Mono', monospace;
    }
    .term-tile.cyan { border-left-color: #00d4ff; }
    .term-tile.green { border-left-color: #00ff7f; }
    .term-tile.red { border-left-color: #ff4d4d; }
    .term-tile .lbl {
        font-size: 9px;
        color: #6a6a6a;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 700;
        margin-bottom: 2px;
    }
    .term-tile .val {
        font-size: 18px;
        font-weight: 700;
        color: #ffa500;
        font-variant-numeric: tabular-nums;
        line-height: 1.2;
    }
    .term-tile.cyan .val { color: #00d4ff; }
    .term-tile.green .val { color: #00ff7f; }
    .term-tile.red .val { color: #ff4d4d; }
    .term-tile .sub {
        font-size: 9px;
        color: #555;
        margin-top: 1px;
        letter-spacing: 0.5px;
    }

    /* ===== Inputs ===== */
    .stTextInput input, .stNumberInput input, .stDateInput input {
        background-color: #0a0a0a !important;
        color: #ffa500 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 0 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 12px !important;
        font-weight: 600;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #ffa500 !important;
        box-shadow: 0 0 0 1px #ffa500 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #0a0a0a !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 0 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 12px !important;
        color: #ffa500 !important;
    }
    label, .stMarkdown p {
        font-size: 10px !important;
        color: #888 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    /* Radio buttons */
    .stRadio > div { gap: 0; }
    .stRadio label p {
        font-size: 11px !important;
        color: #c9d1d9 !important;
        text-transform: none !important;
        letter-spacing: 0 !important;
    }

    /* ===== Buttons ===== */
    .stButton > button, .stDownloadButton > button {
        background-color: #1a1a00 !important;
        color: #ffa500 !important;
        border: 1px solid #ffa500 !important;
        border-radius: 0 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        padding: 6px 14px !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background-color: #ffa500 !important;
        color: #000 !important;
    }

    /* ===== Tabs ===== */
    .stTabs [data-baseweb="tab-list"] {
        background: transparent;
        border-bottom: 1px solid #2a2a2a;
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #888 !important;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 16px !important;
        font-size: 11px !important;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-family: 'IBM Plex Mono', monospace;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #ffa500 !important;
        border-bottom: 2px solid #ffa500 !important;
        background: rgba(255, 165, 0, 0.05);
    }

    /* ===== Tables ===== */
    .stDataFrame, [data-testid="stDataFrame"] {
        border: 1px solid #2a2a2a;
        background: #0a0a0a;
    }
    .stDataFrame table {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 11px !important;
    }

    /* ===== Alerts ===== */
    .stAlert {
        background-color: #1a1a00 !important;
        border-left: 3px solid #ffa500 !important;
        border-radius: 0 !important;
        color: #c9d1d9 !important;
        font-size: 11px !important;
    }

    /* Dividers */
    hr { border-color: #2a2a2a !important; margin: 8px 0 !important; }

    /* Captions */
    .stCaption, [data-testid="stCaptionContainer"] {
        font-size: 10px !important;
        color: #555 !important;
        letter-spacing: 1px;
    }

    /* File uploader — leave native styling (only adjust container border) */
    [data-testid="stFileUploader"] {
        margin-bottom: 0;
    }
</style>
"""


def inject_theme() -> None:
    st.markdown(TERMINAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header bar (Bloomberg-style top strip)
# ---------------------------------------------------------------------------
def header(title: str, subtitle: str, tag: str = "FRONT OFFICE") -> None:
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(
        f"""
        <div class="term-header">
            <div>
                <span class="term-title">▸ {title.upper()}</span>
                <span style="color:#555; margin-left:14px; font-size:10px; letter-spacing:1px;">
                    {subtitle.upper()}
                </span>
            </div>
            <div class="term-status">
                <span class="blink">●</span> LIVE &nbsp;|&nbsp; {now} &nbsp;|&nbsp; {tag}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def section(title: str) -> None:
    st.markdown(f'<div class="term-section">▸ {title}</div>', unsafe_allow_html=True)


def subsection(title: str) -> None:
    st.markdown(f'<div class="term-subsection">{title}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tiles (terminal-style metric cards)
# ---------------------------------------------------------------------------
def tile(label: str, value: str, sub: str = "", tone: str = "amber") -> str:
    tone_cls = "" if tone == "amber" else tone
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="term-tile {tone_cls}">'
        f'<div class="lbl">{label}</div>'
        f'<div class="val">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


def tile_grid(tiles: list[dict], columns_per_row: int = 4) -> None:
    """Render a grid of terminal tiles using HTML for tight control."""
    items = list(tiles)
    if not items:
        return
    for start in range(0, len(items), columns_per_row):
        chunk = items[start:start + columns_per_row]
        cols = st.columns(len(chunk), gap="small")
        for col, t in zip(cols, chunk):
            with col:
                st.markdown(
                    tile(
                        label=t["label"],
                        value=t["value"],
                        sub=t.get("sub", ""),
                        tone=t.get("tone", "amber"),
                    ),
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Dataframe viewer
# ---------------------------------------------------------------------------
def styled_dataframe(
    df,
    height: Optional[int] = None,
    use_container_width: bool = True,
) -> None:
    kwargs = {"use_container_width": use_container_width}
    if height is not None:
        kwargs["height"] = int(height)
    st.dataframe(df, **kwargs)
