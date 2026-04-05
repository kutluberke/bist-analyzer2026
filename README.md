# BIST Radar 📡

Türk borsası (BIST) hisse tarama ve yapay zeka analiz aracı. yfinance üzerinden gerçek zamanlı veriler, kural tabanlı sinyal skorlaması ve Groq AI ile Türkçe hisse analizi sunar.

---

## Özellikler

| Özellik | Açıklama |
|---|---|
| **94 hisse** | BIST100 sembollerini `.IS` uzantısıyla yfinance'ten çeker |
| **Sinyal skorlaması** | Momentum, Değerleme, Hacim ve Volatilite bileşenlerinden 0–100 skor üretir |
| **🟢 AL / 🟡 BEKLE / 🔴 SAT** | Skor eşiklerine göre otomatik sinyal atar |
| **7 filtre** | Sektör, piyasa değeri, F/K, 52H getiri, hacim, sinyal |
| **Detay görünümü** | 6 aylık mum grafiği + SMA20/50 + hacim + radar chart + 8 metrik kart |
| **AI Analiz** | Groq (llama-3.3-70b-versatile) ile Türkçe Güçlü Yönler / Riskler / Öneri |
| **CSV dışa aktarım** | Filtrelenmiş tabloyu UTF-8 BOM CSV olarak indir |

---

## Kurulum

### 1. Gereksinimleri yükle

```bash
cd bist_radar
pip install -r requirements.txt
```

Python 3.10+ gereklidir.

### 2. API anahtarını ayarla

`.env` dosyasını düzenle:

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

Ücretsiz Groq API anahtarı: [console.groq.com](https://console.groq.com)

### 3. Uygulamayı başlat

```bash
streamlit run app.py
```

Tarayıcı otomatik açılır: `http://localhost:8501`

---

## Proje Yapısı

```
bist_radar/
├── app.py                      # Ana Streamlit giriş noktası
├── modules/
│   ├── data_fetcher.py         # yfinance veri çekme (TTL=1sa cache)
│   ├── screener.py             # Filtreleme ve skorlama mantığı
│   ├── analyzer.py             # Groq AI analizi
│   └── charts.py               # Plotly grafik oluşturucuları
├── data/
│   └── bist_tickers.py         # 94 BIST sembolü + sektör eşlemeleri
├── .streamlit/
│   └── config.toml             # Karanlık tema ve sunucu ayarları
├── .env                        # GROQ_API_KEY (git'e ekleme!)
├── .gitignore
└── requirements.txt
```

---

## Skorlama Modeli

Her hisse 0–100 arası puan alır, 4 bileşenden oluşur:

| Bileşen | Ağırlık | Hesaplama |
|---|---|---|
| **Momentum** | %30 | 52 haftalık getirinin sektör emsalleri arasındaki yüzdelik sırası |
| **Değerleme** | %30 | F/K oranının sektör medyanına göre ters yüzdelik sırası (düşük F/K = iyi) |
| **Hacim Trendi** | %20 | Son 10 günlük hacim ÷ 90 günlük ortalama → [0.25×–2.5×] → [0–100] |
| **Düşük Volatilite** | %20 | Yıllık getirilerin standart sapmasının ters yüzdelik sırası |

**Sinyal eşikleri:**
- `≥ 65` → 🟢 AL
- `40–64` → 🟡 BEKLE
- `< 40` → 🔴 SAT

> Skorlama tüm evren üzerinde yapılır ve ardından filtreler uygulanır; bu sayede F/K filtresini açtığında sektör yüzdelikleri bozulmaz.

---

## Veri Kaynakları ve Güncelleme Sıklığı

| Veri | Kaynak | Cache TTL |
|---|---|---|
| Hisse bilgileri (fiyat, F/K, piyasa değeri…) | yfinance `.info` | 1 saat |
| Fiyat geçmişi (OHLCV) | yfinance `download()` | 1 saat |
| 52 haftalık getiri | Fiyat geçmişinden hesaplanır | 1 saat |
| Hacim oranı | Fiyat geçmişinden hesaplanır | 1 saat |
| Volatilite | Log getirilerin std × √252 | 1 saat |

Sol menüdeki **🔄 Verileri Yenile** butonu tüm cache'i temizler ve veriyi yeniden çeker.

---

## Hata Durumları

| Durum | Uygulama davranışı |
|---|---|
| Tek sembol için veri yok | Sessizce atlanır; yükleme sonunda uyarı gösterilir |
| Tüm semboller için veri yok | `st.error` ile durdurulur, yenileme önerilir |
| Groq API anahtarı eksik | Önyükleme uyarısı gösterilir; AI butonu çalışmaz |
| Groq API çağrısı başarısız | Fallback mesajı döner, uygulama çökmez |
| Fiyat geçmişi boş | Grafik "veri yok" mesajıyla gösterilir |
| Skor hesaplama hatası | İlgili hisse 50 puan (nötr) alır |

---

## Geliştirme Notları

### Yeni hisse eklemek

`data/bist_tickers.py` dosyasına `BIST_TICKERS` listesine ekle:

```python
{"ticker": "SMRTG.IS", "name": "Smart Güneş", "sector": "Enerji"},
```

### Skor ağırlıklarını değiştirmek

`modules/screener.py` dosyasının başındaki sabitler:

```python
WEIGHT_MOMENTUM   = 0.30
WEIGHT_VALUATION  = 0.30
WEIGHT_VOLUME     = 0.20
WEIGHT_VOLATILITY = 0.20
```

### Groq modelini değiştirmek

`modules/analyzer.py`:

```python
_MODEL = "llama-3.3-70b-versatile"   # veya "mixtral-8x7b-32768"
```

---

## Uyarı

Bu araç yatırım tavsiyesi vermez. Tüm yatırım kararları yatırımcının kendi sorumluluğundadır. Veriler gecikmeli veya eksik olabilir.
