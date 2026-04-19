"""
backtest.py — MA Crossover Backtest with XU100 Benchmark
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from modules.data_fetcher import _fetch_chart, _chart_to_ohlcv

BENCHMARK_TICKER = "XU100.IS"

_BG     = "#0C1B2E"
_GRID   = "#1A3350"
_TEXT   = "#7A9BB8"
_FONT   = "Space Grotesk, Inter, sans-serif"
_GREEN  = "#00E676"
_ACCENT = "#00D4AA"
_YELLOW = "#FFD600"
_RED    = "#FF4444"


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_ohlcv(ticker: str, period: str = "5y") -> pd.DataFrame | None:
    result = _fetch_chart(ticker, range_=period, interval="1d")
    if result is None:
        return None
    return _chart_to_ohlcv(result, ticker)


def _ma_crossover_signals(close: pd.Series, fast: int, slow: int) -> pd.Series:
    ma_fast = close.rolling(fast).mean()
    ma_slow = close.rolling(slow).mean()
    # shift(1) to avoid look-ahead bias
    return (ma_fast > ma_slow).astype(int).shift(1).fillna(0)


def _portfolio_stats(returns: pd.Series) -> dict:
    equity   = (1 + returns).cumprod()
    n_days   = len(returns)
    total    = float(equity.iloc[-1] - 1)
    cagr     = float(equity.iloc[-1] ** (252 / n_days) - 1) if n_days > 1 else 0.0
    ann_vol  = float(returns.std() * np.sqrt(252))
    sharpe   = float(cagr / ann_vol) if ann_vol > 0 else 0.0
    peak     = equity.cummax()
    drawdown = (equity - peak) / peak
    max_dd   = float(drawdown.min())
    return {
        "total_return":    total,
        "cagr":            cagr,
        "sharpe":          sharpe,
        "max_drawdown":    max_dd,
        "ann_volatility":  ann_vol,
        "equity":          equity,
        "drawdown":        drawdown,
    }


def run_backtest(
    ticker: str,
    period: str = "5y",
    fast_ma: int = 50,
    slow_ma: int = 200,
) -> dict:
    stock_df = _fetch_ohlcv(ticker, period)
    bm_df    = _fetch_ohlcv(BENCHMARK_TICKER, period)

    if stock_df is None or stock_df.empty:
        return {"error": f"{ticker} için veri alınamadı."}

    close = stock_df["Close"].dropna()

    if len(close) < slow_ma + 10:
        return {"error": f"Yeterli veri yok (en az {slow_ma + 10} gün gerekli)."}

    position        = _ma_crossover_signals(close, fast_ma, slow_ma)
    daily_ret       = close.pct_change().fillna(0)
    strategy_ret    = daily_ret * position
    bh_ret          = daily_ret

    if bm_df is not None and not bm_df.empty:
        bm_close = bm_df["Close"].dropna().reindex(close.index, method="ffill")
        bm_ret   = bm_close.pct_change().fillna(0)
    else:
        bm_ret = None

    signal_changes = position.diff().fillna(0)
    buy_dates  = close.index[signal_changes == 1].tolist()
    sell_dates = close.index[signal_changes == -1].tolist()

    return {
        "ticker":    ticker,
        "period":    period,
        "fast_ma":   fast_ma,
        "slow_ma":   slow_ma,
        "close":     close,
        "ma_fast":   close.rolling(fast_ma).mean(),
        "ma_slow":   close.rolling(slow_ma).mean(),
        "position":  position,
        "strategy":  _portfolio_stats(strategy_ret),
        "buy_hold":  _portfolio_stats(bh_ret),
        "benchmark": _portfolio_stats(bm_ret) if bm_ret is not None else None,
        "buy_dates":  buy_dates,
        "sell_dates": sell_dates,
        "n_trades":   len(buy_dates),
        "error":      None,
    }


def build_equity_chart(results: dict) -> go.Figure:
    close  = results["close"]
    ma_f   = results["ma_fast"]
    ma_s   = results["ma_slow"]
    ticker = results["ticker"]

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.42, 0.33, 0.25],
        vertical_spacing=0.04,
        subplot_titles=(
            "Fiyat & Hareketli Ortalamalar",
            "Portföy Değeri (Eşit Başlangıç = 1.00)",
            "Drawdown (%)",
        ),
    )

    # ── Row 1: Price + MAs ────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=close.index, y=close.values,
        name="Fiyat", line=dict(color=_TEXT, width=1),
        hovertemplate="%{x|%d.%m.%Y}<br>₺%{y:.2f}<extra></extra>",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=ma_f.index, y=ma_f.values,
        name=f"MA{results['fast_ma']}", line=dict(color=_ACCENT, width=1.5),
        hovertemplate=f"MA{results['fast_ma']}: ₺%{{y:.2f}}<extra></extra>",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=ma_s.index, y=ma_s.values,
        name=f"MA{results['slow_ma']}", line=dict(color=_YELLOW, width=1.5),
        hovertemplate=f"MA{results['slow_ma']}: ₺%{{y:.2f}}<extra></extra>",
    ), row=1, col=1)

    if results["buy_dates"]:
        bp = close.reindex(results["buy_dates"]).dropna()
        fig.add_trace(go.Scatter(
            x=bp.index, y=bp.values, mode="markers", name="AL",
            marker=dict(color=_GREEN, symbol="triangle-up", size=10),
            hovertemplate="AL · %{x|%d.%m.%Y}<br>₺%{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if results["sell_dates"]:
        sp = close.reindex(results["sell_dates"]).dropna()
        fig.add_trace(go.Scatter(
            x=sp.index, y=sp.values, mode="markers", name="SAT",
            marker=dict(color=_RED, symbol="triangle-down", size=10),
            hovertemplate="SAT · %{x|%d.%m.%Y}<br>₺%{y:.2f}<extra></extra>",
        ), row=1, col=1)

    # ── Row 2: Equity curves ──────────────────────────────────────────────────
    strat_eq = results["strategy"]["equity"]
    bh_eq    = results["buy_hold"]["equity"]

    fig.add_trace(go.Scatter(
        x=strat_eq.index, y=strat_eq.values,
        name=f"MA Stratejisi ({ticker})", line=dict(color=_ACCENT, width=2),
        hovertemplate="Strateji: %{y:.3f}<extra></extra>",
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=bh_eq.index, y=bh_eq.values,
        name=f"Al & Tut ({ticker})", line=dict(color=_GREEN, width=1.5, dash="dot"),
        hovertemplate="Al & Tut: %{y:.3f}<extra></extra>",
    ), row=2, col=1)

    if results["benchmark"] is not None:
        bm_eq = results["benchmark"]["equity"]
        fig.add_trace(go.Scatter(
            x=bm_eq.index, y=bm_eq.values,
            name="XU100 (Benchmark)", line=dict(color=_YELLOW, width=1.5, dash="dash"),
            hovertemplate="XU100: %{y:.3f}<extra></extra>",
        ), row=2, col=1)

    # Reference line at 1.0
    fig.add_hline(y=1.0, line=dict(color=_GRID, width=1, dash="dot"), row=2, col=1)

    # ── Row 3: Drawdown ───────────────────────────────────────────────────────
    dd = results["strategy"]["drawdown"] * 100
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        name="Drawdown", fill="tozeroy",
        fillcolor="rgba(255,68,68,0.12)",
        line=dict(color=_RED, width=1),
        hovertemplate="DD: %{y:.1f}%<extra></extra>",
    ), row=3, col=1)

    # ── Layout ────────────────────────────────────────────────────────────────
    axis = dict(
        gridcolor=_GRID, gridwidth=1,
        zeroline=False, showline=False,
        tickfont=dict(family=_FONT, color=_TEXT, size=10),
    )
    fig.update_layout(
        plot_bgcolor=_BG, paper_bgcolor=_BG,
        font=dict(family=_FONT, color=_TEXT, size=11),
        height=740,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)", font=dict(size=10),
        ),
        margin=dict(l=0, r=0, t=60, b=0),
        hovermode="x unified",
    )
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    fig.update_annotations(font=dict(family=_FONT, color=_TEXT, size=11))

    return fig


def render_backtest_tab(all_tickers: list[str], default_ticker: str | None = None) -> None:
    st.markdown('<div class="sec-label">MA Crossover Backtest · 50/200 Gün</div>', unsafe_allow_html=True)

    c_ticker, c_period, c_btn = st.columns([3, 2, 1])

    with c_ticker:
        idx = all_tickers.index(default_ticker) if default_ticker in all_tickers else 0
        bt_ticker = st.selectbox(
            "Hisse", all_tickers, index=idx,
            key="bt_ticker", label_visibility="collapsed",
        )

    with c_period:
        period_map = {"1 Yıl": "1y", "2 Yıl": "2y", "5 Yıl": "5y"}
        bt_period_label = st.selectbox(
            "Periyot", list(period_map.keys()), index=2,
            key="bt_period", label_visibility="collapsed",
        )
        bt_period = period_map[bt_period_label]

    with c_btn:
        run_bt = st.button("▶  BACKTEST", width="stretch", key="run_bt")

    bt_key = f"bt_{bt_ticker}_{bt_period}"

    if run_bt:
        st.session_state.pop(bt_key, None)

    if bt_key not in st.session_state:
        if not run_bt:
            st.markdown(
                '<div style="font-family:var(--font-mono);font-size:0.8rem;color:var(--text-dim);'
                'padding:2rem 0;text-align:center">'
                'Hisse ve periyot seçip ▶ BACKTEST butonuna basın.</div>',
                unsafe_allow_html=True,
            )
            return
        with st.spinner(f"{bt_ticker} için backtest çalışıyor…"):
            results = run_backtest(bt_ticker, period=bt_period)
        st.session_state[bt_key] = results

    results = st.session_state.get(bt_key)
    if results is None:
        return

    if results.get("error"):
        st.error(results["error"])
        return

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    def _fmt(v, fmt=".1f", suffix="", fallback="—"):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return fallback
        return f"{v:{fmt}}{suffix}"

    strat   = results["strategy"]
    bh      = results["buy_hold"]
    bm      = results.get("benchmark")

    s_ret   = strat["total_return"] * 100
    bh_ret  = bh["total_return"] * 100
    bm_ret  = (bm["total_return"] * 100) if bm else None

    rc  = "green" if s_ret >= 0 else "red"
    ddc = "red"    if strat["max_drawdown"] < -0.2 else ("yellow" if strat["max_drawdown"] < -0.1 else "accent")
    shc = "green"  if strat["sharpe"] >= 1.0 else ("yellow" if strat["sharpe"] >= 0.5 else "red")
    bhc = "green"  if bh_ret >= 0 else "red"

    bm_str  = _fmt(bm_ret, "+.1f", "%") if bm_ret is not None else "—"
    bm_col  = ("green" if (bm_ret or 0) >= 0 else "red") if bm_ret is not None else ""

    st.markdown(
        f'<div class="kpi-grid" style="grid-template-columns:repeat(5,1fr)">'
        f'  <div class="kpi-card {rc}">'
        f'    <div class="kpi-label">Strateji Toplam Getiri</div>'
        f'    <div class="kpi-value {rc}">{_fmt(s_ret, "+.1f", "%")}</div>'
        f'  </div>'
        f'  <div class="kpi-card {bhc}">'
        f'    <div class="kpi-label">Al &amp; Tut Getiri</div>'
        f'    <div class="kpi-value {bhc}">{_fmt(bh_ret, "+.1f", "%")}</div>'
        f'  </div>'
        f'  <div class="kpi-card {bm_col}">'
        f'    <div class="kpi-label">XU100 Getiri</div>'
        f'    <div class="kpi-value {bm_col}">{bm_str}</div>'
        f'  </div>'
        f'  <div class="kpi-card {shc}">'
        f'    <div class="kpi-label">Sharpe Oranı</div>'
        f'    <div class="kpi-value {shc}">{_fmt(strat["sharpe"], ".2f")}</div>'
        f'  </div>'
        f'  <div class="kpi-card {ddc}">'
        f'    <div class="kpi-label">Max Drawdown</div>'
        f'    <div class="kpi-value {ddc}">{_fmt(strat["max_drawdown"] * 100, ".1f", "%")}</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("CAGR (Strateji)",   f"{strat['cagr'] * 100:+.1f}%")
    m2.metric("Yıllık Volatilite", f"{strat['ann_volatility'] * 100:.1f}%")
    m3.metric("İşlem Sayısı",      str(results["n_trades"]))
    m4.metric("CAGR (Al & Tut)",   f"{bh['cagr'] * 100:+.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    st.plotly_chart(build_equity_chart(results), use_container_width=True)

    st.markdown(
        f'<div style="font-family:var(--font-mono);font-size:0.7rem;color:var(--text-dim);'
        f'padding:0.4rem 0;letter-spacing:0.05em">'
        f'Strateji: MA{results["fast_ma"]} &gt; MA{results["slow_ma"]} → AL &nbsp;|&nbsp; '
        f'MA{results["fast_ma"]} &lt; MA{results["slow_ma"]} → SAT &nbsp;|&nbsp; '
        f'Periyot: {bt_period_label} &nbsp;|&nbsp; Benchmark: XU100.IS (Yahoo Finance) &nbsp;|&nbsp; '
        f'Bu araç yatırım tavsiyesi vermez.</div>',
        unsafe_allow_html=True,
    )
