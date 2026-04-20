"""
data_fetcher.py — Yahoo Finance v8 chart API via curl_cffi.

Why curl_cffi?
--------------
Yahoo Finance blocks Python's default requests library on Streamlit Cloud's
shared IP ranges by fingerprinting the TLS handshake.  curl_cffi uses libcurl
to produce an authentic Chrome TLS fingerprint, which Yahoo Finance accepts.

This module calls the v8/finance/chart endpoint with a curl_cffi session
impersonating Chrome 110.  One HTTP request per ticker, inside a cached
function — the loop only runs on a cold cache.  Warm-cache loads are instant.

Public API (unchanged from all previous versions):
    fetch_all_tickers(tickers?)   → pd.DataFrame (screener table)
    fetch_price_history(ticker)   → pd.DataFrame (detail-view chart)
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
from curl_cffi import requests as cf_requests

from data.bist_tickers import TICKER_MAP, TICKER_SYMBOLS

logger = logging.getLogger(__name__)

# ── Shared curl_cffi session with Chrome TLS fingerprint ─────────────────────

_SESSION = cf_requests.Session(impersonate="chrome120")
_SESSION.headers.update({
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://finance.yahoo.com/",
    "Origin":          "https://finance.yahoo.com",
})

_BASE_URL        = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_BASE_URL2       = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
_QUOTE_SUMMARY   = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
_CRUMB_URL       = "https://query2.finance.yahoo.com/v1/test/getcrumb"

_RANGE_MAP = {
    "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
    "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y",
}


# ── Low-level HTTP fetch ──────────────────────────────────────────────────────

def _fetch_chart(
    ticker: str,
    range_: str = "1y",
    interval: str = "1d",
) -> Optional[dict]:
    """
    GET the v8/finance/chart JSON for *ticker* and return the first result dict.

    Tries query1 first, falls back to query2 on non-2xx.
    Retries once after 3 s on HTTP 429 (rate limited) or network errors.
    Returns None on unrecoverable failure so callers can skip the ticker.
    """
    params = {"interval": interval, "range": range_, "includeAdjustedClose": "true"}

    for attempt in range(2):
        for base in (_BASE_URL, _BASE_URL2):
            url = base.format(ticker=ticker)
            logger.debug("Fetching URL: %s", url)
            try:
                resp = _SESSION.get(url, params=params, timeout=12)

                if resp.status_code == 404:
                    logger.debug("Not found (404) for %s — skipping", ticker)
                    return None  # permanent; no point retrying

                if resp.status_code == 429:
                    logger.warning(
                        "Rate limited for %s (attempt %d) — sleeping 5s", ticker, attempt + 1
                    )
                    time.sleep(5)
                    break  # break inner loop, let outer loop retry

                if resp.status_code != 200:
                    logger.warning("HTTP %d for %s", resp.status_code, url)
                    continue  # try query2

                data    = resp.json()
                results = data.get("chart", {}).get("result")
                err     = data.get("chart", {}).get("error")

                if err:
                    logger.warning("API error for %s: %s", ticker, err)
                    return None

                if not results:
                    logger.warning("Empty result list for %s", ticker)
                    return None

                return results[0]

            except Exception as exc:
                logger.warning("Request error for %s (attempt %d): %s", ticker, attempt + 1, exc)

        if attempt == 0:
            time.sleep(3)

    logger.error("Failed to fetch chart for %s after 2 attempts", ticker)
    return None


# ── Fundamental metrics (beta, P/B, dividend, EPS) ───────────────────────────

_CRUMB_RETRIES = 3
_CRUMB_RETRY_DELAY = 2  # seconds


def _get_crumb() -> str:
    """
    Obtain a Yahoo Finance API crumb by establishing a browser-like session.
    The crumb is required by the v10/quoteSummary endpoint.

    Retries up to _CRUMB_RETRIES times with _CRUMB_RETRY_DELAY seconds between
    attempts.  Returns an empty string on total failure.
    """
    for attempt in range(1, _CRUMB_RETRIES + 1):
        try:
            _SESSION.headers["Accept"] = "text/html,application/xhtml+xml,*/*"
            _SESSION.get("https://finance.yahoo.com/", timeout=12)
            _SESSION.headers["Accept"] = "text/plain, */*"
            r = _SESSION.get(_CRUMB_URL, timeout=8)
            if r.status_code == 200 and r.text.strip():
                logger.debug("Crumb acquired on attempt %d", attempt)
                return r.text.strip()
            logger.debug(
                "Crumb endpoint returned HTTP %d on attempt %d", r.status_code, attempt
            )
        except Exception as exc:
            logger.debug("Crumb attempt %d failed: %s", attempt, exc)
        finally:
            _SESSION.headers["Accept"] = "application/json, text/plain, */*"

        if attempt < _CRUMB_RETRIES:
            time.sleep(_CRUMB_RETRY_DELAY)

    logger.debug("Crumb unavailable after %d attempts — will use yfinance fallback", _CRUMB_RETRIES)
    return ""


# Session-scoped crumb; refreshed lazily on 401.
_CRUMB: str = ""


def _fetch_fundamentals_yfinance(ticker: str) -> dict:
    """
    Fallback fundamental data source via the yfinance library.

    Called when the Yahoo Finance crumb / quoteSummary endpoint is
    unavailable.  Fetches trailingPE, priceToBook, beta, dividendYield,
    trailingEps, sharesOutstanding and marketCap from Ticker.info.

    Returns a (possibly partial) dict; missing fields are None.
    Never raises.
    """
    try:
        import yfinance as yf  # lazy import — not required for OHLCV path

        info = yf.Ticker(ticker).info
        if not info:
            logger.debug("yfinance returned empty info for %s", ticker)
            return {}

        def _sf(key: str) -> Optional[float]:
            v = info.get(key)
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        result = {
            "beta":               _sf("beta"),
            "pb_ratio":           _sf("priceToBook"),
            "eps":                _sf("trailingEps"),
            "shares_outstanding": _sf("sharesOutstanding"),
            "dividend_yield":     _sf("dividendYield"),
            "pe_ratio":           _sf("trailingPE"),
            "market_cap":         _sf("marketCap"),
        }
        # Only log if we got at least something useful
        got = [k for k, v in result.items() if v is not None]
        if got:
            logger.debug("yfinance fallback OK for %s: %s", ticker, got)
        else:
            logger.debug("yfinance fallback returned no data for %s", ticker)
        return result

    except ImportError:
        logger.debug("yfinance not installed — fundamental fallback unavailable")
        return {}
    except Exception as exc:
        logger.debug("yfinance fallback failed for %s: %s", ticker, exc)
        return {}


def _fetch_quote_fundamentals(ticker: str) -> dict:
    """
    Fetch beta, priceToBook, dividendYield, trailingEps, trailingPE from
    Yahoo Finance v10/quoteSummary in a single HTTP call.

    Strategy
    --------
    1. Acquire (or reuse) a session-scoped crumb — retried up to 3× internally.
    2. Call quoteSummary; refresh crumb on 401 and retry once.
    3. If the crumb is permanently unavailable, fall back to yfinance.info.
    4. If both sources fail, return {} so callers show "—" in the UI.

    All failures are logged at DEBUG level only (no user-visible warnings).
    Never raises.
    """
    global _CRUMB

    def _rf(section: dict, key: str) -> Optional[float]:
        v = section.get(key, {})
        raw = v.get("raw") if isinstance(v, dict) else v
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    def _quotesummary_attempt(crumb: str) -> dict:
        url = _QUOTE_SUMMARY.format(ticker=ticker)
        resp = _SESSION.get(
            url,
            params={"modules": "defaultKeyStatistics,summaryDetail", "crumb": crumb},
            timeout=10,
        )
        if resp.status_code == 401:
            return {"_unauthorized": True}
        if resp.status_code in (404, 422):
            return {}
        if resp.status_code != 200:
            logger.debug("quoteSummary HTTP %d for %s", resp.status_code, ticker)
            return {}
        data    = resp.json()
        result  = data.get("quoteSummary", {}).get("result") or []
        if not result:
            return {}
        modules = result[0]
        ks = modules.get("defaultKeyStatistics", {})
        sd = modules.get("summaryDetail", {})
        return {
            "beta":               _rf(ks, "beta"),
            "pb_ratio":           _rf(ks, "priceToBook"),
            "eps":                _rf(ks, "trailingEps"),
            "shares_outstanding": _rf(ks, "sharesOutstanding"),
            "dividend_yield":     _rf(sd, "dividendYield"),
            "pe_ratio":           _rf(sd, "trailingPE"),
            "market_cap":         _rf(sd, "marketCap"),
        }

    # ── 1. Try crumb-based quoteSummary ──────────────────────────────────────
    try:
        if not _CRUMB:
            _CRUMB = _get_crumb()

        if _CRUMB:
            result = _quotesummary_attempt(_CRUMB)
            if result.pop("_unauthorized", False):
                logger.debug("Crumb expired for %s — refreshing", ticker)
                _CRUMB = _get_crumb()
                if _CRUMB:
                    result = _quotesummary_attempt(_CRUMB)
                    result.pop("_unauthorized", None)
                else:
                    result = {}
            if result:
                return result
            # Empty dict → quoteSummary gave nothing; fall through to yfinance
        else:
            logger.debug("Crumb unavailable for %s — trying yfinance fallback", ticker)

    except Exception as exc:
        logger.debug("quoteSummary path failed for %s: %s", ticker, exc)

    # ── 2. Fallback: yfinance .info ───────────────────────────────────────────
    return _fetch_fundamentals_yfinance(ticker)


# ── JSON → DataFrame ──────────────────────────────────────────────────────────

def _chart_to_ohlcv(result: dict, ticker: str) -> Optional[pd.DataFrame]:
    """
    Parse a v8/finance/chart result dict into a daily OHLCV DataFrame.

    Timestamps are UTC Unix seconds → converted to date-only index (no tz).
    Uses adjclose when available; falls back to raw close.
    """
    try:
        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {})
        quote      = indicators.get("quote", [{}])[0]

        if not timestamps or not quote:
            logger.warning("No OHLCV data in chart result for %s", ticker)
            return None

        adj_list = (
            indicators.get("adjclose", [{}])[0].get("adjclose")
            if indicators.get("adjclose")
            else None
        )
        close_values = adj_list if adj_list else quote.get("close", [])

        dates = (
            pd.to_datetime(timestamps, unit="s", utc=True)
            .tz_convert("Europe/Istanbul")
            .tz_localize(None)
            .normalize()
        )

        df = pd.DataFrame(
            {
                "Open":   quote.get("open",   []),
                "High":   quote.get("high",   []),
                "Low":    quote.get("low",    []),
                "Close":  close_values,
                "Volume": quote.get("volume", []),
            },
            index=dates,
        )

        df = df.apply(pd.to_numeric, errors="coerce")
        df = df.dropna(how="all")
        df.sort_index(inplace=True)

        if df.empty:
            logger.warning("OHLCV DataFrame empty after cleaning for %s", ticker)
            return None

        return df

    except Exception as exc:
        logger.error("chart_to_ohlcv failed for %s: %s", ticker, exc)
        return None


# ── Build metrics row ─────────────────────────────────────────────────────────

def _build_row(ticker: str, result: dict, fundamentals: dict | None = None) -> Optional[dict]:
    """
    Combine meta fields (live price, 52w hi/lo) with OHLCV-derived
    statistics (returns, volume ratio, volatility) into the metrics dict
    consumed by screener.score_dataframe().
    """
    ohlcv = _chart_to_ohlcv(result, ticker)
    if ohlcv is None:
        return None

    meta   = result.get("meta", {})
    close  = ohlcv["Close"].dropna()
    high   = ohlcv["High"].dropna()
    low    = ohlcv["Low"].dropna()
    volume = ohlcv["Volume"].dropna()

    if close.empty:
        return None

    def _mf(key: str) -> Optional[float]:
        v = meta.get(key)
        return float(v) if v is not None else None

    price = (
        _mf("regularMarketPrice")
        or _mf("currentPrice")
        or float(close.iloc[-1])
    )
    prev_close = (
        _mf("regularMarketPreviousClose")
        or _mf("chartPreviousClose")
        or _mf("previousClose")
        or (float(close.iloc[-2]) if len(close) >= 2 else price)
    )

    w52_high = _mf("fiftyTwoWeekHigh") or float(high.max())
    w52_low  = _mf("fiftyTwoWeekLow")  or float(low.min())

    w52_ret: Optional[float] = None
    if len(close) >= 2 and float(close.iloc[0]) != 0:
        w52_ret = float((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100)

    avg_vol = float(volume.mean()) if not volume.empty else None
    cur_vol = float(volume.iloc[-1]) if not volume.empty else None

    vol_ratio: Optional[float] = None
    if len(volume) >= 90:
        short_avg = volume.iloc[-10:].mean()
        long_avg  = volume.iloc[-90:].mean()
        if long_avg > 0:
            vol_ratio = float(short_avg / long_avg)

    volatility: Optional[float] = None
    if len(close) >= 31:
        log_ret    = np.log(close / close.shift(1)).dropna()
        volatility = float(log_ret.iloc[-30:].std() * np.sqrt(252) * 100)

    local = TICKER_MAP.get(ticker, {})
    fund  = fundamentals or {}

    # Market cap: chart meta → quoteSummary summaryDetail → shares × price
    market_cap = _mf("marketCap") or fund.get("market_cap")
    if not market_cap:
        shares = fund.get("shares_outstanding")
        if shares and price:
            market_cap = shares * price

    return {
        "ticker":         ticker,
        "name":           local.get("name", meta.get("shortName", ticker)),
        "sector":         local.get("sector", "Diger"),
        "price":          price,
        "prev_close":     prev_close,
        "52w_high":       w52_high,
        "52w_low":        w52_low,
        "52w_return":     w52_ret,
        "avg_volume":     avg_vol,
        "volume":         cur_vol,
        "volume_ratio":   vol_ratio,
        "volatility":     volatility,
        "pe_ratio":       _mf("trailingPE") or fund.get("pe_ratio"),
        "market_cap":     market_cap,
        "beta":           fund.get("beta"),
        "dividend_yield": fund.get("dividend_yield"),
        "eps":            fund.get("eps"),
        "pb_ratio":       fund.get("pb_ratio"),
    }


# ── Public: bulk screener data ────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_tickers(tickers: tuple[str, ...] | None = None) -> pd.DataFrame:
    """
    Fetch 1-year OHLCV + meta for every ticker via the Yahoo Finance v8 chart
    API and return a consolidated metrics DataFrame.  Cached for 1 hour.

    Uses curl_cffi with Chrome TLS impersonation to bypass Yahoo's bot filter.

    Side-effects
    ------------
    Writes st.session_state["fetch_failed"] with tickers that returned no
    data so the UI can surface a collapsible warning list.
    """
    if tickers is None:
        tickers = tuple(TICKER_SYMBOLS)

    rows:   list[dict] = []
    failed: list[str]  = []

    for i, ticker in enumerate(tickers, 1):
        result = _fetch_chart(ticker, range_="1y", interval="1d")

        if result is None:
            failed.append(ticker)
            time.sleep(0.3)
            continue

        fundamentals = _fetch_quote_fundamentals(ticker)
        row = _build_row(ticker, result, fundamentals)
        if row is None:
            failed.append(ticker)
        else:
            rows.append(row)
            logger.debug("OK %s (%d/%d)", ticker, i, len(tickers))

        time.sleep(0.3)

    if failed:
        logger.warning("No data for %d tickers: %s", len(failed), failed)
    try:
        st.session_state["fetch_failed"] = failed
    except Exception:
        pass

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.set_index("ticker", inplace=True)
    return df


# ── Public: single-ticker OHLCV for detail-view chart ────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_price_history(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    """
    Return a 6-month OHLCV DataFrame for the detail-view candlestick chart.
    One HTTP call, fired only when the user opens the detail view.
    """
    range_ = _RANGE_MAP.get(period, period)
    result = _fetch_chart(ticker, range_=range_, interval=interval)

    if result is None:
        return None

    return _chart_to_ohlcv(result, ticker)
