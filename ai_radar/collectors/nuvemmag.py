"""NuvemMag (nuvemmag.com) Türkçe teknoloji/AI haber sitesini toplar.

Resmi bir API'si yok, bu yüzden ana sayfa HTML olarak çekilip ayrıştırılıyor
(GitHub Trending toplayıcısında yaptığımız gibi). Anahtar/kimlik doğrulama gerekmez.
"""

import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from ai_radar.collectors.parsing import parse_count

BASE_URL = "https://nuvemmag.com/"
HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)"}

_RELATIVE_TIME_UNITS = {
    "dakika": "minutes",
    "saat": "hours",
    "gün": "days",
}


def fetch_html(url: str = BASE_URL) -> str:
    """Ana sayfanın ham HTML'ini döner."""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


def parse_relative_time(text: str) -> str | None:
    """'14 saat önce', '2 gün önce' gibi göreli zaman ifadelerini ISO 8601'e çevirir.

    Site mutlak tarih değil göreli süre gösteriyor; bu yüzden sonuç
    işlendiği ana göre yaklaşık bir zaman damgasıdır.
    """
    match = re.search(r"(\d+)\s*(dakika|saat|gün)", text.lower())
    if not match:
        return None

    amount = int(match.group(1))
    unit_key = _RELATIVE_TIME_UNITS[match.group(2)]
    delta = timedelta(**{unit_key: amount})
    return (datetime.now(timezone.utc) - delta).isoformat()


def parse_articles(html: str) -> list[dict]:
    """Ana sayfadaki 'Son Yazılar' listesini items şemasına uygun kayıtlara çevirir."""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for article in soup.select("article.uck-card-list"):
        headline = article.select_one("h3.headline a")
        if not headline or not headline.get("href"):
            continue

        excerpt = article.select_one(".uck-card--content > p")
        date_tag = article.select_one("span.date")
        author_tag = article.select_one(".entry_author a")
        # Görsel lazy-load ile yükleniyor; gerçek adres src'de değil data-src'de
        image_tag = article.select_one(".uck-card--image img")
        views_tag = article.select_one(".post-views")

        items.append({
            "source": "nuvemmag",
            "title": headline.get_text(strip=True),
            "url": headline["href"],
            "content": excerpt.get_text(strip=True) if excerpt else None,
            "author": author_tag.get_text(strip=True) if author_tag else None,
            "published_at": parse_relative_time(date_tag.get_text(strip=True)) if date_tag else None,
            "image_url": image_tag.get("data-src") if image_tag else None,
            # Sitenin kendi "görüntülenme" sayısı; "en popüler" sıralaması için kullanılıyor
            "popularity": parse_count(views_tag.get_text(strip=True)) if views_tag else None,
        })

    return items


def collect() -> list[dict]:
    """Ana sayfadaki güncel yazıları toplayıp items şemasına uygun listeye çevirir."""
    return parse_articles(fetch_html())


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected = collect()
    added = save_items(collected)
    print(f"NuvemMag: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
