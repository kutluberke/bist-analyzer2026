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

_SYSTEM_PROMPT = """\
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

_FALLBACK = {
    "guclu_yonler": "Analiz şu anda kullanılamıyor. Lütfen daha sonra tekrar deneyin.",
    "riskler":      "API bağlantısı kurulamadı.",
    "oneri":        "Veriler mevcut olduğunda analizi tekrar çalıştırın.",
    "raw":          "",
    "error":        "groq_unavailable",
}


def _build_user_prompt(data: dict) -> str:
    """Format ticker_data dict into a structured Turkish prompt."""

    def _fmt(val, suffix="", decimals=2, fallback="bilinmiyor"):
        if val is None:
            return fallback
        try:
            return f"{float(val):,.{decimals}f}{suffix}"
        except (TypeError, ValueError):
            return str(val)

    def _fmt_mcap(val):
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

    lines = [
        f"Hisse Kodu      : {data.get('ticker', '?')}",
        f"Şirket Adı      : {data.get('name', '?')}",
        f"Sektör          : {data.get('sector', '?')}",
        f"Güncel Fiyat    : ₺{_fmt(data.get('price'))}",
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

    user_prompt = _build_user_prompt(ticker_data)

    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )
        raw_text = response.choices[0].message.content or ""
        return _parse_response(raw_text)

    except Exception as exc:
        logger.error("Groq API call failed for %s: %s", ticker_data.get("ticker"), exc)
        return {**_FALLBACK, "error": str(exc)}
