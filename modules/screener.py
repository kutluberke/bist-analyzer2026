"""
screener.py — Signal scoring and DataFrame filtering logic.

Scoring model (0-100):
  Momentum    30 pts  — 52w return vs sector peers
  Valuation   30 pts  — P/E vs sector median (lower = better; None gets neutral)
  Volume      20 pts  — recent volume ratio vs 90-day average
  Volatility  20 pts  — penalty for annualised vol > sector median

Signal mapping:
  score > 65  → "🟢 AL"
  score 40-65 → "🟡 BEKLE"
  score < 40  → "🔴 SAT"
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SIGNAL_AL    = "🟢 AL"
SIGNAL_BEKLE = "🟡 BEKLE"
SIGNAL_SAT   = "🔴 SAT"

WEIGHT_MOMENTUM   = 0.30
WEIGHT_VALUATION  = 0.30
WEIGHT_VOLUME     = 0.20
WEIGHT_VOLATILITY = 0.20

AL_THRESHOLD    = 65.0
SAT_THRESHOLD   = 40.0


# ── Internal scoring helpers ───────────────────────────────────────────────────

def _percentile_score(value: float, series: pd.Series, higher_is_better: bool = True) -> float:
    """
    Score *value* by its percentile rank within *series* → [0, 100].
    higher_is_better=False inverts the ranking (e.g. lower P/E is better).
    """
    valid = series.dropna()
    if valid.empty or np.isnan(value):
        return 50.0  # neutral when no peers

    rank = (valid < value).sum() / len(valid)  # fraction of peers below value
    score = rank * 100.0

    if not higher_is_better:
        score = 100.0 - score

    return float(np.clip(score, 0.0, 100.0))


def _momentum_score(ticker: str, df: pd.DataFrame) -> float:
    """30-pt component: 52w return vs sector peers."""
    row = df.loc[ticker]
    ret = row.get("52w_return")
    if ret is None or np.isnan(float(ret if ret is not None else np.nan)):
        return 50.0

    sector = row.get("sector", "")
    peers  = df[df["sector"] == sector]["52w_return"].dropna().astype(float)
    return _percentile_score(float(ret), peers, higher_is_better=True)


# TODO: incorporate beta (risk-adjusted return) and pb_ratio into valuation
# scoring once data is confirmed flowing. pb_ratio < 1 or beta-normalised
# momentum would improve signal quality.
def _valuation_score(ticker: str, df: pd.DataFrame) -> float:
    """30-pt component: P/E vs sector median (lower P/E = better score)."""
    row = df.loc[ticker]
    pe  = row.get("pe_ratio")

    if pe is None:
        return 50.0  # no P/E data → neutral

    pe = float(pe)
    if np.isnan(pe) or pe <= 0:
        return 50.0

    sector = row.get("sector", "")
    peers  = df[(df["sector"] == sector) & (df["pe_ratio"] > 0)]["pe_ratio"].dropna().astype(float)
    return _percentile_score(pe, peers, higher_is_better=False)


def _volume_score(ticker: str, df: pd.DataFrame) -> float:
    """20-pt component: recent 10-day vol ratio vs 90-day average."""
    row   = df.loc[ticker]
    ratio = row.get("volume_ratio")

    if ratio is None:
        return 50.0

    ratio = float(ratio)
    if np.isnan(ratio):
        return 50.0

    # Ratio 1.0 = neutral (50 pts).  Cap gains at 2.5× and losses at 0.25×.
    ratio = np.clip(ratio, 0.25, 2.5)
    score = (ratio - 0.25) / (2.5 - 0.25) * 100.0
    return float(np.clip(score, 0.0, 100.0))


def _volatility_score(ticker: str, df: pd.DataFrame) -> float:
    """20-pt component: penalise high annualised vol relative to sector."""
    row = df.loc[ticker]
    vol = row.get("volatility")

    if vol is None:
        return 50.0

    vol = float(vol)
    if np.isnan(vol):
        return 50.0

    sector = row.get("sector", "")
    peers  = df[df["sector"] == sector]["volatility"].dropna().astype(float)

    # Lower vol = better score → invert percentile
    return _percentile_score(vol, peers, higher_is_better=False)


# ── Public API ────────────────────────────────────────────────────────────────

def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-stock scores and signals for every row in *df*.

    *df* must have the columns produced by data_fetcher.fetch_all_tickers()
    plus optional 'volume_ratio' and 'volatility' columns (added by
    enrich_dataframe if available).

    Adds columns: momentum_score, valuation_score, volume_score,
    volatility_score, total_score, signal.

    Returns a copy of *df* with the new columns appended.
    """
    if df.empty:
        return df

    out = df.copy()

    # Ensure numeric types for scoring columns
    for col in ["52w_return", "pe_ratio", "volume_ratio", "volatility"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        else:
            out[col] = np.nan

    mom_scores  = []
    val_scores  = []
    vol_scores  = []
    vola_scores = []

    for ticker in out.index:
        try:
            m  = _momentum_score(ticker, out)
            v  = _valuation_score(ticker, out)
            vo = _volume_score(ticker, out)
            vl = _volatility_score(ticker, out)
        except Exception as exc:
            logger.error("Scoring failed for %s: %s", ticker, exc)
            m = v = vo = vl = 50.0

        mom_scores.append(m)
        val_scores.append(v)
        vol_scores.append(vo)
        vola_scores.append(vl)

    out["momentum_score"]   = mom_scores
    out["valuation_score"]  = val_scores
    out["volume_score"]     = vol_scores
    out["volatility_score"] = vola_scores

    out["total_score"] = (
        out["momentum_score"]   * WEIGHT_MOMENTUM
        + out["valuation_score"]  * WEIGHT_VALUATION
        + out["volume_score"]     * WEIGHT_VOLUME
        + out["volatility_score"] * WEIGHT_VOLATILITY
    ).round(1)

    _min, _max = out["total_score"].min(), out["total_score"].max()
    if _max > _min:
        out["total_score"] = ((out["total_score"] - _min) / (_max - _min) * 100).round(1)

    out["signal"] = out["total_score"].apply(_score_to_signal)
    return out


def _score_to_signal(score: float) -> str:
    if score >= AL_THRESHOLD:
        return SIGNAL_AL
    if score >= SAT_THRESHOLD:
        return SIGNAL_BEKLE
    return SIGNAL_SAT


# ── Filter logic ──────────────────────────────────────────────────────────────

def apply_filters(
    df: pd.DataFrame,
    sectors: Optional[list[str]] = None,
    market_cap_min: Optional[float] = None,
    market_cap_max: Optional[float] = None,
    pe_min: Optional[float] = None,
    pe_max: Optional[float] = None,
    min_52w_return: Optional[float] = None,
    min_avg_volume: Optional[float] = None,
) -> pd.DataFrame:
    """
    Apply sidebar filter selections to *df* and return the filtered copy.

    All parameters are optional; passing None skips that filter.
    """
    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)

    if sectors:
        mask &= df["sector"].isin(sectors)

    if market_cap_min is not None and "market_cap" in df.columns:
        mask &= df["market_cap"].fillna(0) >= market_cap_min

    if market_cap_max is not None and "market_cap" in df.columns:
        mask &= df["market_cap"].fillna(float("inf")) <= market_cap_max

    if pe_min is not None and "pe_ratio" in df.columns:
        # Only filter rows that *have* a P/E value
        has_pe = df["pe_ratio"].notna()
        mask &= (~has_pe) | (df["pe_ratio"] >= pe_min)

    if pe_max is not None and "pe_ratio" in df.columns:
        has_pe = df["pe_ratio"].notna()
        mask &= (~has_pe) | (df["pe_ratio"] <= pe_max)

    if min_52w_return is not None and "52w_return" in df.columns:
        mask &= df["52w_return"].fillna(-999) >= min_52w_return

    if min_avg_volume is not None and "avg_volume" in df.columns:
        mask &= df["avg_volume"].fillna(0) >= min_avg_volume

    return df[mask].copy()


# ── Display helpers ───────────────────────────────────────────────────────────

def build_display_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a display-ready DataFrame with renamed, formatted columns
    suitable for st.dataframe / st.data_editor.
    """
    if df.empty:
        return pd.DataFrame()

    cols = {
        "name":        "Şirket",
        "sector":      "Sektör",
        "price":       "Fiyat (₺)",
        "pe_ratio":    "F/K",
        "market_cap":  "Piyasa Değeri",
        "52w_return":  "52H Getiri %",
        "total_score": "Skor",
        "signal":      "Sinyal",
    }

    available = [c for c in cols if c in df.columns]
    display   = df[available].rename(columns=cols).copy()

    # Format market cap as human-readable string
    if "Piyasa Değeri" in display.columns:
        display["Piyasa Değeri"] = display["Piyasa Değeri"].apply(_fmt_market_cap)

    # Format F/K as string so None renders as "—" not "None"
    if "F/K" in display.columns:
        display["F/K"] = display["F/K"].apply(_fmt_pe)

    # Round remaining numeric cols
    for col in ["Fiyat (₺)", "52H Getiri %", "Skor"]:
        if col in display.columns:
            display[col] = pd.to_numeric(display[col], errors="coerce").round(2)

    return display


def _fmt_market_cap(val) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    val = float(val)
    if val >= 1e12:
        return f"₺{val/1e12:.1f}T"
    if val >= 1e9:
        return f"₺{val/1e9:.1f}Mlr"
    if val >= 1e6:
        return f"₺{val/1e6:.1f}Mn"
    return f"₺{val:,.0f}"


def _fmt_pe(val) -> str:
    if val is None or val == "None":
        return "—"
    try:
        f = float(val)
        return "—" if np.isnan(f) or f <= 0 else f"{f:.1f}"
    except (TypeError, ValueError):
        return "—"


