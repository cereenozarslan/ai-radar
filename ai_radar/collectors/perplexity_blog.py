"""Perplexity AI'nin resmi blog sayfasını (perplexity.ai/hub/blog) toplar.

Perplexity'nin sitesi Framer (no-code site builder) ile yapılmış ve RSS
sunmuyor. İyi haber: Framer her yazı için gerçek bir <time datetime="..."ISO>
etiketi kullanıyor — bu yüzden Anthropic/Meta'daki gibi metin tarihi
ayrıştırmaya (ör. "Jul 9, 2026" -> datetime) gerek yok, tarih zaten ISO 8601
formatında hazır duruyor. Her <time>'ın en yakın <a> atasını buluyoruz; o
linkin href'i yazının adresi, içindeki h6 başlığı, img'i de görseli veriyor.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.perplexity.ai/hub/blog"
HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)"}

MAX_AGE_DAYS = 60


def fetch_html(url: str = BASE_URL) -> str:
    """Blog sayfasının ham HTML'ini döner."""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


def parse_blog(html: str, base_url: str = BASE_URL, max_age_days: int | None = MAX_AGE_DAYS) -> list[dict]:
    """Blog sayfasındaki yazıları items şemasına uygun listeye çevirir."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days) if max_age_days else None
    soup = BeautifulSoup(html, "html.parser")
    seen_urls: set[str] = set()
    items = []

    for time_tag in soup.find_all("time"):
        link_tag = time_tag.find_parent("a")
        if not link_tag or not link_tag.get("href"):
            continue
        url = urljoin(base_url, link_tag["href"])
        if url in seen_urls:
            continue

        heading = link_tag.find("h6")
        if not heading:
            continue
        seen_urls.add(url)

        published_at = None
        raw_datetime = time_tag.get("datetime")
        if raw_datetime:
            published_at = raw_datetime.replace("Z", "+00:00")
        if cutoff and published_at and datetime.fromisoformat(published_at) < cutoff:
            continue

        image_tag = link_tag.find("img")

        items.append({
            "source": "official_blog",
            "title": heading.get_text(strip=True),
            "url": url,
            "content": None,
            "author": "Perplexity",
            "published_at": published_at,
            "image_url": image_tag.get("src") if image_tag else None,
            "popularity": None,
        })

    return items


def collect() -> list[dict]:
    """Perplexity blogundaki güncel yazıları toplar."""
    return parse_blog(fetch_html())


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected = collect()
    added = save_items(collected)
    print(f"Perplexity: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
