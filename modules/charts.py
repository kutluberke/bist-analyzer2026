"""
charts.py — Plotly chart builders for the BIST Radar detail view.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Shared theme ──────────────────────────────────────────────────────────────

_DARK_BG   = "#0E1117"
_PANEL_BG  = "#1A1D27"
_GRID      = "#2d3142"
_TEXT      = "#f9fafb"
_GREEN     = "#00C896"
_RED       = "#ff4d4d"
_YELLOW    = "#d4c84a"
_VOLUME_UP = "#00C896"
_VOLUME_DN = "#ff4d4d"

_LAYOUT_BASE = dict(
    plot_bgcolor=_DARK_BG,
    paper_bgcolor=_PANEL_BG,
    font=dict(color=_TEXT, family="Inter, sans-serif", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
    hovermode="x unified",
)


# ── Candlestick + Volume (combined subplot) ───────────────────────────────────

def build_price_chart(
    df: pd.DataFrame,
    ticker: str,
    company_name: str = "",
) -> go.Figure:
    """
    Return a two-panel Plotly figure:
      - Top (70%): candlestick with 20-day and 50-day SMA overlays
      - Bottom (30%): volume bars coloured green/red by price direction

    Parameters
    ----------
    df          : OHLCV DataFrame from data_fetcher.fetch_price_history()
    ticker      : e.g. "THYAO.IS"
    company_name: display name for the chart title
    """
    if df is None or df.empty:
        return _empty_chart("Fiyat verisi bulunamadı")

    df = df.copy()
    df.index = pd.to_datetime(df.index)

    # ── Moving averages ───────────────────────────────────────────────────────
    df["sma20"] = df["Close"].rolling(20).mean()
    df["sma50"] = df["Close"].rolling(50).mean()

    # ── Volume colour: green if close >= open, red otherwise ─────────────────
    vol_colors = [
        _VOLUME_UP if float(row["Close"]) >= float(row["Open"]) else _VOLUME_DN
        for _, row in df.iterrows()
    ]

    dates  = df.index.tolist()
    title  = f"{company_name} ({ticker})" if company_name else ticker

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.70, 0.30],
    )

    # ── Candlestick ───────────────────────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["Open"].tolist(),
            high=df["High"].tolist(),
            low=df["Low"].tolist(),
            close=df["Close"].tolist(),
            name="OHLC",
            increasing_line_color=_GREEN,
            decreasing_line_color=_RED,
            increasing_fillcolor=_GREEN,
            decreasing_fillcolor=_RED,
            line=dict(width=1),
            whiskerwidth=0.3,
        ),
        row=1, col=1,
    )

    # ── SMA overlays ─────────────────────────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=dates, y=df["sma20"].tolist(),
            name="SMA 20",
            line=dict(color="#60a5fa", width=1.2, dash="solid"),
            opacity=0.85,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=dates, y=df["sma50"].tolist(),
            name="SMA 50",
            line=dict(color=_YELLOW, width=1.2, dash="dot"),
            opacity=0.85,
        ),
        row=1, col=1,
    )

    # ── Volume bars ───────────────────────────────────────────────────────────
    fig.add_trace(
        go.Bar(
            x=dates,
            y=df["Volume"].tolist(),
            name="Hacim",
            marker_color=vol_colors,
            opacity=0.75,
            showlegend=False,
        ),
        row=2, col=1,
    )

    # ── 20-day avg volume reference line ─────────────────────────────────────
    avg_vol = df["Volume"].rolling(20).mean()
    fig.add_trace(
        go.Scatter(
            x=dates, y=avg_vol.tolist(),
            name="Ort. Hacim (20g)",
            line=dict(color="#9ca3af", width=1, dash="dash"),
            opacity=0.6,
        ),
        row=2, col=1,
    )

    # ── Layout ────────────────────────────────────────────────────────────────
    axis_style = dict(
        gridcolor=_GRID,
        zerolinecolor=_GRID,
        showgrid=True,
    )

    fig.update_layout(
        **_LAYOUT_BASE,
        title=dict(text=title, font=dict(size=15, color=_TEXT), x=0.01),
        xaxis=dict(
            **axis_style,
            rangeslider=dict(visible=False),
            type="date",
        ),
        xaxis2=dict(**axis_style, type="date"),
        yaxis=dict(**axis_style, title="Fiyat (₺)", tickformat=",.2f"),
        yaxis2=dict(**axis_style, title="Hacim"),
        height=520,
    )

    return fig


# ── Score radar chart ─────────────────────────────────────────────────────────

def build_score_radar(
    momentum: float,
    valuation: float,
    volume: float,
    volatility: float,
    ticker: str,
) -> go.Figure:
    """
    Polar/radar chart showing the four scoring dimensions for a single stock.
    """
    categories  = ["Momentum", "Değerleme", "Hacim Trendi", "Düşük Volatilite"]
    values      = [momentum, valuation, volume, volatility]

    # close the polygon
    cats_closed = categories + [categories[0]]
    vals_closed = values     + [values[0]]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=vals_closed,
        theta=cats_closed,
        fill="toself",
        fillcolor="rgba(0,200,150,0.15)",
        line=dict(color=_GREEN, width=2),
        name=ticker,
    ))

    radar_layout = {**_LAYOUT_BASE, "margin": dict(l=40, r=40, t=20, b=20)}
    fig.update_layout(
        **radar_layout,
        polar=dict(
            bgcolor=_PANEL_BG,
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=9, color="#9ca3af"),
                gridcolor=_GRID,
                linecolor=_GRID,
            ),
            angularaxis=dict(
                tickfont=dict(size=11, color=_TEXT),
                gridcolor=_GRID,
                linecolor=_GRID,
            ),
        ),
        height=320,
        showlegend=False,
    )

    return fig


# ── Fallback empty chart ──────────────────────────────────────────────────────

def _empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color="#9ca3af"),
    )
    fig.update_layout(
        **_LAYOUT_BASE,
        height=300,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig
