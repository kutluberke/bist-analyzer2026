# BIST Ticker List — Yahoo Finance format (suffix: .IS)
# Audited 2026-04-05: 79 symbols confirmed live on Yahoo Finance.
# Expanded 2026-04-07: +26 BIST-100 constituents added (105 total).
# Any symbol that returns 404 is silently skipped by _fetch_chart.

BIST_TICKERS: list[dict] = [
    # ── Bankacılık ───────────────────────────────────────────────────────────
    {"ticker": "GARAN.IS",  "name": "Garanti BBVA",              "sector": "Bankacılık"},
    {"ticker": "AKBNK.IS",  "name": "Akbank",                    "sector": "Bankacılık"},
    {"ticker": "ISCTR.IS",  "name": "İş Bankası (C)",            "sector": "Bankacılık"},
    {"ticker": "YKBNK.IS",  "name": "Yapı Kredi Bankası",        "sector": "Bankacılık"},
    {"ticker": "HALKB.IS",  "name": "Halkbank",                  "sector": "Bankacılık"},
    {"ticker": "VAKBN.IS",  "name": "Vakıfbank",                 "sector": "Bankacılık"},
    {"ticker": "TSKB.IS",   "name": "TSKB",                      "sector": "Bankacılık"},
    {"ticker": "ALBRK.IS",  "name": "Albaraka Türk",             "sector": "Bankacılık"},
    {"ticker": "ICBCT.IS",  "name": "ICBC Turkey",               "sector": "Bankacılık"},

    # ── Holding ──────────────────────────────────────────────────────────────
    {"ticker": "KCHOL.IS",  "name": "Koç Holding",               "sector": "Holding"},
    {"ticker": "SAHOL.IS",  "name": "Sabancı Holding",           "sector": "Holding"},
    {"ticker": "SISE.IS",   "name": "Şişe Cam",                  "sector": "Holding"},
    {"ticker": "TKFEN.IS",  "name": "Tekfen Holding",            "sector": "Holding"},
    {"ticker": "DOHOL.IS",  "name": "Doğan Holding",             "sector": "Holding"},
    {"ticker": "NTHOL.IS",  "name": "Net Holding",               "sector": "Holding"},
    {"ticker": "AGHOL.IS",  "name": "AG Anadolu Grubu",          "sector": "Holding"},
    {"ticker": "OYAKC.IS",  "name": "Oyak Çimento",              "sector": "Holding"},
    {"ticker": "ARCLK.IS",  "name": "Arçelik",                   "sector": "Holding"},

    # ── Enerji ───────────────────────────────────────────────────────────────
    {"ticker": "TUPRS.IS",  "name": "Tüpraş",                    "sector": "Enerji"},
    {"ticker": "AKSEN.IS",  "name": "Aksa Enerji",               "sector": "Enerji"},
    {"ticker": "AKENR.IS",  "name": "AK Enerji",                 "sector": "Enerji"},
    {"ticker": "ZOREN.IS",  "name": "Zorlu Enerji",              "sector": "Enerji"},
    {"ticker": "ODAS.IS",   "name": "Odaş Elektrik",             "sector": "Enerji"},
    {"ticker": "TURSG.IS",  "name": "Turkcell Superonline",      "sector": "Enerji"},
    {"ticker": "EUPWR.IS",  "name": "Europower Enerji",          "sector": "Enerji"},
    {"ticker": "ENJSA.IS",  "name": "Enerjisa",                  "sector": "Enerji"},
    {"ticker": "NTGAZ.IS",  "name": "Naturelgaz",                "sector": "Enerji"},

    # ── Otomotiv ─────────────────────────────────────────────────────────────
    {"ticker": "FROTO.IS",  "name": "Ford Otosan",               "sector": "Otomotiv"},
    {"ticker": "TOASO.IS",  "name": "Tofaş Otomobil",            "sector": "Otomotiv"},
    {"ticker": "TTRAK.IS",  "name": "Türk Traktör",              "sector": "Otomotiv"},
    {"ticker": "OTKAR.IS",  "name": "Otokar",                    "sector": "Otomotiv"},
    {"ticker": "DOAS.IS",   "name": "Doğuş Otomotiv",            "sector": "Otomotiv"},
    {"ticker": "KARSN.IS",  "name": "Karsan Otomotiv",           "sector": "Otomotiv"},
    {"ticker": "PARSN.IS",  "name": "Parsan",                    "sector": "Otomotiv"},

    # ── Savunma ──────────────────────────────────────────────────────────────
    {"ticker": "ASELS.IS",  "name": "Aselsan",                   "sector": "Savunma"},
    {"ticker": "RODRG.IS",  "name": "Roketsan",                  "sector": "Savunma"},
    {"ticker": "CGCAM.IS",  "name": "Çağ Cam",                   "sector": "Savunma"},
    {"ticker": "HATEK.IS",  "name": "Havelsan",                  "sector": "Savunma"},
    {"ticker": "KUTPO.IS",  "name": "Kütahya Porselen",          "sector": "Savunma"},

    # ── Perakende ────────────────────────────────────────────────────────────
    {"ticker": "BIMAS.IS",  "name": "BİM Mağazaları",            "sector": "Perakende"},
    {"ticker": "MGROS.IS",  "name": "Migros Ticaret",            "sector": "Perakende"},
    {"ticker": "SOKM.IS",   "name": "Şok Marketler",             "sector": "Perakende"},
    {"ticker": "CRFSA.IS",  "name": "CarrefourSA",               "sector": "Perakende"},
    {"ticker": "BIZIM.IS",  "name": "Bizim Toptan",              "sector": "Perakende"},
    {"ticker": "MAVI.IS",   "name": "Mavi Giyim",                "sector": "Perakende"},
    {"ticker": "YATAS.IS",  "name": "Yataş",                     "sector": "Perakende"},
    {"ticker": "KARTN.IS",  "name": "Kartonsan",                 "sector": "Perakende"},

    # ── Cam / Çelik ──────────────────────────────────────────────────────────
    {"ticker": "EREGL.IS",  "name": "Ereğli Demir Çelik",       "sector": "Cam/Çelik"},
    {"ticker": "KRDMD.IS",  "name": "Kardemir (D)",              "sector": "Cam/Çelik"},
    {"ticker": "ISGYO.IS",  "name": "İş GYO",                    "sector": "Cam/Çelik"},
    {"ticker": "KLMSN.IS",  "name": "Klimasan",                  "sector": "Cam/Çelik"},
    {"ticker": "ERBOS.IS",  "name": "Erbosan",                   "sector": "Cam/Çelik"},

    # ── Çimento ──────────────────────────────────────────────────────────────
    {"ticker": "CIMSA.IS",  "name": "Çimsa Çimento",             "sector": "Çimento"},
    {"ticker": "BUCIM.IS",  "name": "Bursa Çimento",             "sector": "Çimento"},
    {"ticker": "KONYA.IS",  "name": "Konya Çimento",             "sector": "Çimento"},
    {"ticker": "AFYON.IS",  "name": "Afyon Çimento",             "sector": "Çimento"},
    {"ticker": "GOLTS.IS",  "name": "Göltaş Çimento",            "sector": "Çimento"},

    # ── Telekomünikasyon ─────────────────────────────────────────────────────
    {"ticker": "TCELL.IS",  "name": "Turkcell",                  "sector": "Telekomünikasyon"},
    {"ticker": "TTKOM.IS",  "name": "Türk Telekom",              "sector": "Telekomünikasyon"},

    # ── Havacılık / Ulaşım ───────────────────────────────────────────────────
    {"ticker": "THYAO.IS",  "name": "Türk Hava Yolları",         "sector": "Havacılık"},
    {"ticker": "PGSUS.IS",  "name": "Pegasus Hava Taşımacılığı", "sector": "Havacılık"},
    {"ticker": "CLEBI.IS",  "name": "Çelebi Havacılık",          "sector": "Havacılık"},
    {"ticker": "TAVHL.IS",  "name": "TAV Havalimanları",         "sector": "Havacılık"},
    {"ticker": "LOGO.IS",   "name": "Logo Yazılım",              "sector": "Havacılık"},

    # ── İnşaat / GYO ─────────────────────────────────────────────────────────
    {"ticker": "ALGYO.IS",  "name": "Alarko GYO",                "sector": "İnşaat/GYO"},
    {"ticker": "TRGYO.IS",  "name": "Torunlar GYO",              "sector": "İnşaat/GYO"},
    {"ticker": "HLGYO.IS",  "name": "Halk GYO",                  "sector": "İnşaat/GYO"},
    {"ticker": "EKGYO.IS",  "name": "Emlak Konut GYO",           "sector": "İnşaat/GYO"},
    {"ticker": "SNGYO.IS",  "name": "Sinpaş GYO",                "sector": "İnşaat/GYO"},
    {"ticker": "ZRGYO.IS",  "name": "Ziraat GYO",                "sector": "İnşaat/GYO"},

    # ── Sigorta / Finansal ───────────────────────────────────────────────────
    {"ticker": "ANSGR.IS",  "name": "Anadolu Sigorta",           "sector": "Sigorta"},
    {"ticker": "AKGRT.IS",  "name": "Aksigorta",                 "sector": "Sigorta"},
    {"ticker": "RAYSG.IS",  "name": "Ray Sigorta",               "sector": "Sigorta"},

    # ── Teknoloji ────────────────────────────────────────────────────────────
    {"ticker": "NETAS.IS",  "name": "Netaş Telekomunikasyon",    "sector": "Teknoloji"},
    {"ticker": "ARENA.IS",  "name": "Arena Bilgisayar",          "sector": "Teknoloji"},
    {"ticker": "INDES.IS",  "name": "Index Grup",                "sector": "Teknoloji"},
    {"ticker": "LINK.IS",   "name": "Link Bilgisayar",           "sector": "Teknoloji"},
    {"ticker": "KAREL.IS",  "name": "Karel Elektronik",          "sector": "Teknoloji"},
    {"ticker": "DGATE.IS",  "name": "Datagate Bilgisayar",       "sector": "Teknoloji"},
    {"ticker": "KONTR.IS",  "name": "Kontrolmatik",              "sector": "Teknoloji"},
    {"ticker": "VESBE.IS",  "name": "Vestel Beyaz Eşya",         "sector": "Teknoloji"},
    {"ticker": "VESTL.IS",  "name": "Vestel Elektronik",         "sector": "Teknoloji"},

    # ── Gıda / İçecek ────────────────────────────────────────────────────────
    {"ticker": "ULKER.IS",  "name": "Ülker Bisküvi",             "sector": "Gıda"},
    {"ticker": "TATGD.IS",  "name": "TAT Gıda",                  "sector": "Gıda"},
    {"ticker": "AEFES.IS",  "name": "Anadolu Efes",              "sector": "Gıda"},
    {"ticker": "CCOLA.IS",  "name": "Coca-Cola İçecek",          "sector": "Gıda"},
    {"ticker": "BANVT.IS",  "name": "Banvit",                    "sector": "Gıda"},
    {"ticker": "PENGD.IS",  "name": "Penguen Gıda",              "sector": "Gıda"},
    {"ticker": "PNSUT.IS",  "name": "Pınar Süt",                 "sector": "Gıda"},
    {"ticker": "TBORG.IS",  "name": "Türk Tuborg",               "sector": "Gıda"},

    # ── İlaç / Sağlık ────────────────────────────────────────────────────────
    {"ticker": "ECILC.IS",  "name": "Eczacıbaşı İlaç",           "sector": "İlaç/Sağlık"},
    {"ticker": "BFREN.IS",  "name": "Brembo Fren",               "sector": "İlaç/Sağlık"},
    {"ticker": "MPARK.IS",  "name": "Medical Park",              "sector": "İlaç/Sağlık"},

    # ── Kimya / Petrokimya ───────────────────────────────────────────────────
    {"ticker": "PETKM.IS",  "name": "Petkim",                    "sector": "Kimya"},
    {"ticker": "AKCNS.IS",  "name": "Akçansa",                   "sector": "Kimya"},
    {"ticker": "BRKVY.IS",  "name": "Brisa",                     "sector": "Kimya"},
    {"ticker": "BRISA.IS",  "name": "Brisa Bridgestone",         "sector": "Kimya"},
    {"ticker": "SASA.IS",   "name": "Sasa Polyester",            "sector": "Kimya"},
    {"ticker": "SODA.IS",   "name": "Soda Sanayii",              "sector": "Kimya"},
    {"ticker": "KORDS.IS",  "name": "Kordsa",                    "sector": "Kimya"},
    {"ticker": "HEKTS.IS",  "name": "Hektaş",                    "sector": "Kimya"},

    # ── Madencilik ───────────────────────────────────────────────────────────
    {"ticker": "MAALT.IS",  "name": "Marmaris Altın",            "sector": "Madencilik"},

    # ── Spor ─────────────────────────────────────────────────────────────────
    {"ticker": "FENER.IS",  "name": "Fenerbahçe",                "sector": "Spor"},
    {"ticker": "BJKAS.IS",  "name": "Beşiktaş",                  "sector": "Spor"},
    {"ticker": "GSRAY.IS",  "name": "Galatasaray",               "sector": "Spor"},
]

# Convenience: flat list of ticker symbols only
TICKER_SYMBOLS: list[str] = [t["ticker"] for t in BIST_TICKERS]

# Lookup: ticker → metadata dict
TICKER_MAP: dict[str, dict] = {t["ticker"]: t for t in BIST_TICKERS}

# All unique sectors present in the list
ALL_SECTORS: list[str] = sorted({t["sector"] for t in BIST_TICKERS})
