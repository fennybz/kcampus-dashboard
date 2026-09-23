import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os, base64
from datetime import datetime
from db import (init_db, get_all_sales, get_upload_history, insert_upload,
                deactivate_upload, check_duplicate, parse_campus_excel, seed_from_xlsm)

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Kalachandji's Campus Sales", page_icon=":curry:",
                   layout="wide", initial_sidebar_state="collapsed")

# ── Dark Mode Toggle ─────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

dark = st.session_state.dark_mode

if "palette" not in st.session_state:
    st.session_state.palette = "Classic"

PALETTES = {
    "Classic":  ["#e94560", "#0f3460", "#533483", "#f39c12", "#2ecc71", "#3498db", "#e67e22", "#9b59b6", "#1abc9c", "#e74c3c"],
    "Ocean":    ["#0077b6", "#00b4d8", "#90e0ef", "#023e8a", "#48cae4", "#0096c7", "#ade8f4", "#03045e", "#caf0f8", "#0077b6"],
    "Sunset":   ["#ff6b6b", "#feca57", "#ff9ff3", "#54a0ff", "#5f27cd", "#01a3a4", "#f368e0", "#ff9f43", "#ee5a24", "#6ab04c"],
    "Forest":   ["#2d6a4f", "#40916c", "#52b788", "#74c69d", "#95d5b2", "#1b4332", "#b7e4c7", "#d8f3dc", "#081c15", "#344e41"],
    "Berry":    ["#7b2cbf", "#9d4edd", "#c77dff", "#e0aaff", "#5a189a", "#3c096c", "#240046", "#10002b", "#ff6d00", "#ff9e00"],
    "Warm":     ["#d62828", "#f77f00", "#fcbf49", "#eae2b7", "#003049", "#bc4749", "#a7c957", "#6a994e", "#386641", "#dda15e"],
}
PAL = PALETTES[st.session_state.palette]

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Layout */
    .block-container { padding-top: 0.5rem; padding-bottom: 0rem; max-width: 100%; }
    header[data-testid="stHeader"] { display: none; }
    #MainMenu, footer { visibility: hidden; }

    /* Warm themed background */
    .stApp, [data-testid="stAppViewContainer"] {
        background: linear-gradient(160deg, #fdf6f0 0%, #f0e9f5 30%, #e8f0fe 60%, #fdf6f0 100%) !important;
    }
    .main [data-testid="stVerticalBlockBorderWrapper"] {
        background: transparent !important;
    }

    /* Header bar */
    .hero {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 40%, #0f3460 100%);
        padding: 1.2rem 2.5rem; border-radius: 0 0 1.2rem 1.2rem;
        margin: -0.5rem -1rem 0.8rem -1rem;
        display: flex; align-items: center; gap: 1.5rem;
    }
    .hero h1 { color: #ffffff; font-size: 1.8rem; margin: 0; font-weight: 800;
               background: linear-gradient(90deg, #ff6b6b, #e94560, #ff8a80);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .hero .subtitle { color: #a8b2d1; font-size: 0.9rem; margin: 0.2rem 0 0 0; }
    .hero .date-badge { margin-left: auto; background: rgba(233,69,96,0.15);
        color: #ff6b6b; padding: 0.4rem 1rem; border-radius: 2rem;
        font-size: 0.8rem; font-weight: 600; white-space: nowrap; }

    /* KPI row */
    .kpi-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.8rem;
               margin: 0 0 0.6rem 0; }
    .kpi-card { background: rgba(255,255,255,0.85); backdrop-filter: blur(10px);
        border: 1px solid rgba(238,240,246,0.8); border-radius: 1rem;
        padding: 1rem 1.2rem; position: relative; overflow: hidden;
        transition: all 0.25s ease; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
    .kpi-card:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
    .kpi-card .accent { position: absolute; top: 0; left: 0; right: 0; height: 4px; }
    .kpi-label { font-size: 0.7rem; color: #8892b0; text-transform: uppercase;
        letter-spacing: 1.5px; font-weight: 700; margin-bottom: 0.25rem; }
    .kpi-value { font-size: 1.7rem; font-weight: 800; color: #1a1a2e; line-height: 1.1; }
    .kpi-sub { font-size: 0.72rem; color: #a0a8c0; margin-top: 0.2rem; }

    /* Filter bar */
    .filter-strip { background: rgba(248,249,255,0.8); backdrop-filter: blur(10px);
        border: 1px solid rgba(238,240,246,0.6); border-radius: 0.8rem;
        padding: 0.6rem 1.2rem 0.2rem 1.2rem; margin-bottom: 0.6rem; }
    .filter-label { font-size: 0.7rem; color: #8892b0; text-transform: uppercase;
        letter-spacing: 1.2px; font-weight: 700; margin-bottom: 0.15rem; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 0.3rem; background: rgba(248,249,255,0.7);
        backdrop-filter: blur(10px); padding: 0.35rem 0.5rem; border-radius: 0.8rem;
        border: 1px solid rgba(232,236,244,0.6); }
    .stTabs [data-baseweb="tab"] { border-radius: 0.6rem; padding: 0.5rem 1.5rem;
        font-weight: 600; font-size: 0.85rem; }
    .stTabs [aria-selected="true"] { background: linear-gradient(135deg, #e94560, #ff6b6b) !important;
        color: white !important; box-shadow: 0 4px 12px rgba(233,69,96,0.3); }

    /* Section titles */
    .sec-title { font-size: 1.05rem; font-weight: 700; color: #1a1a2e; margin: 0.8rem 0 0.4rem 0;
        padding-bottom: 0.25rem; border-bottom: 3px solid #e94560; display: inline-block; }

    /* Menu Decisions cards */
    .rec-keep { background: linear-gradient(135deg,#d4edda,#c3e6cb); border-left: 4px solid #28a745;
        padding: 0.6rem 1rem; border-radius: 0 0.6rem 0.6rem 0; margin: 0.35rem 0;
        transition: transform 0.15s; }
    .rec-keep:hover { transform: translateX(4px); }
    .rec-watch { background: linear-gradient(135deg,#fff3cd,#ffeeba); border-left: 4px solid #ffc107;
        padding: 0.6rem 1rem; border-radius: 0 0.6rem 0.6rem 0; margin: 0.35rem 0;
        transition: transform 0.15s; }
    .rec-watch:hover { transform: translateX(4px); }
    .rec-drop { background: linear-gradient(135deg,#f8d7da,#f5c6cb); border-left: 4px solid #dc3545;
        padding: 0.6rem 1rem; border-radius: 0 0.6rem 0.6rem 0; margin: 0.35rem 0;
        transition: transform 0.15s; }
    .rec-drop:hover { transform: translateX(4px); }

    /* Data Management */
    .upload-zone { background: linear-gradient(135deg, #f0f4ff, #e8ecff); border: 2px dashed #b8c4e8;
        border-radius: 1rem; padding: 1.5rem; text-align: center; margin-bottom: 1rem; }
    .upload-preview { background: #fff; border: 1px solid #c3e6cb; border-radius: 1rem;
        padding: 1.2rem; margin: 0.5rem 0; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
    .upload-preview .header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.8rem; }
    .upload-preview .header .icon { font-size: 1.5rem; }
    .upload-preview .stat-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 0.5rem; }
    .upload-preview .stat { background: #f8f9ff; border-radius: 0.5rem; padding: 0.6rem;
        text-align: center; }
    .upload-preview .stat .num { font-size: 1.1rem; font-weight: 700; color: #1a1a2e; }
    .upload-preview .stat .lbl { font-size: 0.65rem; color: #888; text-transform: uppercase;
        letter-spacing: 1px; }
    .upload-warn { background: linear-gradient(135deg,#fff3cd,#ffeeba); border: 1px solid #ffc107;
        border-radius: 0.75rem; padding: 1rem; margin: 0.5rem 0; }

    .batch-card { background: #fff; border: 1px solid #eef0f6; border-radius: 0.8rem;
        padding: 1rem 1.2rem; margin: 0.4rem 0; box-shadow: 0 1px 4px rgba(0,0,0,0.03);
        transition: all 0.2s; position: relative; overflow: hidden; }
    .batch-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
    .batch-card.active { border-left: 4px solid #28a745; }
    .batch-card.inactive { border-left: 4px solid #dc3545; opacity: 0.55; }
    .batch-card .badge { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 2rem;
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.5px; }
    .badge-active { background: #d4edda; color: #155724; }
    .badge-removed { background: #f8d7da; color: #721c24; }
    .batch-card .meta { font-size: 0.78rem; color: #666; margin-top: 0.3rem; line-height: 1.5; }
    .batch-card .title { font-weight: 700; font-size: 0.95rem; color: #1a1a2e; }

    .data-summary-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 0.8rem;
        margin: 0.8rem 0; }
    .data-summary-card { background: linear-gradient(135deg,#1a1a2e,#16213e); border-radius: 1rem;
        padding: 1.2rem; text-align: center; }
    .data-summary-card .val { font-size: 1.4rem; font-weight: 800; color: #ff6b6b; }
    .data-summary-card .lbl { font-size: 0.7rem; color: #a8b2d1; text-transform: uppercase;
        letter-spacing: 1px; margin-top: 0.2rem; }

    /* Logo styling */
    .hero img { height: 80px; border-radius: 12px; border: 2px solid rgba(233,69,96,0.4); }

    /* ── Mobile responsive ─────────────────────────────────── */
    @media (max-width: 768px) {
        .hero { flex-wrap: wrap; padding: 1rem; gap: 0.8rem; justify-content: center; text-align: center; }
        .hero img { height: 50px; }
        .hero h1 { font-size: 1.3rem; }
        .hero .subtitle { font-size: 0.75rem; }
        .hero .date-badge { margin-left: 0; margin-top: 0.3rem; }
        .kpi-row { grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }
        .kpi-value { font-size: 1.3rem; }
        .kpi-label { font-size: 0.6rem; }
        .filter-strip { padding: 0.4rem 0.6rem 0.1rem 0.6rem; }
        .stTabs [data-baseweb="tab-list"] { flex-wrap: wrap; gap: 0.2rem; }
        .stTabs [data-baseweb="tab"] { padding: 0.35rem 0.8rem; font-size: 0.72rem; }
        .upload-preview .stat-grid { grid-template-columns: repeat(2,1fr); }
        .data-summary-grid { grid-template-columns: repeat(2,1fr); }
        .rec-keep, .rec-watch, .rec-drop { font-size: 0.85rem; padding: 0.5rem 0.8rem; }
    }
    @media (max-width: 480px) {
        .hero { padding: 0.8rem 0.6rem; gap: 0.5rem; }
        .hero h1 { font-size: 1.1rem; }
        .hero .subtitle { font-size: 0.68rem; }
        .kpi-row { grid-template-columns: repeat(2, 1fr); gap: 0.4rem; }
        .kpi-card { padding: 0.7rem 0.8rem; }
        .kpi-value { font-size: 1.1rem; }
        .stTabs [data-baseweb="tab"] { padding: 0.3rem 0.5rem; font-size: 0.65rem; }
    }
</style>
""", unsafe_allow_html=True)

# ── Dark mode overrides ──────────────────────────────────────────────────────
if dark:
    st.markdown("""
    <style>
        /* Base dark background */
        .stApp, .main, [data-testid="stAppViewContainer"],
        [data-testid="stAppViewBlockContainer"], .block-container,
        section[data-testid="stSidebar"] { background-color: #0d1117 !important; }

        /* Global text */
        .stApp, .stMarkdown, p, span, label, div, li,
        h1, h2, h3, h4, h5, h6 { color: #e6edf3 !important; }
        .stMarkdown a { color: #58a6ff !important; }

        /* KPI cards */
        .kpi-card { background: #161b22 !important; border-color: #30363d !important;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important; }
        .kpi-label { color: #8b949e !important; }
        .kpi-sub { color: #8b949e !important; }

        /* Filter bar */
        .filter-strip { background: #161b22 !important; border-color: #30363d !important; }
        .filter-label { color: #8b949e !important; }

        /* Streamlit inputs */
        .stSelectbox > div > div, .stMultiSelect > div > div,
        [data-baseweb="select"] > div, [data-baseweb="input"] > div,
        .stDateInput > div > div > div { background-color: #21262d !important;
            color: #e6edf3 !important; border-color: #30363d !important; }
        [data-baseweb="tag"] { background-color: #30363d !important; color: #e6edf3 !important; }
        [data-baseweb="popover"] > div, [data-baseweb="menu"],
        [data-baseweb="calendar"] { background-color: #161b22 !important; color: #e6edf3 !important; }
        [data-baseweb="menu"] li { color: #e6edf3 !important; }
        [data-baseweb="menu"] li:hover { background-color: #30363d !important; }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] { background: #161b22 !important; border-color: #30363d !important; }
        .stTabs [data-baseweb="tab"] { color: #8b949e !important; }
        .stTabs [aria-selected="true"] { color: white !important; }

        /* Section titles */
        .sec-title { color: #e6edf3 !important; border-color: #e94560 !important; }

        /* Batch cards */
        .batch-card { background: #161b22 !important; border-color: #30363d !important; }
        .batch-card .title { color: #e6edf3 !important; }
        .batch-card .meta { color: #8b949e !important; }
        .batch-card .meta b { color: #e6edf3 !important; }

        /* Upload preview */
        .upload-preview { background: #161b22 !important; border-color: #30363d !important; }
        .upload-preview .stat { background: #0d1117 !important; }
        .upload-preview .stat .num { color: #e6edf3 !important; }
        .upload-preview .stat .lbl { color: #8b949e !important; }
        .upload-warn { background: #3a2f1a !important; border-color: #6e5a1f !important; }
        .upload-warn b { color: #ffc107 !important; }

        /* Recommendation cards */
        .rec-keep { background: linear-gradient(135deg,#122d1b,#1a3a2a) !important; border-color: #28a745 !important; }
        .rec-keep b { color: #7ee89a !important; }
        .rec-keep br ~ * { color: #8b949e; }
        .rec-watch { background: linear-gradient(135deg,#2d2613,#3a2f1a) !important; border-color: #b8860b !important; }
        .rec-watch b { color: #ffd866 !important; }
        .rec-drop { background: linear-gradient(135deg,#2d1318,#3a1a1e) !important; border-color: #dc3545 !important; }
        .rec-drop b { color: #ff8a8a !important; }
        .rec-keep, .rec-watch, .rec-drop { color: #b0b8c8 !important; }

        /* Data summary cards — already dark, just fine-tune */
        .data-summary-card { border: 1px solid #30363d; }

        /* DataFrame / table */
        [data-testid="stDataFrame"], [data-testid="stDataFrame"] * { background: #161b22 !important; color: #e6edf3 !important; }

        /* Buttons */
        .stButton > button { color: #e6edf3 !important; }
        .stDownloadButton > button { color: #e6edf3 !important; border-color: #30363d !important; background: #21262d !important; }

        /* Metrics */
        [data-testid="stMetricValue"] { color: #e6edf3 !important; }
        [data-testid="stMetricLabel"] { color: #8b949e !important; }

        /* File uploader */
        [data-testid="stFileUploader"] label,
        [data-testid="stFileUploader"] section { background: #161b22 !important;
            border-color: #30363d !important; color: #8b949e !important; }
        [data-testid="stFileUploader"] section > div { color: #8b949e !important; }

        /* Captions, info, warnings */
        .stCaption, [data-testid="stCaptionContainer"] { color: #8b949e !important; }
        [data-testid="stNotification"] { background: #161b22 !important; border-color: #30363d !important; }

        /* Selectbox / dropdown — all layers */
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] div[class],
        .stSelectbox div[data-baseweb="select"],
        .stSelectbox [data-baseweb="select"] > div { background-color: #21262d !important; border-color: #30363d !important; color: #e6edf3 !important; }
        .stSelectbox div[data-baseweb="select"] span,
        .stSelectbox div[data-baseweb="select"] div,
        div[data-baseweb="select"] svg { color: #e6edf3 !important; fill: #e6edf3 !important; }
        /* Popover / dropdown list — root level overrides */
        [data-baseweb="popover"], [data-baseweb="popover"] > div,
        [data-baseweb="menu"], [role="listbox"],
        [data-baseweb="popover"] ul, [data-baseweb="list"],
        [data-baseweb="popover"] div { background-color: #161b22 !important; background: #161b22 !important; color: #e6edf3 !important; }
        [role="listbox"] li, [data-baseweb="menu"] li, [role="option"],
        [role="listbox"] li *, [role="option"] * { color: #e6edf3 !important; background-color: transparent !important; }
        [role="listbox"] li:hover, [role="option"]:hover,
        [role="listbox"] [aria-selected="true"], [role="option"][aria-selected="true"] { background-color: #30363d !important; }
        /* Force the popover body element that Streamlit renders at document root */
        body > div[data-baseweb="popover"],
        body > div > div[data-baseweb="popover"],
        div[data-floating-ui-portal] *, [data-baseweb="layer"] * { background-color: #161b22 !important; color: #e6edf3 !important; }
        div[data-floating-ui-portal] li:hover, [data-baseweb="layer"] li:hover { background-color: #30363d !important; }
        /* Multi-select tags */
        span[data-baseweb="tag"] { background-color: #30363d !important; color: #e6edf3 !important; }
        span[data-baseweb="tag"] span { color: #e6edf3 !important; }
        /* Text inputs */
        div[data-baseweb="input"], div[data-baseweb="input"] input,
        .stDateInput input { color: #e6edf3 !important; background-color: #21262d !important; border-color: #30363d !important; }
        /* Calendar */
        div[data-baseweb="calendar"] { background-color: #161b22 !important; color: #e6edf3 !important; }
        div[data-baseweb="calendar"] * { color: #e6edf3 !important; }

        /* Plotly chart text — force via JS class overrides */
        .js-plotly-plot .plotly .gtitle { fill: #e6edf3 !important; }
        .js-plotly-plot .plotly .xtitle, .js-plotly-plot .plotly .ytitle { fill: #e6edf3 !important; }
        .js-plotly-plot .plotly .xtick text, .js-plotly-plot .plotly .ytick text { fill: #e6edf3 !important; }
        .js-plotly-plot .plotly .legendtext { fill: #e6edf3 !important; }
    </style>
    """, unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────────────────────
LOCATION_COLORS = {
    "Kalachandji's": PAL[0], "Market at JSOM": PAL[1], "Market ECSW": PAL[2],
    "Market at SCI": PAL[3], "Market at Student Union": PAL[4],
    "Market at Student Union - Wall Mall": PAL[6], "Comet Pi": PAL[5]
}
ACCENT, ACCENT2, ACCENT3 = PAL[0], PAL[1], PAL[4]
if dark:
    BG, GRID = "rgba(0,0,0,0)", "#30363d"
    TEXT_COLOR, HOVER_BG = "#c9d1d9", "#161b22"
else:
    BG, GRID = "rgba(0,0,0,0)", "#eef0f6"
    TEXT_COLOR, HOVER_BG = "#1a1a2e", "white"
CL = dict(paper_bgcolor=BG, plot_bgcolor=BG,
          font=dict(family="Inter, Segoe UI, sans-serif", color=TEXT_COLOR, size=12),
          title_font_color=TEXT_COLOR,
          margin=dict(l=40, r=20, t=50, b=40),
          hoverlabel=dict(bgcolor=HOVER_BG, font_size=13, bordercolor="#e8ecf4" if not dark else "#30363d"),
          legend_font_color=TEXT_COLOR,
          xaxis=dict(tickfont=dict(color=TEXT_COLOR), title_font_color=TEXT_COLOR),
          yaxis=dict(tickfont=dict(color=TEXT_COLOR), title_font_color=TEXT_COLOR))
KPI_COLORS = [PAL[0], PAL[1], PAL[4], PAL[3], PAL[7], PAL[9]]

# ── Init DB & Seed ───────────────────────────────────────────────────────────
init_db()
xlsm_path = os.path.join(os.path.dirname(__file__), "data", "Restaurant_Sales_Dashboard.xlsm")
if os.path.exists(xlsm_path):
    seed_from_xlsm(xlsm_path)

# ── HEADER with big logo ────────────────────────────────────────────────────
logo_path = os.path.join(os.path.dirname(__file__), "logo.avif")
logo_b64 = ""
if os.path.exists(logo_path):
    with open(logo_path, "rb") as lf:
        logo_b64 = base64.b64encode(lf.read()).decode()
logo_html = f'<img src="data:image/avif;base64,{logo_b64}">' if logo_b64 else ""

today_str = datetime.now().strftime("%B %d, %Y")
st.markdown(f"""
<div class="hero">
    {logo_html}
    <div style="flex:1;min-width:0;">
        <h1>Kalachandji's Campus Sales</h1>
        <p class="subtitle">University of Texas at Dallas &mdash; Real-time menu decisions, peak analysis &amp; outlet performance</p>
    </div>
    <div class="date-badge">{today_str}</div>
</div>
""", unsafe_allow_html=True)

# Theme toggle + palette selector
tc1, tc2, tc3 = st.columns([10, 1.5, 1])
with tc2:
    pal_choice = st.selectbox("Palette", list(PALETTES.keys()),
                              index=list(PALETTES.keys()).index(st.session_state.palette),
                              label_visibility="collapsed", key="pal_sel")
    if pal_choice != st.session_state.palette:
        st.session_state.palette = pal_choice
        st.rerun()
with tc3:
    toggle_label = "☀ Light" if dark else "🌙 Dark"
    if st.button(toggle_label, key="theme_toggle", type="tertiary"):
        st.session_state.dark_mode = not dark
        st.rerun()

# ── Load Data ────────────────────────────────────────────────────────────────
df_all = get_all_sales()
has_data = not df_all.empty

if has_data:
    df_all["sales_date"] = pd.to_datetime(df_all["sales_date"])
    for c in ["primary_units", "raw_quantity", "gross_sales", "discount", "net_sales",
              "unit_price", "modifier_selections"]:
        if c in df_all.columns:
            df_all[c] = pd.to_numeric(df_all[c], errors="coerce").fillna(0)
    primary = df_all[df_all["row_type"] == "Primary"].copy()

    # ── FILTER BAR ───────────────────────────────────────────────────────────
    st.markdown('<div class="filter-strip">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 2])
    with fc1:
        st.markdown('<div class="filter-label">Outlet</div>', unsafe_allow_html=True)
        outlets = sorted(primary["outlet"].dropna().unique())
        sel_outlets = st.multiselect("Outlet", outlets, default=[],
                                     placeholder="All Outlets", label_visibility="collapsed")
    with fc2:
        st.markdown('<div class="filter-label">Menu Category</div>', unsafe_allow_html=True)
        categories = sorted([c for c in primary["menu_category"].dropna().unique() if c.strip()])
        sel_cats = st.multiselect("Category", categories, default=[],
                                  placeholder="All Categories", label_visibility="collapsed")
    with fc3:
        st.markdown('<div class="filter-label">Date Range</div>', unsafe_allow_html=True)
        min_d = primary["sales_date"].min().date()
        max_d = primary["sales_date"].max().date()
        dr = st.date_input("Dates", value=(min_d, max_d), min_value=min_d,
                           max_value=max_d, label_visibility="collapsed")
        sd = dr[0] if len(dr) >= 1 else min_d
        ed = dr[1] if len(dr) >= 2 else max_d
    with fc4:
        st.markdown('<div class="filter-label">Product</div>', unsafe_allow_html=True)
        products = sorted(primary["product"].dropna().unique())
        sel_products = st.multiselect("Product", products, default=[],
                                      placeholder="All Products", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    # Apply filters
    mask = (primary["outlet"].isin(sel_outlets if sel_outlets else outlets)
            & primary["menu_category"].isin(sel_cats if sel_cats else categories)
            & primary["product"].isin(sel_products if sel_products else products)
            & (primary["sales_date"].dt.date >= sd) & (primary["sales_date"].dt.date <= ed))
    f = primary[mask].copy()

    if f.empty:
        st.warning("No data for current filters.")
        st.stop()

    # ── KPI CARDS ────────────────────────────────────────────────────────────
    net = f["net_sales"].sum()
    gross = f["gross_sales"].sum()
    units = f["primary_units"].sum()
    days = f["sales_date"].nunique()
    disc = f["discount"].sum()
    avg_unit = net / units if units else 0
    avg_daily = net / days if days else 0

    kpis = [
        ("Net Sales", f"${net:,.0f}", f"across {days} days &bull; Gross ${gross:,.0f}", KPI_COLORS[0]),
        ("Units Sold", f"{units:,.0f}", f"avg {units/days:,.0f}/day" if days else "", KPI_COLORS[1]),
        ("Avg $/Unit", f"${avg_unit:,.2f}", "revenue per item", KPI_COLORS[2]),
        ("Avg Daily Rev", f"${avg_daily:,.0f}", f"across {days} days", KPI_COLORS[3]),
        ("Discounts", f"${disc:,.2f}", f"{disc/gross*100:.1f}% of gross" if gross else "", KPI_COLORS[4]),
        ("Products", f"{f['product'].nunique()}", f"across {f['outlet'].nunique()} outlets", KPI_COLORS[5]),
    ]
    cards_html = '<div class="kpi-row">'
    for label, value, sub, color in kpis:
        cards_html += f'''<div class="kpi-card">
            <div class="accent" style="background:linear-gradient(90deg,{color},{color}88);"></div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{color};">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>'''
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["  Overview  ", "  Menu Decisions  ", "  Peak Times  ",
     "  Locations  ", "  Data Management  ", "  Raw Data  ", "  AI Insights  "])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: DATA MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    # Data summary at top
    history = get_upload_history()
    active_h = history[history["status"] == "ACTIVE"] if not history.empty else pd.DataFrame()

    if not active_h.empty:
        total_rows = int(active_h["row_count"].sum())
        total_net = f["net_sales"].sum() if has_data else 0.0
        total_batches = len(active_h)
        coverage = f'{active_h["date_min"].min()} to {active_h["date_max"].max()}'
    else:
        total_rows, total_net, total_batches, coverage = 0, 0.0, 0, "No data"

    st.markdown(f'''
    <div class="data-summary-grid">
        <div class="data-summary-card"><div class="val">{total_batches}</div><div class="lbl">Active Batches</div></div>
        <div class="data-summary-card"><div class="val">{total_rows:,}</div><div class="lbl">Total Rows</div></div>
        <div class="data-summary-card"><div class="val">${total_net:,.0f}</div><div class="lbl">Total Net Sales</div></div>
        <div class="data-summary-card"><div class="val">{coverage}</div><div class="lbl">Date Coverage</div></div>
    </div>
    ''', unsafe_allow_html=True)

    # Two-column layout: Upload on left, History on right
    upload_col, history_col = st.columns([1, 1], gap="large")

    with upload_col:
        st.markdown('<p class="sec-title">Upload Weekly Report</p>', unsafe_allow_html=True)
        st.markdown("Drop the weekly campus Excel file below. Data is validated and appended to your running history.")

        uploaded = st.file_uploader("Upload Excel", type=["xlsx", "xls"], key="uploader",
                                    label_visibility="collapsed")

        if uploaded:
            with st.spinner("Parsing..."):
                parsed = parse_campus_excel(uploaded, uploaded.name)

            if parsed.empty:
                st.error("Could not parse any data rows. Check file format.")
            else:
                date_min = parsed["sales_date"].min()
                date_max = parsed["sales_date"].max()
                net_total = parsed["net_sales"].sum()
                units_total = int(parsed.loc[parsed["row_type"] == "Primary", "primary_units"].sum())
                n_items = parsed["product"].nunique()
                n_outlets = parsed["outlet"].nunique()

                st.markdown(f'''
                <div class="upload-preview">
                    <div class="header">
                        <span class="icon">&#128202;</span>
                        <span style="font-weight:700;font-size:1rem;">{uploaded.name}</span>
                    </div>
                    <div class="stat-grid">
                        <div class="stat"><div class="num">{date_min}</div><div class="lbl">Start Date</div></div>
                        <div class="stat"><div class="num">{date_max}</div><div class="lbl">End Date</div></div>
                        <div class="stat"><div class="num">{len(parsed):,}</div><div class="lbl">Rows</div></div>
                        <div class="stat"><div class="num">{units_total:,}</div><div class="lbl">Units</div></div>
                        <div class="stat"><div class="num">${net_total:,.2f}</div><div class="lbl">Net Sales</div></div>
                        <div class="stat"><div class="num">{n_items}</div><div class="lbl">Products</div></div>
                        <div class="stat"><div class="num">{n_outlets}</div><div class="lbl">Outlets</div></div>
                        <div class="stat"><div class="num">${net_total/max(units_total,1):,.2f}</div><div class="lbl">Avg / Unit</div></div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)

                dup = check_duplicate(date_min, date_max, uploaded.name)
                if dup:
                    st.markdown(f'''
                    <div class="upload-warn">
                        <b>Duplicate detected:</b> {date_min} to {date_max} already uploaded on {dup[2]}
                        (Batch #{dup[0]}: {dup[1]}). Check the box below to force a second upload.
                    </div>
                    ''', unsafe_allow_html=True)
                    force = st.checkbox("Force upload (allow duplicate)")
                    can_upload = force
                else:
                    can_upload = True

                if can_upload:
                    if st.button("Confirm Upload", type="primary", use_container_width=True):
                        uid = insert_upload(uploaded.name, parsed)
                        st.success(f"Batch #{uid} uploaded — {len(parsed)} rows added.")
                        st.cache_data.clear()
                        st.rerun()

    with history_col:
        st.markdown('<p class="sec-title">Upload History</p>', unsafe_allow_html=True)

        if history.empty:
            st.info("No uploads yet. Use the panel on the left to upload your first weekly report.")
        else:
            # Filter controls for history
            hf1, hf2 = st.columns(2)
            with hf1:
                status_filter = st.selectbox("Status", ["All", "Active", "Removed"],
                                             label_visibility="collapsed")
            with hf2:
                sort_by = st.selectbox("Sort", ["Newest First", "Oldest First", "Highest Sales",
                                                "Most Rows"], label_visibility="collapsed")

            filtered_h = history.copy()
            if status_filter == "Active":
                filtered_h = filtered_h[filtered_h["status"] == "ACTIVE"]
            elif status_filter == "Removed":
                filtered_h = filtered_h[filtered_h["status"] == "INACTIVE"]

            if sort_by == "Newest First":
                filtered_h = filtered_h.sort_values("uploaded_at", ascending=False)
            elif sort_by == "Oldest First":
                filtered_h = filtered_h.sort_values("uploaded_at", ascending=True)
            elif sort_by == "Highest Sales":
                filtered_h = filtered_h.sort_values("net_sales", ascending=False)
            else:
                filtered_h = filtered_h.sort_values("row_count", ascending=False)

            for _, h in filtered_h.iterrows():
                is_active = h["status"] == "ACTIVE"
                card_cls = "active" if is_active else "inactive"
                badge_cls = "badge-active" if is_active else "badge-removed"
                badge_text = "ACTIVE" if is_active else "REMOVED"
                st.markdown(f'''
                <div class="batch-card {card_cls}">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span class="title">Batch #{h['id']} &mdash; {h['filename']}</span>
                        <span class="badge {badge_cls}">{badge_text}</span>
                    </div>
                    <div class="meta">
                        <b>{h['date_min']}</b> to <b>{h['date_max']}</b> &nbsp;&bull;&nbsp;
                        {h['row_count']:,} rows &nbsp;&bull;&nbsp;
                        {h['total_units']:,} units &nbsp;&bull;&nbsp;
                        <b>${h['net_sales']:,.2f}</b> net<br>
                        Uploaded {h['uploaded_at']}
                    </div>
                </div>
                ''', unsafe_allow_html=True)

            # Batch removal
            st.markdown("")
            active_batches = history[history["status"] == "ACTIVE"]
            if len(active_batches) > 1:
                st.markdown('<p class="sec-title">Remove a Batch</p>', unsafe_allow_html=True)
                batch_opts = [f"#{r['id']} — {r['filename']} ({r['date_min']} to {r['date_max']})"
                              for _, r in active_batches.iterrows()]
                sel_batch = st.selectbox("Select batch", batch_opts, label_visibility="collapsed")
                batch_id = int(sel_batch.split("#")[1].split(" ")[0])
                if st.button("Remove Batch", type="secondary"):
                    deactivate_upload(batch_id)
                    st.success(f"Batch #{batch_id} removed.")
                    st.cache_data.clear()
                    st.rerun()
            elif len(active_batches) == 1:
                st.caption("Only one active batch — cannot remove the last one.")

# ── Guard: stop if no data for chart tabs ────────────────────────────────────
if not has_data:
    with tab1:
        st.info("No data yet. Go to **Data Management** to upload your first weekly report.")
    st.stop()

if f.empty:
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    c1, c2 = st.columns([3, 2])
    with c1:
        daily = f.groupby("sales_date").agg(
            Revenue=("net_sales", "sum"), Units=("primary_units", "sum")).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["sales_date"], y=daily["Revenue"], mode="lines",
            line=dict(color=ACCENT, width=3, shape="spline"),
            fill="tozeroy", fillcolor="rgba(233,69,96,0.06)",
            hovertemplate="<b>%{x|%a %b %d}</b><br>$%{y:,.2f}<extra></extra>", name="Revenue"))
        if len(daily) > 3:
            daily["MA"] = daily["Revenue"].rolling(min(7, len(daily)), min_periods=1).mean()
            fig.add_trace(go.Scatter(
                x=daily["sales_date"], y=daily["MA"], mode="lines",
                line=dict(color=ACCENT2, width=2, dash="dot"),
                hovertemplate="Moving Avg: $%{y:,.2f}<extra></extra>", name="Moving Avg"))
        fig.update_layout(**CL, title="Daily Revenue Trend", height=380,
                          legend=dict(orientation="h", y=1.12))
        fig.update_xaxes(gridcolor=GRID)
        fig.update_yaxes(gridcolor=GRID)
        st.plotly_chart(fig, width="stretch")

    with c2:
        loc_rev = (f.groupby("outlet")["net_sales"].sum().reset_index()
                   .sort_values("net_sales", ascending=False))
        fig_d = go.Figure(go.Pie(
            labels=loc_rev["outlet"], values=loc_rev["net_sales"], hole=0.55,
            textposition="outside", textinfo="label+percent",
            marker=dict(colors=[LOCATION_COLORS.get(l, "#ccc") for l in loc_rev["outlet"]]),
            hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
            pull=[0.03] * len(loc_rev)))
        fig_d.update_layout(**CL, title="Revenue by Outlet", height=380, showlegend=False)
        fig_d.add_annotation(
            text=f"<b>${net:,.0f}</b><br><span style='font-size:11px;color:#888'>Net</span>",
            x=0.5, y=0.5, font_size=18, font_color=TEXT_COLOR, showarrow=False)
        st.plotly_chart(fig_d, width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        cat_data = (f.groupby("menu_category").agg(Revenue=("net_sales", "sum"))
                    .reset_index().sort_values("Revenue", ascending=False))
        fig_cat = go.Figure(go.Bar(
            x=cat_data["menu_category"], y=cat_data["Revenue"],
            marker=dict(color=cat_data["Revenue"],
                        colorscale=[[0, PAL[2]], [0.5, PAL[0]], [1, PAL[9]]]),
            text=[f"${v:,.0f}" for v in cat_data["Revenue"]],
            textposition="outside", textfont=dict(size=10),
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>"))
        fig_cat.update_layout(**CL, title="Revenue by Category", height=400)
        fig_cat.update_xaxes(tickangle=-30, gridcolor=GRID)
        fig_cat.update_yaxes(gridcolor=GRID)
        st.plotly_chart(fig_cat, width="stretch")

    with c4:
        top10 = (f.groupby("product")["net_sales"].sum().nlargest(10)
                 .reset_index().sort_values("net_sales"))
        fig_t = go.Figure(go.Bar(
            x=top10["net_sales"], y=top10["product"], orientation="h",
            marker=dict(color=top10["net_sales"],
                        colorscale=[[0, PAL[2]], [0.5, PAL[0]], [1, PAL[9]]]),
            text=[f"${v:,.0f}" for v in top10["net_sales"]],
            textposition="outside", textfont=dict(size=10, color=TEXT_COLOR),
            hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>"))
        fig_t.update_layout(**CL, title="Top 10 Products", height=400)
        fig_t.update_xaxes(visible=False)
        fig_t.update_yaxes(gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_t, width="stretch")

    # ── Product x Day Heatmap ────────────────────────────────────────────────
    st.markdown('<p class="sec-title">Product Sales Heatmap (Top 15 by Day)</p>',
                unsafe_allow_html=True)
    top_prods = f.groupby("product")["net_sales"].sum().nlargest(15).index.tolist()
    hm_data = f[f["product"].isin(top_prods)].groupby(
        ["product", "day_of_week"])["net_sales"].sum().reset_index()
    hm_piv = hm_data.pivot_table(index="product", columns="day_of_week",
                                  values="net_sales", fill_value=0)
    dow_order_hm = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hm_piv = hm_piv.reindex(columns=[d for d in dow_order_hm if d in hm_piv.columns])
    # Sort products by total revenue descending
    hm_piv = hm_piv.loc[hm_piv.sum(axis=1).sort_values(ascending=True).index]

    fig_phm = go.Figure(go.Heatmap(
        z=hm_piv.values, x=hm_piv.columns.tolist(), y=hm_piv.index.tolist(),
        colorscale=[[0, "#f8f9ff" if not dark else "#0d1117"],
                    [0.25, PAL[5]+"55"],
                    [0.5, PAL[0]],
                    [1, PAL[1]]],
        hovertemplate="<b>%{y}</b><br>%{x}: $%{z:,.2f}<extra></extra>",
        texttemplate="$%{z:,.0f}", textfont=dict(size=10)))
    fig_phm.update_layout(**CL, height=max(350, len(top_prods) * 28 + 80),
                           title="When does each product sell best?")
    st.plotly_chart(fig_phm, width="stretch")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: MENU DECISIONS
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<p class="sec-title">Menu Performance Matrix</p>', unsafe_allow_html=True)
    st.markdown("Identify which items to **keep**, **watch**, or consider **removing**.")

    ip = f.groupby("product").agg(
        Revenue=("net_sales", "sum"), Units=("primary_units", "sum"),
        Days_Sold=("sales_date", "nunique"), Avg_Price=("unit_price", "mean"),
        Discount=("discount", "sum")).reset_index()
    ip["Rev_Per_Day"] = ip["Revenue"] / ip["Days_Sold"]
    ip["Rev_Share"] = ip["Revenue"] / ip["Revenue"].sum() * 100
    rev_med, units_med = ip["Revenue"].median(), ip["Units"].median()

    def classify(r):
        if r["Revenue"] >= rev_med and r["Units"] >= units_med:
            return "KEEP - Star"
        elif r["Revenue"] >= rev_med or r["Units"] >= units_med:
            return "WATCH - Mixed"
        return "REVIEW - Remove?"
    ip["Rec"] = ip.apply(classify, axis=1)

    cmap = {"KEEP - Star": PAL[4], "WATCH - Mixed": PAL[3], "REVIEW - Remove?": PAL[9]}
    fig_mx = px.scatter(
        ip, x="Units", y="Revenue", color="Rec", size="Rev_Share", hover_name="product",
        color_discrete_map=cmap,
        hover_data={"Revenue": ":$,.2f", "Units": ":,.0f", "Days_Sold": True,
                    "Rev_Per_Day": ":$,.2f", "Avg_Price": ":$,.2f"},
        title="Menu Matrix (size = revenue share)")
    fig_mx.add_hline(y=rev_med, line_dash="dash", line_color="#888",
                     annotation_text=f"Rev median ${rev_med:,.0f}")
    fig_mx.add_vline(x=units_med, line_dash="dash", line_color="#888",
                     annotation_text=f"Units median {units_med:,.0f}")
    fig_mx.update_layout(**CL, height=500, legend=dict(orientation="h", y=-0.12))
    fig_mx.update_xaxes(gridcolor=GRID, title_text="Total Units")
    fig_mx.update_yaxes(gridcolor=GRID, title_text="Total Revenue ($)")
    st.plotly_chart(fig_mx, width="stretch")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Stars (Keep)")
        for _, r in ip[ip["Rec"].str.startswith("KEEP")].sort_values("Revenue", ascending=False).iterrows():
            st.markdown(f'<div class="rec-keep"><b>{r["product"]}</b><br>'
                        f'${r["Revenue"]:,.2f} &bull; {r["Units"]:,.0f} units &bull; '
                        f'{r["Rev_Share"]:.1f}%</div>', unsafe_allow_html=True)
    with c2:
        st.markdown("### Watch List")
        for _, r in ip[ip["Rec"].str.startswith("WATCH")].sort_values("Revenue", ascending=False).iterrows():
            st.markdown(f'<div class="rec-watch"><b>{r["product"]}</b><br>'
                        f'${r["Revenue"]:,.2f} &bull; {r["Units"]:,.0f} units &bull; '
                        f'${r["Rev_Per_Day"]:,.2f}/day</div>', unsafe_allow_html=True)
    with c3:
        st.markdown("### Review (Consider Removing)")
        for _, r in ip[ip["Rec"].str.startswith("REVIEW")].sort_values("Revenue").iterrows():
            st.markdown(f'<div class="rec-drop"><b>{r["product"]}</b><br>'
                        f'${r["Revenue"]:,.2f} &bull; {r["Units"]:,.0f} units &bull; '
                        f'sold {r["Days_Sold"]:.0f}/{days} days</div>', unsafe_allow_html=True)

    # Pareto
    st.markdown('<p class="sec-title">80/20 Rule — Which products drive 80% of revenue?</p>',
                unsafe_allow_html=True)
    par = ip.sort_values("Revenue", ascending=False).copy()
    par["Cum_Pct"] = par["Revenue"].cumsum() / par["Revenue"].sum() * 100
    fig_par = make_subplots(specs=[[{"secondary_y": True}]])
    fig_par.add_trace(go.Bar(
        x=par["product"], y=par["Revenue"], name="Revenue",
        marker=dict(color=ACCENT, opacity=0.7),
        hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>"), secondary_y=False)
    fig_par.add_trace(go.Scatter(
        x=par["product"], y=par["Cum_Pct"], name="Cumulative %", mode="lines+markers",
        line=dict(color=ACCENT2, width=3), marker=dict(size=6),
        hovertemplate="%{y:.1f}% cumulative<extra></extra>"), secondary_y=True)
    fig_par.add_hline(y=80, line_dash="dash", line_color="#e74c3c",
                      secondary_y=True, annotation_text="80%")
    fig_par.update_layout(**CL, title="Revenue Pareto", height=420,
                          legend=dict(orientation="h", y=1.12))
    fig_par.update_xaxes(tickangle=-45, gridcolor=GRID)
    fig_par.update_yaxes(title_text="Revenue ($)", secondary_y=False, gridcolor=GRID,
                         tickfont=dict(color=TEXT_COLOR), title_font_color=TEXT_COLOR)
    fig_par.update_yaxes(title_text="Cumulative %", secondary_y=True,
                         gridcolor="rgba(0,0,0,0)", range=[0, 105],
                         tickfont=dict(color=TEXT_COLOR), title_font_color=TEXT_COLOR)
    st.plotly_chart(fig_par, width="stretch")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: PEAK TIMES
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<p class="sec-title">When Are Sales Highest / Lowest?</p>',
                unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow = f.groupby("day_of_week").agg(
        Rev=("net_sales", "sum"), Units=("primary_units", "sum"),
        Days=("sales_date", "nunique")).reset_index()
    dow["Avg_Rev"] = dow["Rev"] / dow["Days"]
    dow["Avg_Units"] = dow["Units"] / dow["Days"]
    dow["day_of_week"] = pd.Categorical(dow["day_of_week"], categories=dow_order, ordered=True)
    dow = dow.sort_values("day_of_week").dropna(subset=["day_of_week"])
    best_day = dow.loc[dow["Avg_Rev"].idxmax(), "day_of_week"]
    worst_day = dow.loc[dow["Avg_Rev"].idxmin(), "day_of_week"]

    with c1:
        colors = [ACCENT3 if d == best_day else "#e74c3c" if d == worst_day else ACCENT2
                  for d in dow["day_of_week"]]
        fig_dow = go.Figure(go.Bar(
            x=dow["day_of_week"].astype(str), y=dow["Avg_Rev"],
            marker=dict(color=colors, opacity=0.85),
            text=[f"${v:,.0f}" for v in dow["Avg_Rev"]], textposition="outside",
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}/day<extra></extra>"))
        fig_dow.update_layout(**CL, height=400,
            title=f"Avg Revenue by Day (Best: {best_day}, Weakest: {worst_day})")
        fig_dow.update_xaxes(gridcolor=GRID)
        fig_dow.update_yaxes(gridcolor=GRID, title_text="Avg Revenue ($)")
        st.plotly_chart(fig_dow, width="stretch")
    with c2:
        fig_dow_u = go.Figure(go.Bar(
            x=dow["day_of_week"].astype(str), y=dow["Avg_Units"],
            marker=dict(color=ACCENT, opacity=0.85),
            text=[f"{v:,.0f}" for v in dow["Avg_Units"]], textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y:,.0f} units/day<extra></extra>"))
        fig_dow_u.update_layout(**CL, title="Avg Units by Day", height=400)
        fig_dow_u.update_xaxes(gridcolor=GRID)
        fig_dow_u.update_yaxes(gridcolor=GRID, title_text="Avg Units")
        st.plotly_chart(fig_dow_u, width="stretch")

    # Heatmap
    st.markdown('<p class="sec-title">Revenue Heatmap: Day x Outlet</p>',
                unsafe_allow_html=True)
    do = f.groupby(["day_of_week", "outlet"]).agg(
        Rev=("net_sales", "sum"), Days=("sales_date", "nunique")).reset_index()
    do["Avg"] = do["Rev"] / do["Days"]
    piv = do.pivot_table(index="outlet", columns="day_of_week", values="Avg", fill_value=0)
    piv = piv.reindex(columns=[d for d in dow_order if d in piv.columns])
    fig_hm = go.Figure(go.Heatmap(
        z=piv.values, x=piv.columns.tolist(), y=piv.index.tolist(),
        colorscale=[[0, "#f8f9ff" if not dark else "#0d1117"], [0.3, PAL[5]+"55"],
                    [0.6, PAL[0]], [1, PAL[1]]],
        hovertemplate="<b>%{y}</b><br>%{x}: $%{z:,.2f}/day<extra></extra>",
        texttemplate="$%{z:,.0f}", textfont=dict(size=11, color=TEXT_COLOR)))
    fig_hm.update_layout(**CL, title="Which outlets peak on which days?", height=350)
    st.plotly_chart(fig_hm, width="stretch")

    # Daily bars
    daily2 = (f.groupby("sales_date").agg(Rev=("net_sales", "sum"))
              .reset_index().sort_values("sales_date"))
    best = daily2.loc[daily2["Rev"].idxmax()]
    worst = daily2.loc[daily2["Rev"].idxmin()]
    fig_d2 = go.Figure(go.Bar(
        x=daily2["sales_date"], y=daily2["Rev"],
        marker=dict(color=[
            ACCENT3 if r["sales_date"] == best["sales_date"]
            else "#e74c3c" if r["sales_date"] == worst["sales_date"]
            else ACCENT2 for _, r in daily2.iterrows()], opacity=0.8),
        text=[f"${v:,.0f}" for v in daily2["Rev"]],
        textposition="outside", textfont=dict(size=10),
        hovertemplate="<b>%{x|%a %b %d}</b><br>$%{y:,.2f}<extra></extra>"))
    fig_d2.update_layout(**CL, height=400,
        title=(f"Daily Revenue — Best: {best['sales_date'].strftime('%a %b %d')} "
               f"(${best['Rev']:,.0f}) | Worst: {worst['sales_date'].strftime('%a %b %d')} "
               f"(${worst['Rev']:,.0f})"))
    fig_d2.update_xaxes(gridcolor=GRID)
    fig_d2.update_yaxes(gridcolor=GRID)
    st.plotly_chart(fig_d2, width="stretch")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: LOCATIONS
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    ls = (f.groupby("outlet").agg(
        Revenue=("net_sales", "sum"), Units=("primary_units", "sum"),
        Days=("sales_date", "nunique"), Items=("product", "nunique"))
        .reset_index().sort_values("Revenue", ascending=False))
    ls["Avg_Daily"] = ls["Revenue"] / ls["Days"]

    c1, c2 = st.columns(2)
    with c1:
        fig_lb = go.Figure(go.Bar(
            x=ls["outlet"], y=ls["Revenue"],
            marker=dict(color=[LOCATION_COLORS.get(l, "#ccc") for l in ls["outlet"]]),
            text=[f"${v:,.0f}" for v in ls["Revenue"]], textposition="outside",
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>"))
        fig_lb.update_layout(**CL, title="Total Revenue by Outlet", height=400)
        fig_lb.update_xaxes(tickangle=-30, gridcolor=GRID)
        fig_lb.update_yaxes(gridcolor=GRID)
        st.plotly_chart(fig_lb, width="stretch")
    with c2:
        fig_la = go.Figure(go.Bar(
            x=ls["outlet"], y=ls["Avg_Daily"],
            marker=dict(color=[LOCATION_COLORS.get(l, "#ccc") for l in ls["outlet"]],
                        opacity=0.8),
            text=[f"${v:,.0f}" for v in ls["Avg_Daily"]], textposition="outside",
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}/day<extra></extra>"))
        fig_la.update_layout(**CL, title="Avg Daily Revenue", height=400)
        fig_la.update_xaxes(tickangle=-30, gridcolor=GRID)
        fig_la.update_yaxes(gridcolor=GRID)
        st.plotly_chart(fig_la, width="stretch")

    st.markdown('<p class="sec-title">Outlet Drill-Down</p>', unsafe_allow_html=True)
    sel = st.selectbox("Select outlet", ls["outlet"].tolist(), label_visibility="collapsed")
    ld = f[f["outlet"] == sel]
    lc1, lc2 = st.columns(2)
    with lc1:
        li = (ld.groupby("product")["net_sales"].sum().nlargest(10)
              .reset_index().sort_values("net_sales"))
        fig_li = go.Figure(go.Bar(
            x=li["net_sales"], y=li["product"], orientation="h",
            marker=dict(color=LOCATION_COLORS.get(sel, ACCENT)),
            text=[f"${v:,.0f}" for v in li["net_sales"]],
            textposition="outside", textfont=dict(size=10),
            hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>"))
        fig_li.update_layout(**CL, title=f"Top Items at {sel}", height=380)
        fig_li.update_xaxes(visible=False)
        fig_li.update_yaxes(gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_li, width="stretch")
    with lc2:
        ldd = ld.groupby("sales_date")["net_sales"].sum().reset_index()
        fig_ld = go.Figure(go.Bar(
            x=ldd["sales_date"], y=ldd["net_sales"],
            marker=dict(color=LOCATION_COLORS.get(sel, ACCENT), opacity=0.7),
            hovertemplate="<b>%{x|%a %b %d}</b><br>$%{y:,.2f}<extra></extra>"))
        fig_ld.update_layout(**CL, title=f"Daily Sales at {sel}", height=380)
        fig_ld.update_xaxes(gridcolor=GRID)
        fig_ld.update_yaxes(gridcolor=GRID)
        st.plotly_chart(fig_ld, width="stretch")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6: RAW DATA
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown('<p class="sec-title">All Sales Data (Filtered)</p>', unsafe_allow_html=True)
    show_cols = ["sales_date", "outlet", "menu_category", "product", "primary_units",
                 "unit_price", "gross_sales", "discount", "net_sales", "filename", "uploaded_at"]
    display = f[[c for c in show_cols if c in f.columns]].copy()
    display["sales_date"] = display["sales_date"].dt.strftime("%Y-%m-%d")
    display.columns = [c.replace("_", " ").title() for c in display.columns]
    st.dataframe(display, width="stretch", height=500)
    st.download_button("Download as CSV", display.to_csv(index=False),
                       "kcampus_data.csv", "text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7: AI INSIGHTS (Chatbot)
# ══════════════════════════════════════════════════════════════════════════════
with tab7:
    st.markdown('<p class="sec-title">AI Sales Analyst</p>', unsafe_allow_html=True)
    st.markdown("Click any analysis below to get instant insights from your data — no API key needed.")

    # ── Built-in analysis functions ──────────────────────────────────────
    def _top_products(df, n=10):
        tp = df.groupby("product").agg(
            rev=("net_sales","sum"), units=("primary_units","sum"),
            days=("sales_date","nunique"), avg_price=("unit_price","mean")
        ).reset_index().sort_values("rev", ascending=False)
        total_rev = df["net_sales"].sum()
        lines = [f"### Top {min(n, len(tp))} Products by Revenue\n"]
        for i, r in tp.head(n).iterrows():
            pct = r["rev"]/total_rev*100 if total_rev else 0
            lines.append(f"**{r['product']}** — **${r['rev']:,.2f}** ({pct:.1f}% of total) · "
                         f"{r['units']:,.0f} units · avg ${r['avg_price']:,.2f}/unit · sold {r['days']} days")
        return "\n\n".join(lines)

    def _underperformers(df):
        tp = df.groupby("product").agg(
            rev=("net_sales","sum"), units=("primary_units","sum"),
            days=("sales_date","nunique")).reset_index().sort_values("rev")
        total_rev = df["net_sales"].sum()
        total_days = df["sales_date"].nunique()
        bottom = tp.head(10)
        lines = ["### Menu Items to Review\n",
                 "These items contribute the least revenue and may be candidates for removal or repricing:\n"]
        for _, r in bottom.iterrows():
            pct = r["rev"]/total_rev*100 if total_rev else 0
            freq = f"only {r['days']}/{total_days} days" if r["days"] < total_days else f"all {total_days} days"
            lines.append(f"- **{r['product']}** — ${r['rev']:,.2f} ({pct:.1f}%), {r['units']:,.0f} units, sold {freq}")
        lines.append(f"\n**Recommendation:** Items under **${total_rev*0.005:,.2f}** (0.5% of total) with "
                     f"infrequent sales are strong removal candidates — they add menu complexity without meaningful revenue.")
        return "\n".join(lines)

    def _day_of_week(df):
        dow = df.groupby("day_of_week").agg(
            rev=("net_sales","sum"), units=("primary_units","sum"),
            days=("sales_date","nunique")).reset_index()
        dow["avg_rev"] = dow["rev"] / dow["days"]
        dow["avg_units"] = dow["units"] / dow["days"]
        dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        dow["day_of_week"] = pd.Categorical(dow["day_of_week"], categories=dow_order, ordered=True)
        dow = dow.sort_values("day_of_week").dropna(subset=["day_of_week"])
        best = dow.loc[dow["avg_rev"].idxmax()]
        worst = dow.loc[dow["avg_rev"].idxmin()]
        lines = ["### Day-of-Week Analysis\n",
                 "| Day | Avg Revenue | Avg Units | Total Rev |",
                 "|-----|------------|-----------|-----------|"]
        for _, r in dow.iterrows():
            flag = " ⬆" if r["day_of_week"] == best["day_of_week"] else (" ⬇" if r["day_of_week"] == worst["day_of_week"] else "")
            lines.append(f"| {r['day_of_week']}{flag} | ${r['avg_rev']:,.2f} | {r['avg_units']:,.0f} | ${r['rev']:,.2f} |")
        spread = best["avg_rev"] - worst["avg_rev"]
        lines.append(f"\n**Peak day: {best['day_of_week']}** (${best['avg_rev']:,.2f}/day) — "
                     f"staff up and ensure popular items are stocked.")
        lines.append(f"\n**Slowest day: {worst['day_of_week']}** (${worst['avg_rev']:,.2f}/day) — "
                     f"consider promotions or reduced prep. Spread is **${spread:,.2f}** between peak and low.")
        return "\n".join(lines)

    def _outlet_comparison(df):
        out = df.groupby("outlet").agg(
            rev=("net_sales","sum"), units=("primary_units","sum"),
            days=("sales_date","nunique"), items=("product","nunique"),
            gross=("gross_sales","sum"), disc=("discount","sum")
        ).reset_index().sort_values("rev", ascending=False)
        total_rev = df["net_sales"].sum()
        lines = ["### Outlet Performance Comparison\n"]
        for _, r in out.iterrows():
            pct = r["rev"]/total_rev*100 if total_rev else 0
            avg_d = r["rev"]/r["days"] if r["days"] else 0
            disc_pct = abs(r["disc"])/r["gross"]*100 if r["gross"] else 0
            lines.append(f"**{r['outlet']}** — **${r['rev']:,.2f}** ({pct:.1f}%)\n"
                         f"- ${avg_d:,.2f}/day · {r['units']:,.0f} units · {r['items']} unique products · "
                         f"{disc_pct:.1f}% discount rate\n")
        top = out.iloc[0]
        if len(out) > 1:
            bot = out.iloc[-1]
            lines.append(f"**{top['outlet']}** leads with **{top['rev']/total_rev*100:.1f}%** of revenue. "
                         f"**{bot['outlet']}** is the smallest contributor at "
                         f"**${bot['rev']:,.2f}** — evaluate if it's covering costs.")
        return "\n".join(lines)

    def _category_breakdown(df):
        if "menu_category" not in df.columns or df["menu_category"].isna().all():
            return "No menu category data available in the current filter."
        cat = df.groupby("menu_category").agg(
            rev=("net_sales","sum"), units=("primary_units","sum"),
            items=("product","nunique"), avg_price=("unit_price","mean")
        ).reset_index().sort_values("rev", ascending=False)
        total = df["net_sales"].sum()
        lines = ["### Revenue by Menu Category\n",
                 "| Category | Revenue | % | Units | Products | Avg Price |",
                 "|----------|---------|---|-------|----------|-----------|"]
        for _, r in cat.iterrows():
            if not r["menu_category"]:
                continue
            pct = r["rev"]/total*100 if total else 0
            lines.append(f"| {r['menu_category']} | ${r['rev']:,.2f} | {pct:.1f}% | "
                         f"{r['units']:,.0f} | {r['items']} | ${r['avg_price']:,.2f} |")
        top_cat = cat.iloc[0]
        lines.append(f"\n**{top_cat['menu_category']}** dominates with **${top_cat['rev']:,.2f}** — "
                     f"focus marketing and daily specials around this category.")
        return "\n".join(lines)

    def _weekly_strategy(df):
        total_rev = df["net_sales"].sum()
        total_days = df["sales_date"].nunique()
        avg_daily = total_rev / total_days if total_days else 0
        # Day analysis
        dow = df.groupby("day_of_week").agg(rev=("net_sales","sum"), days=("sales_date","nunique")).reset_index()
        dow["avg"] = dow["rev"]/dow["days"]
        best_day = dow.loc[dow["avg"].idxmax(), "day_of_week"]
        worst_day = dow.loc[dow["avg"].idxmin(), "day_of_week"]
        # Top/bottom products
        tp = df.groupby("product")["net_sales"].sum().sort_values(ascending=False)
        top3 = list(tp.head(3).index)
        bot3 = list(tp.tail(3).index)
        # Top outlet
        out = df.groupby("outlet")["net_sales"].sum().sort_values(ascending=False)
        top_outlet = out.index[0] if len(out) else "N/A"
        lines = [
            "### Weekly Strategy Recommendation\n",
            f"**Overview:** ${total_rev:,.2f} across {total_days} days = **${avg_daily:,.2f}/day** average.\n",
            "#### Staffing",
            f"- **Peak day ({best_day}):** Schedule full staff, prep extra inventory for top sellers",
            f"- **Slow day ({worst_day}):** Reduce staff if possible, run promotions to drive traffic\n",
            "#### Menu",
            f"- **Protect top sellers:** {', '.join(top3)} — ensure consistent availability",
            f"- **Review bottom items:** {', '.join(bot3)} — consider removal or repricing",
            f"- Run daily specials on slow days featuring high-margin items\n",
            "#### Operations",
            f"- **Focus on {top_outlet}** — your top outlet. Ensure it never runs out of stock",
            f"- Track daily sales against the **${avg_daily:,.2f}** benchmark",
            f"- Discount rate: {abs(df['discount'].sum())/df['gross_sales'].sum()*100:.1f}% — "
            f"{'healthy' if abs(df['discount'].sum())/df['gross_sales'].sum()*100 < 10 else 'review discount policies'}",
        ]
        return "\n".join(lines)

    def _discount_analysis(df):
        total_gross = df["gross_sales"].sum()
        total_disc = abs(df["discount"].sum())
        disc_pct = total_disc/total_gross*100 if total_gross else 0
        # By outlet
        out = df.groupby("outlet").agg(gross=("gross_sales","sum"), disc=("discount","sum")).reset_index()
        out["disc_abs"] = out["disc"].abs()
        out["disc_pct"] = out["disc_abs"]/out["gross"]*100
        out = out.sort_values("disc_pct", ascending=False)
        # By product (top discounted)
        prod = df.groupby("product").agg(gross=("gross_sales","sum"), disc=("discount","sum")).reset_index()
        prod["disc_abs"] = prod["disc"].abs()
        prod = prod[prod["disc_abs"] > 0].sort_values("disc_abs", ascending=False)
        lines = [
            "### Discount Analysis\n",
            f"**Total discounts:** ${total_disc:,.2f} out of ${total_gross:,.2f} gross = **{disc_pct:.1f}%**\n",
        ]
        if disc_pct == 0:
            lines.append("No discounts recorded in this period.")
            return "\n".join(lines)
        lines.append("**By Outlet:**\n")
        for _, r in out.iterrows():
            lines.append(f"- {r['outlet']}: ${r['disc_abs']:,.2f} ({r['disc_pct']:.1f}%)")
        if len(prod):
            lines.append("\n**Most Discounted Products:**\n")
            for _, r in prod.head(8).iterrows():
                lines.append(f"- {r['product']}: ${r['disc_abs']:,.2f} discounted")
        return "\n".join(lines)

    def _daily_trend(df):
        daily = df.groupby("sales_date").agg(
            rev=("net_sales","sum"), units=("primary_units","sum")).reset_index().sort_values("sales_date")
        avg_rev = daily["rev"].mean()
        best = daily.loc[daily["rev"].idxmax()]
        worst = daily.loc[daily["rev"].idxmin()]
        lines = [
            "### Daily Revenue Trend\n",
            "| Date | Revenue | Units | vs Avg |",
            "|------|---------|-------|--------|",
        ]
        for _, r in daily.iterrows():
            diff = r["rev"] - avg_rev
            flag = "+" if diff >= 0 else ""
            lines.append(f"| {r['sales_date'].strftime('%a %b %d')} | ${r['rev']:,.2f} | "
                         f"{r['units']:,.0f} | {flag}${diff:,.2f} |")
        lines.append(f"\n**Best day:** {best['sales_date'].strftime('%A %b %d')} at **${best['rev']:,.2f}**")
        lines.append(f"\n**Slowest day:** {worst['sales_date'].strftime('%A %b %d')} at **${worst['rev']:,.2f}**")
        lines.append(f"\n**Average:** ${avg_rev:,.2f}/day — "
                     f"{'Stable' if daily['rev'].std()/avg_rev < 0.15 else 'Variable'} "
                     f"(std dev ${daily['rev'].std():,.2f})")
        return "\n".join(lines)

    # ── Analysis buttons ─────────────────────────────────────────────────
    analyses = {
        "Top Products":       ("Best-selling items by revenue", _top_products),
        "Menu Review":        ("Low performers to consider removing", _underperformers),
        "Day-of-Week":        ("Staffing and daily patterns", _day_of_week),
        "Outlet Comparison":  ("Performance across locations", _outlet_comparison),
        "Category Breakdown": ("Revenue by menu category", _category_breakdown),
        "Weekly Strategy":    ("Full operational recommendation", _weekly_strategy),
        "Discount Analysis":  ("Where discounts are going", _discount_analysis),
        "Daily Trend":        ("Day-by-day revenue with benchmarks", _daily_trend),
    }

    if "insight_result" not in st.session_state:
        st.session_state.insight_result = None

    btn_cols = st.columns(4)
    for i, (name, (desc, func)) in enumerate(analyses.items()):
        with btn_cols[i % 4]:
            if st.button(f"📊 {name}", key=f"ai_{name}", help=desc, use_container_width=True):
                st.session_state.insight_result = (name, func(f))
                st.rerun()

    st.markdown("---")

    # Show result
    if st.session_state.insight_result:
        rname, rtext = st.session_state.insight_result
        st.markdown(rtext)
        if st.button("Clear", key="clear_insight"):
            st.session_state.insight_result = None
            st.rerun()

    # ── Optional: Claude API upgrade for free-form questions ─────────────
    with st.expander("💬 Free-form Chat (requires API key)", expanded=False):
        st.caption("Optionally connect Claude AI for custom questions beyond the built-in analyses.")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            api_key = st.text_input("Anthropic API Key", type="password",
                                    placeholder="sk-ant-...", key="api_key_input",
                                    help="Get your key at console.anthropic.com")
        if not api_key:
            st.info("The built-in analyses above work without a key. Enter an API key here only if you want to ask custom questions.")
        else:
            def build_data_summary(df):
                summary = []
                summary.append(f"Date range: {df['sales_date'].min().strftime('%Y-%m-%d')} to {df['sales_date'].max().strftime('%Y-%m-%d')}")
                summary.append(f"Total days: {df['sales_date'].nunique()}")
                summary.append(f"Total net sales: ${df['net_sales'].sum():,.2f}")
                summary.append(f"Total gross sales: ${df['gross_sales'].sum():,.2f}")
                summary.append(f"Total discounts: ${df['discount'].sum():,.2f}")
                summary.append(f"Total units sold: {df['primary_units'].sum():,.0f}")
                summary.append(f"Unique products: {df['product'].nunique()}")
                summary.append(f"Outlets: {', '.join(df['outlet'].unique())}")
                top_p = df.groupby("product").agg(
                    rev=("net_sales","sum"), units=("primary_units","sum"),
                    days=("sales_date","nunique")).reset_index().sort_values("rev", ascending=False)
                summary.append("\nTop products by revenue:")
                for _, r in top_p.head(15).iterrows():
                    summary.append(f"  {r['product']}: ${r['rev']:,.2f} rev, {r['units']:,.0f} units, sold {r['days']} days")
                out = df.groupby("outlet").agg(
                    rev=("net_sales","sum"), units=("primary_units","sum"),
                    days=("sales_date","nunique"), items=("product","nunique")).reset_index().sort_values("rev", ascending=False)
                summary.append("\nRevenue by outlet:")
                for _, r in out.iterrows():
                    avg_d = r["rev"]/r["days"] if r["days"] else 0
                    summary.append(f"  {r['outlet']}: ${r['rev']:,.2f} total, ${avg_d:,.2f}/day, {r['units']:,.0f} units, {r['items']} products")
                dow = df.groupby("day_of_week").agg(
                    rev=("net_sales","sum"), units=("primary_units","sum"),
                    days=("sales_date","nunique")).reset_index()
                dow["avg_rev"] = dow["rev"]/dow["days"]
                dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                dow["day_of_week"] = pd.Categorical(dow["day_of_week"], categories=dow_order, ordered=True)
                dow = dow.sort_values("day_of_week")
                summary.append("\nAvg daily revenue by day of week:")
                for _, r in dow.iterrows():
                    summary.append(f"  {r['day_of_week']}: ${r['avg_rev']:,.2f}/day, {r['units']/r['days']:,.0f} units/day")
                if "menu_category" in df.columns:
                    cat = df.groupby("menu_category")["net_sales"].sum().sort_values(ascending=False)
                    summary.append("\nRevenue by category:")
                    for c, v in cat.items():
                        if c:
                            summary.append(f"  {c}: ${v:,.2f}")
                return "\n".join(summary)

            data_context = build_data_summary(f)
            SYSTEM_PROMPT = f"""You are a sales analytics expert for Kalachandji's, a vegetarian restaurant on the UT Dallas campus. Analyze data to help with menu, staffing, and operations.

Current filtered data:
{data_context}

Be specific, cite numbers, use bullet points. Format currency as $X,XXX.XX."""

            if "messages" not in st.session_state:
                st.session_state.messages = []

            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                with st.chat_message("assistant"):
                    try:
                        import anthropic
                        client = anthropic.Anthropic(api_key=api_key)
                        api_messages = [{"role": m["role"], "content": m["content"]}
                                        for m in st.session_state.messages]
                        with st.spinner("Analyzing..."):
                            response = client.messages.create(
                                model="claude-sonnet-4-20250514", max_tokens=1500,
                                system=SYSTEM_PROMPT, messages=api_messages)
                        reply = response.content[0].text
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            if user_input := st.chat_input("Ask a custom question..."):
                st.session_state.messages.append({"role": "user", "content": user_input})
                st.rerun()

            if st.session_state.messages:
                if st.button("Clear Chat", key="clear_chat"):
                    st.session_state.messages = []
                    st.rerun()
