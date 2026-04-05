"""
BIST Radar 📡 — Turkish Stock Market Screener
app.py — Main Streamlit entry point (Phase 3: sidebar + table + detail view)
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="BIST Radar 📡",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from data.bist_tickers import ALL_SECTORS, TICKER_SYMBOLS
from modules.data_fetcher import (
    fetch_all_tickers,
    fetch_price_history,
)
from modules.screener import (
    apply_filters,
    build_display_df,
    score_dataframe,
    SIGNAL_AL,
    SIGNAL_BEKLE,
    SIGNAL_SAT,
)
from modules.charts import build_price_chart, build_52w_range_chart, build_score_radar
from modules.analyzer import analyze_stock

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ── Boot-time validation ──────────────────────────────────────────────────────

def _check_env() -> None:
    """Warn once per session about missing or placeholder credentials."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key or groq_key == "your_groq_api_key_here":
        st.warning(
            "**GROQ_API_KEY** tanımlanmamış veya varsayılan değerde. "
            "`.env` dosyanıza gerçek anahtarınızı ekleyin; "
            "AI analizi bu olmadan çalışmaz.",
            icon="🔑",
        )

_check_env()


# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Sidebar header */
    .sidebar-title  { font-size: 1.3rem; font-weight: 700; color: #00C896; }
    .sidebar-desc   { font-size: 0.82rem; color: #9ca3af; margin-top: -0.4rem; }

    /* Metric cards row */
    div[data-testid="metric-container"] {
        background: #1A1D27;
        border: 1px solid #2d3142;
        border-radius: 10px;
        padding: 0.6rem 1rem;
    }
    div[data-testid="metric-container"] label { color: #9ca3af !important; font-size: 0.78rem; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #f9fafb !important; font-size: 1.45rem;
    }

    /* Table tweaks */
    thead tr th { background-color: #1A1D27 !important; }
    .stDataFrame { border: 1px solid #2d3142; border-radius: 8px; }

    /* Section dividers */
    hr { border-color: #2d3142; }

    /* Detail view metric cards */
    .metric-card {
        background: #1A1D27;
        border: 1px solid #2d3142;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        text-align: center;
    }
    .metric-card .label { font-size: 0.72rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-card .value { font-size: 1.25rem; font-weight: 600; color: #f9fafb; margin-top: 2px; }
    .metric-card .value.green  { color: #00C896; }
    .metric-card .value.red    { color: #ff4d4d; }
    .metric-card .value.yellow { color: #d4c84a; }

    /* AI analysis sections */
    .ai-section {
        background: #1A1D27;
        border-left: 3px solid #00C896;
        border-radius: 0 8px 8px 0;
        padding: 0.85rem 1.1rem;
        margin-bottom: 0.75rem;
        font-size: 0.92rem;
        line-height: 1.6;
        color: #e5e7eb;
    }
    .ai-section.risk   { border-left-color: #ff4d4d; }
    .ai-section.oneri  { border-left-color: #d4c84a; }
    .ai-section-title  { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em;
                         text-transform: uppercase; margin-bottom: 0.4rem; color: #00C896; }
    .ai-section.risk  .ai-section-title  { color: #ff4d4d; }
    .ai-section.oneri .ai-section-title  { color: #d4c84a; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<p class="sidebar-title">📡 BIST Radar</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sidebar-desc">Türk borsası tarama ve analiz aracı</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Sector filter
    st.subheader("🏭 Sektör")
    selected_sectors: list[str] = st.multiselect(
        "Sektör seçin (boş = hepsi)",
        options=ALL_SECTORS,
        default=[],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Market cap filter
    st.subheader("💰 Piyasa Değeri")
    MCAP_OPTIONS = {
        "Tümü":           (0, None),
        "> ₺10 Milyar":   (10_000_000_000, None),
        "> ₺50 Milyar":   (50_000_000_000, None),
        "> ₺100 Milyar":  (100_000_000_000, None),
        "> ₺500 Milyar":  (500_000_000_000, None),
    }
    mcap_choice = st.selectbox(
        "Minimum piyasa değeri",
        options=list(MCAP_OPTIONS.keys()),
        index=0,
        label_visibility="collapsed",
    )
    mcap_min, mcap_max = MCAP_OPTIONS[mcap_choice]

    st.markdown("---")

    # P/E filter
    st.subheader("📊 F/K Oranı")
    pe_filter_on = st.checkbox("F/K filtresi uygula", value=False)
    pe_min: float | None = None
    pe_max: float | None = None
    if pe_filter_on:
        pe_range = st.slider(
            "F/K aralığı",
            min_value=0.0,
            max_value=100.0,
            value=(0.0, 40.0),
            step=0.5,
            label_visibility="collapsed",
        )
        pe_min, pe_max = float(pe_range[0]), float(pe_range[1])

    st.markdown("---")

    # 52-week return filter
    st.subheader("📈 52H Getiri")
    min_52w = st.slider(
        "Minimum 52 haftalık getiri (%)",
        min_value=-100,
        max_value=500,
        value=-100,
        step=5,
        label_visibility="collapsed",
    )
    min_52w_return: float | None = None if min_52w == -100 else float(min_52w)

    st.markdown("---")

    # Volume filter
    st.subheader("📦 Hacim")
    VOL_OPTIONS = {
        "Tümü":             0,
        "> 1M adet/gün":    1_000_000,
        "> 5M adet/gün":    5_000_000,
        "> 10M adet/gün":   10_000_000,
        "> 50M adet/gün":   50_000_000,
    }
    vol_choice = st.selectbox(
        "Minimum ortalama günlük hacim",
        options=list(VOL_OPTIONS.keys()),
        index=0,
        label_visibility="collapsed",
    )
    min_avg_volume: float | None = VOL_OPTIONS[vol_choice] or None

    st.markdown("---")

    # Signal quick-filter
    st.subheader("🚦 Sinyal")
    show_al    = st.checkbox("🟢 AL",    value=True)
    show_bekle = st.checkbox("🟡 BEKLE", value=True)
    show_sat   = st.checkbox("🔴 SAT",   value=True)

    st.markdown("---")

    refresh = st.button("🔄 Verileri Yenile", use_container_width=True)
    if refresh:
        st.cache_data.clear()
        st.rerun()

    st.caption(f"Toplam {len(TICKER_SYMBOLS)} hisse · Veri: yfinance")


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_enriched_data(tickers: tuple[str, ...]) -> pd.DataFrame:
    """
    Thin wrapper around fetch_all_tickers kept for caching isolation.
    volume_ratio and volatility are now computed inside the bulk OHLCV
    download path — no per-ticker secondary calls needed.
    """
    return fetch_all_tickers(tickers)


# ── Main page ─────────────────────────────────────────────────────────────────

st.title("BIST Radar 📡")
st.caption("Türk borsası hisse tarama ve skorlama platformu")

with st.spinner("Piyasa verileri yükleniyor…"):
    raw_df = load_enriched_data(tuple(TICKER_SYMBOLS))

if raw_df.empty:
    st.error(
        "Hiçbir hisse için veri alınamadı. Olası nedenler:\n"
        "- İnternet bağlantısı yok\n"
        "- yfinance API geçici olarak erişilemiyor\n"
        "- Tüm semboller geçersiz\n\n"
        "Sayfayı yenilemek için sol menüdeki **🔄 Verileri Yenile** butonunu kullanın."
    )
    st.stop()

# Surface any tickers that silently returned no data
_failed = st.session_state.get("fetch_failed", [])
if _failed:
    with st.expander(f"⚠️ {len(_failed)} hisse yüklenemedi", expanded=False):
        st.caption(
            "Bu semboller için yfinance'tan veri alınamadı ve tabloya dahil edilmedi:"
        )
        st.code(", ".join(_failed))

# Score all tickers before filtering (scoring needs full peer groups)
try:
    scored_df = score_dataframe(raw_df)
except Exception as _score_err:
    logger.error("Scoring failed: %s", _score_err)
    st.error(f"Skorlama sırasında hata oluştu: {_score_err}")
    st.stop()

# Apply sidebar filters
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

# Apply signal quick-filter
wanted_signals = []
if show_al:    wanted_signals.append(SIGNAL_AL)
if show_bekle: wanted_signals.append(SIGNAL_BEKLE)
if show_sat:   wanted_signals.append(SIGNAL_SAT)

if "signal" in filtered_df.columns and wanted_signals:
    filtered_df = filtered_df[filtered_df["signal"].isin(wanted_signals)]


# ── KPI summary row ───────────────────────────────────────────────────────────

total        = len(filtered_df)
count_al     = (filtered_df["signal"] == SIGNAL_AL).sum()    if "signal" in filtered_df.columns else 0
count_bekle  = (filtered_df["signal"] == SIGNAL_BEKLE).sum() if "signal" in filtered_df.columns else 0
count_sat    = (filtered_df["signal"] == SIGNAL_SAT).sum()   if "signal" in filtered_df.columns else 0

avg_return = (
    filtered_df["52w_return"].dropna().mean()
    if "52w_return" in filtered_df.columns and not filtered_df.empty
    else None
)
avg_score = (
    filtered_df["total_score"].dropna().mean()
    if "total_score" in filtered_df.columns and not filtered_df.empty
    else None
)

col1, col2, col3, col4, col5, col6 = st.columns(6)

col1.metric("Hisse Sayısı",   total)
col2.metric("🟢 AL",          count_al)
col3.metric("🟡 BEKLE",       count_bekle)
col4.metric("🔴 SAT",         count_sat)
col5.metric(
    "Ort. 52H Getiri",
    f"{avg_return:.1f}%" if avg_return is not None else "—",
    delta=None,
)
col6.metric(
    "Ort. Skor",
    f"{avg_score:.1f}" if avg_score is not None else "—",
)

st.markdown("---")


# ── Sector breakdown mini-chart ───────────────────────────────────────────────

if not filtered_df.empty and "sector" in filtered_df.columns:
    with st.expander("📊 Sektör Dağılımı", expanded=False):
        sector_counts = (
            filtered_df.groupby("sector")["signal"]
            .value_counts()
            .unstack(fill_value=0)
        )
        # Ensure all signal columns exist
        for sig in [SIGNAL_AL, SIGNAL_BEKLE, SIGNAL_SAT]:
            if sig not in sector_counts.columns:
                sector_counts[sig] = 0

        sector_counts = sector_counts[[SIGNAL_AL, SIGNAL_BEKLE, SIGNAL_SAT]]
        sector_counts.columns = ["AL", "BEKLE", "SAT"]

        import plotly.graph_objects as go

        fig = go.Figure()
        color_map = {"AL": "#00C896", "BEKLE": "#d4c84a", "SAT": "#ff4d4d"}
        for sig_label, color in color_map.items():
            fig.add_trace(go.Bar(
                name=sig_label,
                x=sector_counts.index.tolist(),
                y=sector_counts[sig_label].tolist(),
                marker_color=color,
            ))

        fig.update_layout(
            barmode="stack",
            plot_bgcolor="#0E1117",
            paper_bgcolor="#0E1117",
            font_color="#f9fafb",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=30, b=0),
            height=280,
            xaxis=dict(gridcolor="#2d3142"),
            yaxis=dict(gridcolor="#2d3142", title="Hisse Sayısı"),
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Stock table ───────────────────────────────────────────────────────────────

st.subheader(f"Hisse Listesi ({total} sonuç)")

if filtered_df.empty:
    st.warning("Seçili filtrelere uyan hisse bulunamadı. Filtreleri genişletin.")
else:
    # Sort controls
    sort_col_label, sort_dir_label = st.columns([3, 1])

    SORT_OPTIONS = {
        "Skor (yüksek → düşük)":     ("total_score", False),
        "52H Getiri (yüksek → düşük)":("52w_return",  False),
        "52H Getiri (düşük → yüksek)":("52w_return",  True),
        "F/K (düşük → yüksek)":       ("pe_ratio",    True),
        "F/K (yüksek → düşük)":       ("pe_ratio",    False),
        "Piyasa Değeri (büyük → küçük)":("market_cap", False),
        "Fiyat (yüksek → düşük)":     ("price",       False),
    }

    with sort_col_label:
        sort_choice = st.selectbox(
            "Sıralama",
            options=list(SORT_OPTIONS.keys()),
            index=0,
        )

    sort_column, sort_asc = SORT_OPTIONS[sort_choice]

    if sort_column in filtered_df.columns:
        sorted_df = filtered_df.sort_values(
            by=sort_column,
            ascending=sort_asc,
            na_position="last",
        )
    else:
        sorted_df = filtered_df

    display_df = build_display_df(sorted_df)

    # Reset index so ticker appears as a column in the table
    display_df.insert(0, "Ticker", sorted_df.index)
    display_df = display_df.reset_index(drop=True)

    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(600, 55 + len(display_df) * 35),
        column_config={
            "Ticker":        st.column_config.TextColumn("Ticker", width="small"),
            "Şirket":        st.column_config.TextColumn("Şirket", width="medium"),
            "Sektör":        st.column_config.TextColumn("Sektör", width="small"),
            "Fiyat (₺)":     st.column_config.NumberColumn("Fiyat (₺)", format="₺%.2f"),
            "F/K":           st.column_config.NumberColumn("F/K", format="%.1f"),
            "Piyasa Değeri": st.column_config.TextColumn("Piyasa Değeri", width="medium"),
            "52H Getiri %":  st.column_config.NumberColumn("52H Getiri %", format="%.2f%%"),
            "Skor":          st.column_config.ProgressColumn(
                                 "Skor", min_value=0, max_value=100, format="%.1f"
                             ),
            "Sinyal":        st.column_config.TextColumn("Sinyal", width="small"),
        },
        hide_index=True,
    )

    # ── Download button ───────────────────────────────────────────────────────
    csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ CSV İndir",
        data=csv_data,
        file_name="bist_radar_sonuclar.csv",
        mime="text/csv",
    )


# ── Detail view ───────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("🔍 Hisse Detay Görünümü")

# Stock selector — always draw from the full scored universe so user can look
# up any ticker even if filters hide it from the table.
all_tickers_sorted = sorted(scored_df.index.tolist())
ticker_labels      = {
    t: f"{t}  —  {scored_df.loc[t, 'name']}" if "name" in scored_df.columns else t
    for t in all_tickers_sorted
}

# Pre-select first ticker in filtered list if table is non-empty
default_ticker = (
    filtered_df.index[0]
    if not filtered_df.empty
    else (all_tickers_sorted[0] if all_tickers_sorted else None)
)
default_idx = all_tickers_sorted.index(default_ticker) if default_ticker in all_tickers_sorted else 0

selected_ticker: str = st.selectbox(
    "Hisse seçin",
    options=all_tickers_sorted,
    index=default_idx,
    format_func=lambda t: ticker_labels.get(t, t),
)

if selected_ticker:
    row = scored_df.loc[selected_ticker].to_dict()
    row["ticker"] = selected_ticker

    # ── Header strip ─────────────────────────────────────────────────────────
    signal_val  = row.get("signal", "—")
    price_val   = row.get("price")
    prev_close  = row.get("prev_close")
    day_chg     = ((price_val - prev_close) / prev_close * 100) if price_val and prev_close and prev_close != 0 else None

    h_left, h_mid, h_right = st.columns([3, 2, 1])
    with h_left:
        st.markdown(
            f"### {row.get('name', selected_ticker)} &nbsp; "
            f"<span style='color:#9ca3af;font-size:0.9rem'>{selected_ticker} · {row.get('sector','')}</span>",
            unsafe_allow_html=True,
        )
    with h_mid:
        price_str = f"₺{price_val:,.2f}" if price_val else "—"
        delta_str = f"{day_chg:+.2f}% bugün" if day_chg is not None else None
        st.metric("Güncel Fiyat", price_str, delta=delta_str)
    with h_right:
        signal_color = {"🟢": "#00C896", "🟡": "#d4c84a", "🔴": "#ff4d4d"}.get(signal_val[0], "#9ca3af")
        st.markdown(
            f"<div style='text-align:right;font-size:1.8rem;margin-top:0.3rem'>{signal_val}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Two-column layout: chart left, metrics right ──────────────────────────
    chart_col, metrics_col = st.columns([2, 1], gap="large")

    with chart_col:
        with st.spinner("Fiyat grafiği yükleniyor…"):
            hist_df = fetch_price_history(selected_ticker, period="6mo")

        fig_price = build_price_chart(
            hist_df,
            ticker=selected_ticker,
            company_name=row.get("name", ""),
        )
        st.plotly_chart(fig_price, use_container_width=True)

        # 52-week range bar
        fig_range = build_52w_range_chart(
            current=row.get("price"),
            low_52w=row.get("52w_low"),
            high_52w=row.get("52w_high"),
            ticker=selected_ticker,
        )
        st.plotly_chart(fig_range, use_container_width=True)

    with metrics_col:
        # ── Key metrics cards ─────────────────────────────────────────────────
        def _mc(label: str, value: str, css_class: str = "") -> str:
            return (
                f'<div class="metric-card">'
                f'<div class="label">{label}</div>'
                f'<div class="value {css_class}">{value}</div>'
                f'</div>'
            )

        def _fv(val, fmt=".2f", prefix="", suffix="", fallback="—"):
            if val is None or (isinstance(val, float) and __import__("math").isnan(val)):
                return fallback
            return f"{prefix}{float(val):{fmt}}{suffix}"

        w52_ret = row.get("52w_return")
        ret_class = "green" if (w52_ret or 0) > 0 else "red"

        mc_html = "".join([
            _mc("F/K Oranı",     _fv(row.get("pe_ratio"),  ".1f")),
            _mc("F/DD Oranı",    _fv(row.get("pb_ratio"),  ".2f")),
            _mc("Beta",          _fv(row.get("beta"),       ".2f")),
            _mc("52H Getiri",    _fv(w52_ret, ".1f", suffix="%"), ret_class),
            _mc("Temettü",       _fv(
                row.get("dividend_yield", 0) * 100 if row.get("dividend_yield") else None,
                ".2f", suffix="%"
            )),
            _mc("Ort. Hacim",    _fv(row.get("avg_volume"), ",.0f", suffix=" adet")),
            _mc("Hacim Trendi",  _fv(row.get("volume_ratio"), ".2f", suffix="x")),
            _mc("Yıl. Volatilite", _fv(row.get("volatility"), ".1f", suffix="%")),
        ])

        # 2-column grid for the metric cards
        st.markdown(
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">{mc_html}</div>',
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Score radar chart ─────────────────────────────────────────────────
        fig_radar = build_score_radar(
            momentum   = row.get("momentum_score",   50),
            valuation  = row.get("valuation_score",  50),
            volume     = row.get("volume_score",     50),
            volatility = row.get("volatility_score", 50),
            ticker     = selected_ticker,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # ── AI Analysis ───────────────────────────────────────────────────────────
    st.markdown("---")

    with st.expander("🤖 Yapay Zeka Analizi (Groq · Llama 3.3 70B)", expanded=True):
        ai_col1, ai_col2 = st.columns([5, 1])
        with ai_col2:
            run_analysis = st.button("Analizi Çalıştır ▶", use_container_width=True)

        # Keep analysis in session state so it survives re-runs caused by
        # other widgets, but re-runs fresh when user explicitly clicks the button
        # or switches to a different ticker.
        state_key = f"ai_analysis_{selected_ticker}"

        if run_analysis:
            # Clear any stale result for this ticker before re-running
            st.session_state.pop(state_key, None)

        if state_key not in st.session_state:
            if run_analysis:
                with st.spinner("Yapay zeka analiz ediyor… (5-15 saniye)"):
                    result = analyze_stock(row)
                st.session_state[state_key] = result
            else:
                st.info(
                    "Yukarıdaki **Analizi Çalıştır** butonuna basarak "
                    "bu hisse için Groq AI analizi başlatın.",
                    icon="💡",
                )

        if state_key in st.session_state:
            result = st.session_state[state_key]

            if result.get("error") and result["error"] not in ("parse_failed",):
                err = result["error"]
                if err == "no_api_key":
                    st.warning(
                        "GROQ_API_KEY ayarlanmamış. `.env` dosyanıza anahtarınızı ekleyin.",
                        icon="🔑",
                    )
                else:
                    st.warning(f"Analiz alınamadı: `{err}`", icon="⚠️")
            else:
                guclu  = result.get("guclu_yonler", "").strip()
                riskler = result.get("riskler", "").strip()
                oneri  = result.get("oneri", "").strip()

                if guclu:
                    st.markdown(
                        f'<div class="ai-section">'
                        f'<div class="ai-section-title">💪 Güçlü Yönler</div>'
                        f'{guclu}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                if riskler:
                    st.markdown(
                        f'<div class="ai-section risk">'
                        f'<div class="ai-section-title">⚠️ Riskler</div>'
                        f'{riskler}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                if oneri:
                    st.markdown(
                        f'<div class="ai-section oneri">'
                        f'<div class="ai-section-title">📋 Öneri</div>'
                        f'{oneri}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # Show raw response in debug expander
                if result.get("error") == "parse_failed" and result.get("raw"):
                    with st.expander("⚙️ Ham model çıktısı"):
                        st.text(result["raw"])


# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption(
    "BIST Radar · Veriler yfinance üzerinden alınmaktadır · "
    "Bu araç yatırım tavsiyesi vermez. "
    "Tüm yatırım kararları yatırımcının sorumluluğundadır."
)
