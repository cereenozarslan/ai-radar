"""Resmi YZ şirketi blog/haber RSS akışlarını toplar.

RSS, bir sitenin "içeriğimi makine-okunur şekilde paylaşıyorum" diye
kasıtlı sunduğu standart bir format (XML) — NuvemMag/GitHub Trending'de
yaptığımız gibi HTML'i parçalamaya (scraping) çalışmıyoruz; siteler bize
zaten yapılandırılmış veri veriyor, bu yüzden bu koleksiyoncu çok daha
sağlam (site "tasarımı" değişse de RSS formatı değişmez).

feedparser kütüphanesi RSS 2.0 ile Atom arasındaki farkları kendisi
normalize ediyor (ikisini de aynı `entry.title`/`entry.link` gibi ortak
alanlarla okuyabiliyoruz).
"""

from datetime import datetime, timedelta, timezone

import feedparser
import requests

HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)"}

# OpenAI'ın akışı 2015'e kadar giden TÜM arşivi (1000+ yazı) döndürüyor —
# bir haber toplayıcısı için bu kadar eski içerik gürültüden başka bir şey
# değil, bu yüzden sadece son N günü tutuyoruz (diğer koleksiyoncularda
# kullandığımız "güncellik penceresi" ile aynı mantık).
MAX_AGE_DAYS = 60

# Her şirketin RSS akışı; "author" alanında hangi şirketten geldiğini
# gösteriyoruz (hepsi tek bir "official_blog" kaynağı altında birleşiyor).
FEEDS = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
}


def fetch_feed_text(feed_url: str) -> str:
    """Bir RSS akışının ham XML metnini çeker."""
    resp = requests.get(feed_url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


def _parse_published(entry) -> str | None:
    parsed_time = entry.get("published_parsed")
    if not parsed_time:
        return None
    return datetime(*parsed_time[:6], tzinfo=timezone.utc).isoformat()


def _extract_image(entry) -> str | None:
    """Bazı akışlar (örn. DeepMind) Media RSS uzantısıyla küçük resim veriyor;
    vermeyenlerde (örn. OpenAI) None dönüyoruz — arayüz görselsiz kaydı da
    zaten düzgün gösteriyor."""
    thumbnails = entry.get("media_thumbnail")
    if thumbnails:
        return thumbnails[0].get("url")
    return None


def parse_feed(feed_text: str, company: str, max_age_days: int | None = MAX_AGE_DAYS) -> list[dict]:
    """Ham RSS/Atom metnini items şemasına uygun listeye çevirir.

    max_age_days verilirse, o kadar günden eski (pubDate'i olan) kayıtlar
    atlanır. Tarihi hiç okunamayan kayıtlar güvenli tarafta kalmak için
    yine de dahil edilir.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days) if max_age_days else None
    parsed = feedparser.parse(feed_text)
    items = []
    for entry in parsed.entries:
        title = entry.get("title")
        link = entry.get("link")
        if not title or not link:
            continue

        published_at = _parse_published(entry)
        if cutoff and published_at and datetime.fromisoformat(published_at) < cutoff:
            continue

        items.append({
            "source": "official_blog",
            "title": title,
            "url": link,
            "content": entry.get("summary"),
            "author": company,
            "published_at": published_at,
            "image_url": _extract_image(entry),
            "popularity": None,
        })
    return items


def collect() -> list[dict]:
    """Tüm şirketlerin RSS akışlarındaki yazıları toplar."""
    items = []
    for company, feed_url in FEEDS.items():
        feed_text = fetch_feed_text(feed_url)
        items.extend(parse_feed(feed_text, company))
    return items


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected = collect()
    added = save_items(collected)
    print(f"Resmi Bloglar: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
