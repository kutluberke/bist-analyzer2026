"""
BIST Radar — Turkish Stock Market Screener
app.py — Bloomberg-inspired dark financial terminal UI
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="BIST Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from data.bist_tickers import ALL_SECTORS, TICKER_SYMBOLS
from modules.data_fetcher import fetch_all_tickers, fetch_price_history
from modules.screener import (
    apply_filters,
    build_display_df,
    score_dataframe,
    SIGNAL_AL,
    SIGNAL_BEKLE,
    SIGNAL_SAT,
)
from modules.charts import build_price_chart, build_score_radar
from modules.analyzer import analyze_stock, analyze_short_term, analyze_long_term
from modules.backtest import render_backtest_tab

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ── Boot-time validation ──────────────────────────────────────────────────────

def _check_env() -> None:
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key or groq_key == "your_groq_api_key_here":
        st.warning(
            "**GROQ_API_KEY** tanımlanmamış. `.env` dosyanıza gerçek anahtarınızı ekleyin.",
            icon="🔑",
        )

_check_env()


# ── Design tokens ─────────────────────────────────────────────────────────────
# Bloomberg-inspired dark financial terminal palette

_CSS = """
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap');

/* ── Root tokens ── */
:root {
  --bg-base:      #060D18;
  --bg-surface:   #0C1B2E;
  --bg-card:      #0F2235;
  --bg-elevated:  #162D45;
  --bg-hover:     #1A3350;

  --border-dim:   #1A3350;
  --border-base:  #1E4060;
  --border-bright:#2A5A80;

  --text-primary: #E2EBF5;
  --text-secondary:#7A9BB8;
  --text-dim:     #3D6080;
  --text-muted:   #2A4A65;

  --accent:       #00D4AA;
  --accent-dim:   #00A07E;
  --accent-glow:  rgba(0,212,170,0.15);

  --green:        #00E676;
  --green-dim:    rgba(0,230,118,0.12);
  --yellow:       #FFD600;
  --yellow-dim:   rgba(255,214,0,0.12);
  --red:          #FF4444;
  --red-dim:      rgba(255,68,68,0.12);

  --radius-sm:    6px;
  --radius-md:    10px;
  --radius-lg:    14px;

  --font-ui:      'Space Grotesk', 'Inter', system-ui, sans-serif;
  --font-mono:    'JetBrains Mono', 'Fira Code', monospace;
}

/* ── Global reset ── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background-color: var(--bg-base) !important;
  font-family: var(--font-ui) !important;
  color: var(--text-primary) !important;
}

/* Hide Streamlit chrome */
[data-testid="stHeader"]          { display: none !important; }
[data-testid="stDecoration"]      { display: none !important; }
footer                             { display: none !important; }
#MainMenu                          { display: none !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar               { width: 5px; height: 5px; }
::-webkit-scrollbar-track         { background: var(--bg-base); }
::-webkit-scrollbar-thumb         { background: var(--border-base); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover   { background: var(--border-bright); }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
  background: var(--bg-surface) !important;
  border-right: 1px solid var(--border-dim) !important;
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

/* Sidebar widget labels */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stMarkdown p {
  font-family: var(--font-ui) !important;
  color: var(--text-secondary) !important;
  font-size: 0.78rem !important;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

/* Sidebar selectboxes & inputs */
section[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
section[data-testid="stSidebar"] [data-testid="stMultiSelect"] > div > div {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-base) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-ui) !important;
}

/* Sidebar checkboxes */
section[data-testid="stSidebar"] [data-testid="stCheckbox"] label {
  color: var(--text-primary) !important;
  font-size: 0.88rem !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
}

/* Sidebar slider */
section[data-testid="stSidebar"] [data-testid="stSlider"] > div > div > div {
  background: var(--accent) !important;
}

/* Sidebar hr */
section[data-testid="stSidebar"] hr {
  border-color: var(--border-dim) !important;
  margin: 0.6rem 0 !important;
}

/* ── Main content padding ── */
[data-testid="stMain"] > div > div > div { padding-top: 0 !important; }
.main .block-container { padding: 1.2rem 2rem 3rem 2rem !important; max-width: 100% !important; }

/* ── Buttons ── */
.stButton > button {
  background: var(--bg-elevated) !important;
  color: var(--accent) !important;
  border: 1px solid var(--border-base) !important;
  border-radius: var(--radius-sm) !important;
  font-family: var(--font-ui) !important;
  font-weight: 600 !important;
  font-size: 0.82rem !important;
  letter-spacing: 0.04em !important;
  text-transform: uppercase !important;
  padding: 0.45rem 1rem !important;
  transition: all 0.15s ease !important;
}
.stButton > button:hover {
  background: var(--accent-glow) !important;
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}
.stButton > button[kind="primary"] {
  background: var(--accent) !important;
  color: #000 !important;
  border-color: var(--accent) !important;
}

/* ── Selectboxes ── */
[data-testid="stSelectbox"] > div > div {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-base) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-mono) !important;
  font-size: 0.88rem !important;
}

/* ── Metric containers (native) ── */
div[data-testid="metric-container"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-dim) !important;
  border-radius: var(--radius-md) !important;
  padding: 0.75rem 1rem !important;
}
div[data-testid="metric-container"] label {
  color: var(--text-dim) !important;
  font-size: 0.7rem !important;
  font-family: var(--font-ui) !important;
  font-weight: 600 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
}
div[data-testid="stMetricValue"] {
  color: var(--text-primary) !important;
  font-family: var(--font-mono) !important;
  font-size: 1.6rem !important;
  font-weight: 600 !important;
}
div[data-testid="stMetricDelta"] {
  font-family: var(--font-mono) !important;
  font-size: 0.8rem !important;
}

/* ── DataFrame ── */
.stDataFrame { border: 1px solid var(--border-dim) !important; border-radius: var(--radius-md) !important; }
.stDataFrame iframe { border-radius: var(--radius-md) !important; }

/* ── Expanders ── */
[data-testid="stExpander"] {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border-dim) !important;
  border-radius: var(--radius-md) !important;
}
[data-testid="stExpander"] summary {
  font-family: var(--font-ui) !important;
  font-weight: 600 !important;
  font-size: 0.85rem !important;
  letter-spacing: 0.04em !important;
  color: var(--text-secondary) !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] > div { border-top-color: var(--accent) !important; }

/* ── Caption ── */
.stCaption, [data-testid="stCaptionContainer"] {
  font-family: var(--font-mono) !important;
  color: var(--text-dim) !important;
  font-size: 0.72rem !important;
}

/* ── st.info / st.warning ── */
[data-testid="stAlert"] {
  background: var(--bg-elevated) !important;
  border-radius: var(--radius-md) !important;
  border: 1px solid var(--border-base) !important;
  font-family: var(--font-ui) !important;
}

/* ── Download button ── */
[data-testid="stDownloadButton"] > button {
  background: transparent !important;
  color: var(--text-secondary) !important;
  border: 1px solid var(--border-base) !important;
  border-radius: var(--radius-sm) !important;
  font-size: 0.78rem !important;
  font-family: var(--font-ui) !important;
}

/* ── CUSTOM COMPONENTS ── */

/* Terminal header bar */
.trm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, #0C1B2E 0%, #060D18 60%);
  border-bottom: 2px solid var(--border-base);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  padding: 1rem 1.5rem 0.9rem;
  margin-bottom: 0;
}
.trm-logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.trm-logo-text {
  font-family: var(--font-ui);
  font-weight: 700;
  font-size: 1.55rem;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}
.trm-logo-text span { color: var(--accent); }
.trm-logo-sub {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--text-dim);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-top: 2px;
}
.trm-live {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--green);
  letter-spacing: 0.08em;
  font-weight: 600;
}
.trm-live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--green);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0,230,118,0.4); }
  50%       { opacity: 0.5; box-shadow: 0 0 0 5px rgba(0,230,118,0); }
}
.trm-ts {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-dim);
  letter-spacing: 0.04em;
  text-align: right;
}

/* Section label */
.sec-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--font-ui);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin: 1.5rem 0 0.75rem;
}
.sec-label::before {
  content: '';
  display: inline-block;
  width: 3px;
  height: 14px;
  background: var(--accent);
  border-radius: 2px;
}
.sec-label::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-dim);
  margin-left: 0.3rem;
}

/* KPI card (custom) */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 0.6rem;
  margin-bottom: 0.25rem;
}
.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-md);
  padding: 0.85rem 1rem;
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--border-base);
}
.kpi-card.green::before { background: var(--green); }
.kpi-card.yellow::before { background: var(--yellow); }
.kpi-card.red::before    { background: var(--red); }
.kpi-card.accent::before { background: var(--accent); }
.kpi-label {
  font-family: var(--font-ui);
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 0.35rem;
}
.kpi-value {
  font-family: var(--font-mono);
  font-size: 1.6rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.1;
}
.kpi-value.green  { color: var(--green); }
.kpi-value.yellow { color: var(--yellow); }
.kpi-value.red    { color: var(--red); }
.kpi-value.accent { color: var(--accent); }

/* Signal badge */
.sig-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.06em;
}
.sig-al    { background: var(--green-dim); color: var(--green);  border: 1px solid rgba(0,230,118,0.3); }
.sig-bekle { background: var(--yellow-dim); color: var(--yellow); border: 1px solid rgba(255,214,0,0.3); }
.sig-sat   { background: var(--red-dim);   color: var(--red);    border: 1px solid rgba(255,68,68,0.3); }

/* Sidebar brand block */
.sb-brand {
  background: linear-gradient(135deg, #0C1B2E 0%, #091525 100%);
  border-bottom: 1px solid var(--border-dim);
  padding: 1.1rem 1.2rem 1rem;
  margin-bottom: 0.5rem;
}
.sb-title {
  font-family: var(--font-ui);
  font-weight: 700;
  font-size: 1.15rem;
  color: var(--text-primary);
  line-height: 1;
}
.sb-title span { color: var(--accent); }
.sb-sub {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-dim);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 3px;
}

/* Sidebar section header */
.sb-sec {
  font-family: var(--font-ui);
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  padding: 0.15rem 0;
}

/* Metric card (detail view) */
.mc-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}
.mc-card {
  background: var(--bg-card);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  padding: 0.65rem 0.8rem;
  text-align: center;
}
.mc-label {
  font-family: var(--font-ui);
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 3px;
}
.mc-value {
  font-family: var(--font-mono);
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-primary);
}
.mc-value.green  { color: var(--green); }
.mc-value.red    { color: var(--red); }
.mc-value.yellow { color: var(--yellow); }
.mc-value.accent { color: var(--accent); }

/* Detail header */
.det-header {
  background: var(--bg-card);
  border: 1px solid var(--border-dim);
  border-left: 3px solid var(--accent);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding: 1rem 1.4rem;
  margin-bottom: 1rem;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.det-name {
  font-family: var(--font-ui);
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}
.det-meta {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-dim);
  letter-spacing: 0.06em;
  margin-top: 3px;
}
.det-price {
  text-align: right;
}
.det-price-val {
  font-family: var(--font-mono);
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}
.det-price-chg {
  font-family: var(--font-mono);
  font-size: 0.82rem;
  font-weight: 600;
  margin-top: 4px;
}
.det-price-chg.up   { color: var(--green); }
.det-price-chg.down { color: var(--red); }
.det-price-chg.flat { color: var(--text-dim); }

/* AI analysis sections */
.ai-card {
  background: var(--bg-card);
  border: 1px solid var(--border-dim);
  border-left: 3px solid var(--accent);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding: 0.85rem 1.1rem;
  margin-bottom: 0.6rem;
  font-family: var(--font-ui);
  font-size: 0.9rem;
  line-height: 1.65;
  color: var(--text-secondary);
}
.ai-card.risk  { border-left-color: var(--red); }
.ai-card.oneri { border-left-color: var(--yellow); }
.ai-card-title {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 0.45rem;
  color: var(--accent);
  font-family: var(--font-ui);
}
.ai-card.risk  .ai-card-title { color: var(--red); }
.ai-card.oneri .ai-card-title { color: var(--yellow); }

/* Footer */
.trm-footer {
  margin-top: 2.5rem;
  padding: 0.85rem 0;
  border-top: 1px solid var(--border-dim);
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  text-align: center;
}
.trm-footer a { color: var(--text-dim); text-decoration: none; }

/* Suppress Streamlit's auto-injected anchor links on headings */
[data-testid="stHeaderActionElements"] { display: none !important; }
</style>
""".strip()

st.markdown(_CSS, unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        '<div class="sb-brand">'
        '<div class="sb-title">BIST<span>RADAR</span></div>'
        '<div class="sb-sub">Hisse Tarama Platformu · v2.0</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sb-sec">Sektör</div>', unsafe_allow_html=True)
    selected_sectors: list[str] = st.multiselect(
        "Sektör",
        options=ALL_SECTORS,
        default=[],
        label_visibility="collapsed",
        placeholder="Tüm sektörler",
    )

    st.markdown('<div class="sb-sec" style="margin-top:0.9rem">Piyasa Değeri</div>', unsafe_allow_html=True)
    MCAP_OPTIONS = {
        "Tümü":           (0, None),
        "> ₺10 Milyar":   (10_000_000_000, None),
        "> ₺50 Milyar":   (50_000_000_000, None),
        "> ₺100 Milyar":  (100_000_000_000, None),
        "> ₺500 Milyar":  (500_000_000_000, None),
    }
    mcap_choice = st.selectbox("Piyasa Değeri", list(MCAP_OPTIONS.keys()), index=0, label_visibility="collapsed")
    mcap_min, mcap_max = MCAP_OPTIONS[mcap_choice]

    st.markdown('<div class="sb-sec" style="margin-top:0.9rem">F/K Filtresi</div>', unsafe_allow_html=True)
    pe_filter_on = st.checkbox("F/K filtresi uygula", value=False)
    pe_min: float | None = None
    pe_max: float | None = None
    if pe_filter_on:
        pe_range = st.slider("F/K", min_value=0.0, max_value=100.0, value=(0.0, 40.0), step=0.5, label_visibility="collapsed")
        pe_min, pe_max = float(pe_range[0]), float(pe_range[1])

    st.markdown('<div class="sb-sec" style="margin-top:0.9rem">52H Getiri Min.</div>', unsafe_allow_html=True)
    min_52w = st.slider("52H Getiri", min_value=-100, max_value=500, value=-100, step=5, label_visibility="collapsed")
    min_52w_return: float | None = None if min_52w == -100 else float(min_52w)

    st.markdown('<div class="sb-sec" style="margin-top:0.9rem">Hacim</div>', unsafe_allow_html=True)
    VOL_OPTIONS = {
        "Tümü":             0,
        "> 1M adet/gün":    1_000_000,
        "> 5M adet/gün":    5_000_000,
        "> 10M adet/gün":   10_000_000,
        "> 50M adet/gün":   50_000_000,
    }
    vol_choice = st.selectbox("Hacim", list(VOL_OPTIONS.keys()), index=0, label_visibility="collapsed")
    min_avg_volume: float | None = VOL_OPTIONS[vol_choice] or None

    st.markdown('<div class="sb-sec" style="margin-top:0.9rem">Sinyal</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    show_al    = c1.checkbox("AL",    value=True)
    show_bekle = c2.checkbox("BEKLE", value=True)
    show_sat   = c3.checkbox("SAT",   value=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("↺  VERİLERİ YENİLE", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.markdown(
        f'<div style="font-family:var(--font-mono);font-size:0.62rem;color:var(--text-muted);'
        f'padding:0.5rem 0;letter-spacing:0.05em">'
        f'{len(TICKER_SYMBOLS)} hisse · BIST · Yahoo Finance</div>',
        unsafe_allow_html=True,
    )


# ── Terminal header ───────────────────────────────────────────────────────────

try:
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Istanbul"))
except ImportError:
    import pytz
    now = datetime.now(pytz.timezone("Europe/Istanbul"))
now_str = now.strftime("%d.%m.%Y  %H:%M")
st.markdown(
    f'<div class="trm-header">'
    f'  <div class="trm-logo">'
    f'    <div>'
    f'      <div class="trm-logo-text">BIST<span>RADAR</span></div>'
    f'      <div class="trm-logo-sub">Borsa İstanbul · Hisse Tarama &amp; Analiz</div>'
    f'    </div>'
    f'  </div>'
    f'  <div style="display:flex;align-items:center;gap:1.5rem">'
    f'    <div class="trm-live"><div class="trm-live-dot"></div>CANLI</div>'
    f'    <div class="trm-ts">{now_str}<br>'
    f'      <span style="color:var(--text-muted)">UTC+3 · İSTANBUL</span></div>'
    f'  </div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_enriched_data(tickers: tuple[str, ...]) -> pd.DataFrame:
    return fetch_all_tickers(tickers)


# Session-state flags
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

if "data_requested" not in st.session_state:
    st.session_state.data_requested = False

# Lazy load gate — don't fetch on every startup; wait for user trigger
if not st.session_state.data_requested:
    st.markdown(
        '<div style="text-align:center;padding:3rem 1rem">'
        '<div style="font-family:var(--font-mono);font-size:1rem;color:var(--text-secondary);'
        'margin-bottom:1.5rem;letter-spacing:0.08em">BIST · 100+ HİSSE</div>'
        '<div style="font-family:var(--font-ui);font-size:0.85rem;color:var(--text-dim);'
        'margin-bottom:2rem">Gerçek zamanlı piyasa verilerini yüklemek için butona tıklayın.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    _, _mid, _ = st.columns([1, 2, 1])
    with _mid:
        if st.button("▶  Piyasa Verilerini Yükle", width="stretch"):
            st.session_state.data_requested = True
            st.rerun()
    st.stop()

with st.spinner("Piyasa verileri yükleniyor… (ilk açılışta 1-2 dk sürebilir)"):
    raw_df = load_enriched_data(tuple(TICKER_SYMBOLS))

if raw_df.empty:
    st.error(
        "Hiçbir hisse için veri alınamadı. "
        "İnternet bağlantınızı kontrol edin veya sol menüden verileri yenileyin."
    )
    st.stop()

_failed = st.session_state.get("fetch_failed", [])
if _failed:
    with st.expander(f"⚠  {len(_failed)} hisse yüklenemedi", expanded=False):
        st.code(", ".join(_failed))

try:
    scored_df = score_dataframe(raw_df)
except Exception as _score_err:
    logger.error("Scoring failed: %s", _score_err)
    st.error(f"Skorlama hatası: {_score_err}")
    st.stop()

filtered_df = apply_filters(
    scored_df,
    sectors=selected_sectors if selected_sectors else None,
    market_cap_min=mcap_min,
    market_cap_max=mcap_max,
    pe_min=pe_min,
    pe_max=pe_max,
    min_52w_return=min_52w_return,
    min_avg_volume=min_avg_volume,
)

wanted_signals = []
if show_al:    wanted_signals.append(SIGNAL_AL)
if show_bekle: wanted_signals.append(SIGNAL_BEKLE)
if show_sat:   wanted_signals.append(SIGNAL_SAT)

if "signal" in filtered_df.columns and wanted_signals:
    filtered_df = filtered_df[filtered_df["signal"].isin(wanted_signals)]


_tab_screener, _tab_backtest = st.tabs(["Tarayıcı", "Backtest"])

with _tab_screener:

    # ── KPI scoreboard ────────────────────────────────────────────────────────

    total       = len(filtered_df)
    count_al    = int((filtered_df["signal"] == SIGNAL_AL).sum())    if "signal" in filtered_df.columns else 0
    count_bekle = int((filtered_df["signal"] == SIGNAL_BEKLE).sum()) if "signal" in filtered_df.columns else 0
    count_sat   = int((filtered_df["signal"] == SIGNAL_SAT).sum())   if "signal" in filtered_df.columns else 0
    avg_return  = filtered_df["52w_return"].dropna().mean()  if "52w_return"   in filtered_df.columns and not filtered_df.empty else None
    avg_score   = filtered_df["total_score"].dropna().mean() if "total_score"  in filtered_df.columns and not filtered_df.empty else None

    ret_color   = "green" if (avg_return or 0) >= 0 else "red"
    score_color = "accent" if (avg_score or 0) >= 65 else ("yellow" if (avg_score or 0) >= 40 else "red")

    st.markdown(
        f'<div class="sec-label">Özet</div>'
        f'<div class="kpi-grid">'
        f'  <div class="kpi-card accent">'
        f'    <div class="kpi-label">Toplam Hisse</div>'
        f'    <div class="kpi-value accent">{total}</div>'
        f'  </div>'
        f'  <div class="kpi-card green">'
        f'    <div class="kpi-label">AL Sinyali</div>'
        f'    <div class="kpi-value green">{count_al}</div>'
        f'  </div>'
        f'  <div class="kpi-card yellow">'
        f'    <div class="kpi-label">BEKLE Sinyali</div>'
        f'    <div class="kpi-value yellow">{count_bekle}</div>'
        f'  </div>'
        f'  <div class="kpi-card red">'
        f'    <div class="kpi-label">SAT Sinyali</div>'
        f'    <div class="kpi-value red">{count_sat}</div>'
        f'  </div>'
        f'  <div class="kpi-card">'
        f'    <div class="kpi-label">Ort. 52H Getiri</div>'
        f'    <div class="kpi-value {ret_color}">'
        f'      {"—" if avg_return is None else f"{avg_return:+.1f}%"}'
        f'    </div>'
        f'  </div>'
        f'  <div class="kpi-card">'
        f'    <div class="kpi-label">Ort. Skor</div>'
        f'    <div class="kpi-value {score_color}">'
        f'      {"—" if avg_score is None else f"{avg_score:.1f}"}'
        f'    </div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Sector breakdown chart ────────────────────────────────────────────────

    if not filtered_df.empty and "sector" in filtered_df.columns:
        with st.expander("  Sektör Dağılımı", expanded=False):
            sector_counts = (
                filtered_df.groupby("sector")["signal"]
                .value_counts()
                .unstack(fill_value=0)
            )
            for sig in [SIGNAL_AL, SIGNAL_BEKLE, SIGNAL_SAT]:
                if sig not in sector_counts.columns:
                    sector_counts[sig] = 0
            sector_counts = sector_counts[[SIGNAL_AL, SIGNAL_BEKLE, SIGNAL_SAT]]
            sector_counts.columns = ["AL", "BEKLE", "SAT"]

            import plotly.graph_objects as go

            fig_sec = go.Figure()
            for lbl, color in [("AL", "#00E676"), ("BEKLE", "#FFD600"), ("SAT", "#FF4444")]:
                fig_sec.add_trace(go.Bar(
                    name=lbl,
                    x=sector_counts.index.tolist(),
                    y=sector_counts[lbl].tolist(),
                    marker_color=color,
                    marker_line_width=0,
                ))
            fig_sec.update_layout(
                barmode="stack",
                plot_bgcolor="#0C1B2E",
                paper_bgcolor="#0C1B2E",
                font=dict(family="Space Grotesk, Inter, sans-serif", color="#7A9BB8", size=11),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
                margin=dict(l=0, r=0, t=30, b=0),
                height=260,
                xaxis=dict(gridcolor="#1A3350", tickfont=dict(size=10)),
                yaxis=dict(gridcolor="#1A3350", tickfont=dict(size=10)),
            )
            st.plotly_chart(fig_sec, width="stretch")

    # ── Stock table ───────────────────────────────────────────────────────────

    st.markdown(
        f'<a id="hisse-listesi" style="display:none"></a>'
        f'<div class="sec-label">Hisse Listesi — {total} sonuç</div>',
        unsafe_allow_html=True,
    )

    if filtered_df.empty:
        st.warning("Seçili filtrelere uyan hisse bulunamadı. Filtreleri genişletin.")
    else:
        s_col, _ = st.columns([3, 1])
        SORT_OPTIONS = {
            "Skor ↓":            ("total_score", False),
            "52H Getiri ↓":      ("52w_return",  False),
            "52H Getiri ↑":      ("52w_return",  True),
            "F/K ↑":             ("pe_ratio",    True),
            "F/K ↓":             ("pe_ratio",    False),
            "Piyasa Değeri ↓":   ("market_cap",  False),
            "Fiyat ↓":           ("price",       False),
        }
        with s_col:
            sort_choice = st.selectbox("Sıralama", list(SORT_OPTIONS.keys()), index=0)

        sort_column, sort_asc = SORT_OPTIONS[sort_choice]
        sorted_df = (
            filtered_df.sort_values(sort_column, ascending=sort_asc, na_position="last")
            if sort_column in filtered_df.columns else filtered_df
        )

        display_df = build_display_df(sorted_df)
        display_df.insert(0, "Ticker", sorted_df.index)
        display_df = display_df.reset_index(drop=True)

        st.dataframe(
            display_df,
            width="stretch",
            height=min(620, 56 + len(display_df) * 36),
            column_config={
                "Ticker":        st.column_config.TextColumn("TICKER", width="small"),
                "Şirket":        st.column_config.TextColumn("ŞİRKET", width="medium"),
                "Sektör":        st.column_config.TextColumn("SEKTÖR", width="small"),
                "Fiyat (₺)":     st.column_config.NumberColumn("FİYAT", format="₺%.2f"),
                "F/K":           st.column_config.TextColumn("F/K", width="small"),
                "Piyasa Değeri": st.column_config.TextColumn("PİY. DEĞERİ", width="medium"),
                "52H Getiri %":  st.column_config.NumberColumn("52H GETİRİ", format="%.2f%%"),
                "Skor":          st.column_config.ProgressColumn("SKOR", min_value=0, max_value=100, format="%.0f"),
                "Sinyal":        st.column_config.TextColumn("SİNYAL", width="small"),
            },
            hide_index=True,
        )

        csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="↓  CSV İndir",
            data=csv_data,
            file_name="bist_radar.csv",
            mime="text/csv",
        )

    # ── Watchlist panel ───────────────────────────────────────────────────────

    if st.session_state.watchlist:
        wl_tickers = [t for t in st.session_state.watchlist if t in scored_df.index]
        if wl_tickers:
            st.markdown('<div class="sec-label">İzleme Listem</div>', unsafe_allow_html=True)
            wl_display = build_display_df(scored_df.loc[wl_tickers])
            wl_display.insert(0, "Ticker", wl_tickers)
            wl_display = wl_display.reset_index(drop=True)
            st.dataframe(
                wl_display,
                width="stretch",
                height=min(400, 56 + len(wl_display) * 36),
                column_config={
                    "Ticker":        st.column_config.TextColumn("TICKER", width="small"),
                    "Şirket":        st.column_config.TextColumn("ŞİRKET", width="medium"),
                    "Fiyat (₺)":     st.column_config.NumberColumn("FİYAT", format="₺%.2f"),
                    "Skor":          st.column_config.ProgressColumn("SKOR", min_value=0, max_value=100, format="%.0f"),
                    "Sinyal":        st.column_config.TextColumn("SİNYAL", width="small"),
                },
                hide_index=True,
            )

    # ── Detail view ───────────────────────────────────────────────────────────

    st.markdown('<div class="sec-label">Hisse Detay</div>', unsafe_allow_html=True)

    all_tickers_sorted = sorted(scored_df.index.tolist())
    ticker_labels = {
        t: f"{t}  —  {scored_df.loc[t, 'name']}" if "name" in scored_df.columns else t
        for t in all_tickers_sorted
    }
    default_ticker = (
        filtered_df.index[0] if not filtered_df.empty
        else (all_tickers_sorted[0] if all_tickers_sorted else None)
    )
    default_idx = all_tickers_sorted.index(default_ticker) if default_ticker in all_tickers_sorted else 0

    selected_ticker: str = st.selectbox(
        "Hisse",
        options=all_tickers_sorted,
        index=default_idx,
        format_func=lambda t: ticker_labels.get(t, t),
        label_visibility="collapsed",
    )

    if selected_ticker:
        row        = scored_df.loc[selected_ticker].to_dict()
        row["ticker"] = selected_ticker
        signal_val = row.get("signal", "—")
        price_val  = row.get("price")
        prev_close = row.get("prev_close")
        day_chg    = ((price_val - prev_close) / prev_close * 100) if price_val and prev_close and prev_close != 0 else None

        price_str  = f"₺{price_val:,.2f}" if price_val else "—"
        if day_chg is None:
            chg_css, chg_str = "flat", "—"
        elif day_chg >= 0:
            chg_css, chg_str = "up",   f"▲ {day_chg:+.2f}%"
        else:
            chg_css, chg_str = "down", f"▼ {day_chg:.2f}%"

        sig_map = {
            SIGNAL_AL:    ('<span class="sig-badge sig-al">▲ AL</span>',    "var(--green)"),
            SIGNAL_BEKLE: ('<span class="sig-badge sig-bekle">◆ BEKLE</span>', "var(--yellow)"),
            SIGNAL_SAT:   ('<span class="sig-badge sig-sat">▼ SAT</span>',  "var(--red)"),
        }
        sig_html, sig_border = sig_map.get(signal_val, (signal_val, "var(--border-base)"))

        total_score = row.get("total_score", 0) or 0
        score_bar_color = "#00E676" if total_score >= 65 else ("#FFD600" if total_score >= 40 else "#FF4444")

        st.markdown(
            f'<div class="det-header" style="border-left-color:{sig_border}">'
            f'  <div>'
            f'    <div class="det-name">{row.get("name", selected_ticker)}</div>'
            f'    <div class="det-meta">'
            f'      <span style="color:var(--accent);font-weight:600">{selected_ticker}</span>'
            f'      &nbsp;·&nbsp; {row.get("sector","")}'
            f'      &nbsp;·&nbsp; {sig_html}'
            f'      &nbsp;·&nbsp; '
            f'      <span style="color:var(--text-dim)">SKOR:</span> '
            f'      <span style="color:{score_bar_color};font-weight:700">{total_score:.0f}</span>'
            f'    </div>'
            f'  </div>'
            f'  <div class="det-price">'
            f'    <div class="det-price-val">{price_str}</div>'
            f'    <div class="det-price-chg {chg_css}">{chg_str}</div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        _in_wl = selected_ticker in st.session_state.watchlist
        _wl_label = "★ Listeden Çıkar" if _in_wl else "☆ İzleme Listesine Ekle"
        if st.button(_wl_label, key=f"wl_{selected_ticker}"):
            if _in_wl:
                st.session_state.watchlist.remove(selected_ticker)
            else:
                st.session_state.watchlist.append(selected_ticker)
            st.rerun()

        chart_col, metrics_col = st.columns([2, 1], gap="large")

        with chart_col:
            _period_options = {
                "1 Ay": "1mo",
                "3 Ay": "3mo",
                "6 Ay": "6mo",
                "1 Yıl": "1y",
                "2 Yıl": "2y",
                "5 Yıl": "5y",
            }
            _period_label = st.radio(
                "Periyot",
                list(_period_options.keys()),
                index=3,
                horizontal=True,
                label_visibility="collapsed",
                key=f"period_{selected_ticker}",
            )
            _period = _period_options[_period_label]

            with st.spinner("Fiyat grafiği yükleniyor…"):
                hist_df = fetch_price_history(selected_ticker, period=_period)
            st.plotly_chart(
                build_price_chart(hist_df, ticker=selected_ticker, company_name=row.get("name", "")),
                width="stretch",
            )


        with metrics_col:
            import math as _math

            def _fv(val, fmt=".2f", prefix="", suffix="", fallback="—"):
                if val is None or (isinstance(val, float) and _math.isnan(val)):
                    return fallback
                return f"{prefix}{float(val):{fmt}}{suffix}"

            dy = row.get("dividend_yield")
            dy_str = _fv(dy * 100 if dy else None, ".2f", suffix="%")

            cards = [
                ("F/K ORANI",    _fv(row.get("pe_ratio"),    ".1f"),               ""),
                ("F/DD ORANI",   _fv(row.get("pb_ratio"),    ".2f"),               ""),
                ("BETA",         _fv(row.get("beta"),        ".2f"),               ""),
                ("TEMETTÜ",      dy_str,                                            ""),
                ("ORT. HACİM",   _fv(row.get("avg_volume"),  ",.0f", suffix=" lot"), ""),
                ("HACİM TRENDİ", _fv(row.get("volume_ratio"), ".2f", suffix="x"),  "accent"),
                ("YIL. VOL.",    _fv(row.get("volatility"),  ".1f", suffix="%"),   ""),
            ]
            cards_html = "".join(
                f'<div class="mc-card">'
                f'<div class="mc-label">{lbl}</div>'
                f'<div class="mc-value {cls}">{val}</div>'
                f'</div>'
                for lbl, val, cls in cards
            )
            st.markdown(f'<div class="mc-grid">{cards_html}</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.plotly_chart(
                build_score_radar(
                    momentum   = row.get("momentum_score",   50),
                    valuation  = row.get("valuation_score",  50),
                    volume     = row.get("volume_score",     50),
                    volatility = row.get("volatility_score", 50),
                    ticker     = selected_ticker,
                ),
                width="stretch",
            )

            # ── Fiyat Performansı ─────────────────────────────────────────────
            st.markdown('<div class="sec-label" style="margin-top:0.5rem">Fiyat Performansı</div>', unsafe_allow_html=True)

            _PERF_MAP = {"1H": "1mo", "3H": "3mo", "6H": "6mo", "1Y": "1y"}
            _perf_label = st.radio(
                "Performans Periyodu",
                list(_PERF_MAP.keys()),
                index=3,
                horizontal=True,
                label_visibility="collapsed",
                key=f"perf_period_{selected_ticker}",
            )
            _perf_period = _PERF_MAP[_perf_label]

            with st.spinner("Yükleniyor…"):
                _perf_df = fetch_price_history(selected_ticker, period=_perf_period)

            if _perf_df is not None and not _perf_df.empty:
                _p_close  = _perf_df["Close"].dropna()
                _p_chg    = (_p_close.iloc[-1] - _p_close.iloc[0]) / _p_close.iloc[0] * 100
                _p_min    = float(_perf_df["Low"].min())
                _p_max    = float(_perf_df["High"].max())
                _chg_cls  = "green" if _p_chg >= 0 else "red"
                _chg_sign = "+" if _p_chg >= 0 else ""
                st.markdown(
                    f'<div class="mc-grid">'
                    f'  <div class="mc-card" style="grid-column:span 2">'
                    f'    <div class="mc-label">% Değişim ({_perf_label})</div>'
                    f'    <div class="mc-value {_chg_cls}">{_chg_sign}{_p_chg:.2f}%</div>'
                    f'  </div>'
                    f'  <div class="mc-card">'
                    f'    <div class="mc-label">Periyod Min</div>'
                    f'    <div class="mc-value">₺{_p_min:,.2f}</div>'
                    f'  </div>'
                    f'  <div class="mc-card">'
                    f'    <div class="mc-label">Periyod Max</div>'
                    f'    <div class="mc-value">₺{_p_max:,.2f}</div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Performans verisi alınamadı.")

        # ── AI Analysis ───────────────────────────────────────────────────────
        st.markdown(
            '<div class="sec-label" style="margin-top:1rem">Yapay Zeka Analizi · Groq / Llama 3.3 70B</div>',
            unsafe_allow_html=True,
        )

        # İki buton yan yana
        _ai_c1, _ai_c2, _ai_c3 = st.columns([2, 2, 3])
        with _ai_c1:
            run_short = st.button(
                "⚡ Kısa Dönem", key=f"btn_short_{selected_ticker}", width="stretch"
            )
        with _ai_c2:
            run_long = st.button(
                "📈 Uzun Dönem", key=f"btn_long_{selected_ticker}", width="stretch"
            )

        _short_key = f"ai_short_{selected_ticker}"
        _long_key  = f"ai_long_{selected_ticker}"

        # Yeni analiz isteklerinde önbelleği temizle
        if run_short:
            st.session_state.pop(_short_key, None)
        if run_long:
            st.session_state.pop(_long_key, None)

        # Analizleri çalıştır
        if run_short:
            with st.spinner("Kısa dönem analiz yapılıyor… (5-15 sn)"):
                st.session_state[_short_key] = analyze_short_term(row)
        if run_long:
            with st.spinner("Uzun dönem analiz yapılıyor… (5-15 sn)"):
                st.session_state[_long_key] = analyze_long_term(row)

        # Hiçbir analiz henüz yapılmadıysa yönlendirme mesajı
        if _short_key not in st.session_state and _long_key not in st.session_state:
            st.markdown(
                '<div style="font-family:var(--font-mono);font-size:0.8rem;'
                'color:var(--text-dim);padding:0.5rem 0">'
                '⚡ Kısa Dönem veya 📈 Uzun Dönem butonuna basarak analizi başlatın. '
                'Her iki analiz aynı anda görüntülenebilir.</div>',
                unsafe_allow_html=True,
            )

        def _render_ai_result(result: dict) -> None:
            """Tek bir analiz sonucunu (güçlü yönler / riskler / öneri) render eder."""
            if result.get("error") and result["error"] not in ("parse_failed",):
                err = result["error"]
                st.warning(
                    "GROQ_API_KEY ayarlanmamış." if err == "no_api_key"
                    else f"Analiz alınamadı: `{err}`",
                    icon="⚠",
                )
                return
            for section, css, title in [
                ("guclu_yonler", "",      "💪  GÜÇLÜ YÖNLER"),
                ("riskler",      "risk",  "⚠  RİSKLER"),
                ("oneri",        "oneri", "◆  ÖNERİ"),
            ]:
                text = result.get(section, "").strip()
                if text:
                    st.markdown(
                        f'<div class="ai-card {css}">'
                        f'<div class="ai-card-title">{title}</div>'
                        f'{text}</div>',
                        unsafe_allow_html=True,
                    )
            if result.get("error") == "parse_failed" and result.get("raw"):
                with st.expander("Ham model çıktısı"):
                    st.text(result["raw"])

        # Kısa dönem sonucu
        if _short_key in st.session_state:
            with st.expander("⚡ Kısa Dönem Analizi — 1-4 Hafta Perspektifi", expanded=True):
                st.markdown(
                    '<div style="font-family:var(--font-mono);font-size:0.7rem;'
                    'color:var(--text-dim);margin-bottom:0.75rem;letter-spacing:0.05em">'
                    'Odak: Momentum · Hacim Trendi · SMA20 Pozisyonu · Kısa Vadeli Volatilite</div>',
                    unsafe_allow_html=True,
                )
                _render_ai_result(st.session_state[_short_key])

        # Uzun dönem sonucu
        if _long_key in st.session_state:
            with st.expander("📈 Uzun Dönem Analizi — 6-12 Ay Perspektifi", expanded=True):
                st.markdown(
                    '<div style="font-family:var(--font-mono);font-size:0.7rem;'
                    'color:var(--text-dim);margin-bottom:0.75rem;letter-spacing:0.05em">'
                    'Odak: F/K · F/DD · Temettü · Beta · Sektör Pozisyonu · Piyasa Değeri</div>',
                    unsafe_allow_html=True,
                )
                _render_ai_result(st.session_state[_long_key])

with _tab_backtest:
    render_backtest_tab(all_tickers_sorted, default_ticker=selected_ticker)


# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown(
    '<div class="trm-footer">'
    'BIST RADAR &nbsp;·&nbsp; Veriler Yahoo Finance üzerinden alınmaktadır &nbsp;·&nbsp; '
    'Bu araç yatırım tavsiyesi vermez. Tüm yatırım kararları yatırımcının sorumluluğundadır.'
    '</div>',
    unsafe_allow_html=True,
)
