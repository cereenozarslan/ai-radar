# AI Radar

Yapay zeka dünyasındaki gelişmeleri tek yerde toplayan haber ve etkinlik takip sistemi.
Resmi blogları, GitHub trendlerini, YouTube kanallarını, X (Twitter) akışını ve Türkiye'deki
teknoloji etkinliklerini otomatik tarar; içerikleri puanlayıp bir web arayüzünde sunar.

## Ne yapar

- **14 farklı kaynaktan otomatik toplama** — Anthropic, OpenAI, Google DeepMind, xAI, Meta AI
  ve Perplexity resmi blogları; GitHub Trending; YouTube kanal ve konu takibi; X (Twitter);
  Kommunity, Meetup ve Coderspace etkinlikleri
- **Sinyal puanlama** (`signal_score.py`) — her içeriğe önem puanı vererek gürültüyü ayıklar
- **Konu trendi analizi** (`topic_trends.py`) — hangi başlıkların yükselişte olduğunu çıkarır
- **Doğal dil sorgu ayrıştırma** (`query_parser.py`) — arama cümlesini filtreye çevirir
- **FastAPI web arayüzü** — toplanan içerikleri tarayıcıda gösterir
- **SQLite veritabanı** — geçmiş içerikler saklanır, tekrar eden kayıtlar elenir

## Teknolojiler

Python · FastAPI · Uvicorn · SQLite · BeautifulSoup4 · feedparser · Tweepy · httpx · pytest

## Kurulum

```bash
git clone https://github.com/cereenozarslan/ai-radar.git
cd ai-radar
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # anahtarlarını doldur
```

### Gerekli anahtarlar

`.env.example` dosyası hangi değerlerin gerektiğini listeler:

| Anahtar | Ne için |
|---|---|
| `DATABASE_PATH` | SQLite dosyasının yolu |
| `X_BEARER_TOKEN` | X (Twitter) içeriklerini okumak için |
| `YOUTUBE_API_KEY` | YouTube kanal ve konu takibi için |

X ve YouTube anahtarları olmadan da çalışır — o kaynaklar atlanır, diğerleri toplanmaya devam eder.

## Çalıştırma

```bash
uvicorn ai_radar.web:app --reload
```

Ardından http://localhost:8000 adresini aç.

## Testler

```bash
pytest
```

Her toplayıcı (collector) için ayrı test dosyası vardır; kaynak sitelerin HTML yapısı
değiştiğinde hangi toplayıcının bozulduğu testlerden anlaşılır.

## Proje yapısı

```
ai_radar/
  collectors/     her kaynak için ayrı toplayıcı modül
  config.py       ayarlar ve .env okuma
  database.py     SQLite katmanı
  signal_score.py içerik puanlama
  topic_trends.py trend analizi
  web.py          FastAPI uygulaması
tests/            toplayıcı testleri
```

## Not

`.env` ve `data/` klasörü bilinçli olarak depoya dahil edilmemiştir — anahtarlar ve toplanan
veriler kişiseldir.
