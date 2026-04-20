"""
analyzer.py — Groq-powered AI stock analysis (Turkish).

Public API
----------
analyze_stock(ticker_data) -> dict
    Keys: "guclu_yonler", "riskler", "oneri", "raw", "error"
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL        = "llama-3.3-70b-versatile"
_MAX_TOKENS   = 1024
_TEMPERATURE  = 0.3

# ── System prompts ─────────────────────────────────────────────────────────────

_SYSTEM_BASE = """\
Sen deneyimli bir Türk borsa analistisin. \
Verilen hisse senedi verilerini analiz et ve yatırımcıya Türkçe, net ve somut tavsiye ver. \
Spekülatif değil, veri odaklı ol. \
Cevabını MUTLAKA aşağıdaki JSON formatında döndür, başka hiçbir şey ekleme:

{
  "guclu_yonler": "...",
  "riskler": "...",
  "oneri": "..."
}

Her alan 2-4 cümle olsun. Madde işareti veya markdown kullanma, düz metin yaz."""

_SYSTEM_SHORT = _SYSTEM_BASE + """

ODAK: Bu analizde SADECE kısa vadeli (1-4 hafta) teknik ve momentum \
perspektifine odaklan. Uzun vadeli temel analiz yapma."""

_SYSTEM_LONG = _SYSTEM_BASE + """

ODAK: Bu analizde SADECE uzun vadeli (6-12 ay) temel analiz \
perspektifine odaklan. Kısa vadeli fiyat hareketlerini değil, \
şirketin yapısal gücünü ve yatırım uygunluğunu değerlendir."""

# Geriye dönük uyumluluk için
_SYSTEM_PROMPT = _SYSTEM_BASE

_FALLBACK = {
    "guclu_yonler": "Analiz şu anda kullanılamıyor. Lütfen daha sonra tekrar deneyin.",
    "riskler":      "API bağlantısı kurulamadı.",
    "oneri":        "Veriler mevcut olduğunda analizi tekrar çalıştırın.",
    "raw":          "",
    "error":        "groq_unavailable",
}


def _fmt(val, suffix="", decimals=2, fallback="bilinmiyor") -> str:
    if val is None:
        return fallback
    try:
        return f"{float(val):,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_mcap(val) -> str:
    if val is None:
        return "bilinmiyor"
    try:
        v = float(val)
        if v >= 1e12: return f"₺{v/1e12:.2f} trilyon"
        if v >= 1e9:  return f"₺{v/1e9:.2f} milyar"
        if v >= 1e6:  return f"₺{v/1e6:.2f} milyon"
        return f"₺{v:,.0f}"
    except (TypeError, ValueError):
        return "bilinmiyor"


def _build_user_prompt(data: dict) -> str:
    """Genel (eski) prompt — geriye dönük uyumluluk için korundu."""
    price     = data.get("price")
    prev      = data.get("prev_close")
    day_chg   = ((price - prev) / prev * 100) if price and prev and prev != 0 else None

    lines = [
        f"Hisse Kodu      : {data.get('ticker', '?')}",
        f"Şirket Adı      : {data.get('name', '?')}",
        f"Sektör          : {data.get('sector', '?')}",
        f"Güncel Fiyat    : ₺{_fmt(price)}",
        f"52H Yüksek      : ₺{_fmt(data.get('52w_high'))}",
        f"52H Düşük       : ₺{_fmt(data.get('52w_low'))}",
        f"52H Getiri      : %{_fmt(data.get('52w_return'), decimals=1)}",
        f"F/K Oranı       : {_fmt(data.get('pe_ratio'), decimals=1)}",
        f"F/DD Oranı      : {_fmt(data.get('pb_ratio'), decimals=2)}",
        f"Piyasa Değeri   : {_fmt_mcap(data.get('market_cap'))}",
        f"Beta            : {_fmt(data.get('beta'), decimals=2)}",
        f"Temettü Verimi  : %{_fmt(data.get('dividend_yield', 0) * 100 if data.get('dividend_yield') else None, decimals=2)}",
        f"HBS Kazanç (EPS): ₺{_fmt(data.get('eps'), decimals=2)}",
        f"Ort. Günlük Hacim: {_fmt(data.get('avg_volume'), decimals=0)} adet",
        f"Hacim Trendi    : {_fmt(data.get('volume_ratio'), decimals=2)}x (90g ortalamasına göre)",
        f"Yıllık Volatilite: %{_fmt(data.get('volatility'), decimals=1)}",
        f"BIST Radar Skoru: {_fmt(data.get('total_score'), decimals=1)} / 100",
        f"Sinyal          : {data.get('signal', '?')}",
        "",
        "Skor bileşenleri:",
        f"  Momentum    : {_fmt(data.get('momentum_score'),   decimals=1)} / 100",
        f"  Değerleme   : {_fmt(data.get('valuation_score'),  decimals=1)} / 100",
        f"  Hacim       : {_fmt(data.get('volume_score'),     decimals=1)} / 100",
        f"  Volatilite  : {_fmt(data.get('volatility_score'), decimals=1)} / 100",
    ]
    return "\n".join(lines)


def _build_short_term_prompt(data: dict) -> str:
    """
    Kısa dönem (1-4 hafta) odaklı prompt.
    Teknik / momentum verileri ön planda.
    """
    price   = data.get("price")
    prev    = data.get("prev_close")
    day_chg = ((price - prev) / prev * 100) if price and prev and prev != 0 else None

    # SMA20 pozisyonunu momentum skoru üzerinden yorumla
    mom_score = data.get("momentum_score") or 50
    if mom_score >= 70:
        sma_comment = "Fiyat büyük olasılıkla kısa vadeli ortalamalarının üzerinde seyrediyor (güçlü momentum)."
    elif mom_score >= 45:
        sma_comment = "Fiyat kısa vadeli ortalamalar civarında seyrediyor (nötr momentum)."
    else:
        sma_comment = "Fiyat büyük olasılıkla kısa vadeli ortalamalarının altında seyrediyor (zayıf momentum)."

    vol_ratio  = data.get("volume_ratio")
    vol_comment = (
        f"Son 10 günlük işlem hacmi 90 günlük ortalamanın {_fmt(vol_ratio, decimals=2)}x'i — "
        + ("belirgin hacim artışı var." if (vol_ratio or 0) > 1.3
           else "hacim artışı sınırlı." if (vol_ratio or 0) > 0.8
           else "hacim düşük seyrediyor.")
    )

    lines = [
        "=== KISA DÖNEM ANALİZİ (1-4 Hafta Perspektifi) ===",
        "",
        f"Hisse Kodu      : {data.get('ticker', '?')}",
        f"Şirket Adı      : {data.get('name', '?')}",
        f"Sektör          : {data.get('sector', '?')}",
        f"Güncel Fiyat    : ₺{_fmt(price)}",
        f"Günlük Değişim  : %{_fmt(day_chg, decimals=2) if day_chg is not None else 'bilinmiyor'}",
        "",
        "── Momentum & Teknik ──",
        f"Momentum Skoru  : {_fmt(data.get('momentum_score'), decimals=1)} / 100",
        f"SMA20 Pozisyonu : {sma_comment}",
        f"Hacim Trendi    : {vol_comment}",
        f"Hacim Skoru     : {_fmt(data.get('volume_score'), decimals=1)} / 100",
        "",
        "── Kısa Vadeli Volatilite ──",
        f"Yıllık Volatilite: %{_fmt(data.get('volatility'), decimals=1)} (günlük ≈ %{_fmt((data.get('volatility') or 0) / 16, decimals=2)})",
        f"Volatilite Skoru: {_fmt(data.get('volatility_score'), decimals=1)} / 100",
        "",
        "── Son 1 Aylık Fiyat Hareketi (Yaklaşık) ──",
        f"52H Getiri      : %{_fmt(data.get('52w_return'), decimals=1)} (yıllık referans)",
        f"Beta            : {_fmt(data.get('beta'), decimals=2)} (piyasa duyarlılığı)",
        "",
        "── BIST Radar Sinyali ──",
        f"Genel Sinyal    : {data.get('signal', '?')}",
        f"Toplam Skor     : {_fmt(data.get('total_score'), decimals=1)} / 100",
        "",
        "Soru: Bu hisse önümüzdeki 1-4 haftada ne yapabilir? "
        "Momentum, hacim ve volatilite verilerini kullanarak kısa vadeli beklentini açıkla.",
    ]
    return "\n".join(lines)


def _build_long_term_prompt(data: dict) -> str:
    """
    Uzun dönem (6-12 ay) odaklı prompt.
    Temel analiz verileri ön planda.
    """
    dy = data.get("dividend_yield")
    dy_str = _fmt(dy * 100 if dy else None, decimals=2) + "%" if dy else "bilinmiyor"

    lines = [
        "=== UZUN DÖNEM ANALİZİ (6-12 Ay Perspektifi) ===",
        "",
        f"Hisse Kodu      : {data.get('ticker', '?')}",
        f"Şirket Adı      : {data.get('name', '?')}",
        f"Sektör          : {data.get('sector', '?')}",
        f"Güncel Fiyat    : ₺{_fmt(data.get('price'))}",
        "",
        "── Değerleme Metrikleri ──",
        f"F/K Oranı       : {_fmt(data.get('pe_ratio'), decimals=1)}",
        f"F/DD Oranı      : {_fmt(data.get('pb_ratio'), decimals=2)}",
        f"HBS Kazanç (EPS): ₺{_fmt(data.get('eps'), decimals=2)}",
        f"Değerleme Skoru : {_fmt(data.get('valuation_score'), decimals=1)} / 100",
        "",
        "── Temettü & Sermaye ──",
        f"Temettü Verimi  : {dy_str}",
        f"Piyasa Değeri   : {_fmt_mcap(data.get('market_cap'))}",
        "",
        "── Risk & Piyasa Pozisyonu ──",
        f"Beta            : {_fmt(data.get('beta'), decimals=2)} (1.0 = piyasayla aynı risk)",
        f"52H Getiri      : %{_fmt(data.get('52w_return'), decimals=1)}",
        f"52H Yüksek      : ₺{_fmt(data.get('52w_high'))}",
        f"52H Düşük       : ₺{_fmt(data.get('52w_low'))}",
        f"Yıllık Volatilite: %{_fmt(data.get('volatility'), decimals=1)}",
        "",
        "── BIST Radar Özeti ──",
        f"Genel Sinyal    : {data.get('signal', '?')}",
        f"Toplam Skor     : {_fmt(data.get('total_score'), decimals=1)} / 100",
        "",
        "Soru: Bu hisse uzun vadeli (6-12 ay) portföy için uygun mu? "
        "F/K, F/DD, temettü, beta ve sektör pozisyonunu temel alarak değerlendirme yap.",
    ]
    return "\n".join(lines)


def _parse_response(text: str) -> dict:
    """
    Extract the JSON object from the model response.
    Falls back to splitting by section headers if JSON parse fails.
    """
    text = text.strip()

    # Try strict JSON first
    try:
        # Find the first { ... } block
        start = text.index("{")
        end   = text.rindex("}") + 1
        obj   = json.loads(text[start:end])
        return {
            "guclu_yonler": obj.get("guclu_yonler", ""),
            "riskler":      obj.get("riskler", ""),
            "oneri":        obj.get("oneri", ""),
            "raw":          text,
            "error":        None,
        }
    except (ValueError, KeyError, json.JSONDecodeError):
        pass

    # Graceful fallback: return raw text in "oneri" field
    return {
        "guclu_yonler": "",
        "riskler":      "",
        "oneri":        text,
        "raw":          text,
        "error":        "parse_failed",
    }


def _call_groq(system_prompt: str, user_prompt: str, ticker: str = "?") -> dict:
    """Shared Groq API call used by all analyze_* functions."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        logger.warning("GROQ_API_KEY not set — returning fallback")
        return {**_FALLBACK, "error": "no_api_key"}

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
    except ImportError:
        logger.error("groq package not installed")
        return {**_FALLBACK, "error": "groq_not_installed"}
    except Exception as exc:
        logger.error("Groq client init failed: %s", exc)
        return {**_FALLBACK, "error": str(exc)}

    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )
        raw_text = response.choices[0].message.content or ""
        return _parse_response(raw_text)
    except Exception as exc:
        logger.error("Groq API call failed for %s: %s", ticker, exc)
        return {**_FALLBACK, "error": str(exc)}


def analyze_short_term(ticker_data: dict) -> dict:
    """
    1-4 haftalık kısa dönem perspektifiyle analiz.
    Momentum, hacim trendi, volatilite ve SMA pozisyonu odaklı.
    """
    return _call_groq(
        system_prompt=_SYSTEM_SHORT,
        user_prompt=_build_short_term_prompt(ticker_data),
        ticker=ticker_data.get("ticker", "?"),
    )


def analyze_long_term(ticker_data: dict) -> dict:
    """
    6-12 aylık uzun dönem perspektifiyle analiz.
    F/K, F/DD, temettü, beta ve sektör odaklı temel analiz.
    """
    return _call_groq(
        system_prompt=_SYSTEM_LONG,
        user_prompt=_build_long_term_prompt(ticker_data),
        ticker=ticker_data.get("ticker", "?"),
    )


def analyze_stock(ticker_data: dict) -> dict:
    """
    Send structured stock data to Groq and return parsed analysis sections.

    Parameters
    ----------
    ticker_data : dict
        Row from scored_df (as returned by screener.score_dataframe),
        enriched with volume_ratio and volatility fields.

    Returns
    -------
    dict with keys:
        guclu_yonler  — paragraph on strengths
        riskler       — paragraph on risks
        oneri         — actionable recommendation
        raw           — raw model output string
        error         — None on success, error tag on failure
    """
    return _call_groq(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(ticker_data),
        ticker=ticker_data.get("ticker", "?"),
    )
