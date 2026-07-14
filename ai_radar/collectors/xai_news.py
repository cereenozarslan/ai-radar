"""xAI'nin (Grok) resmi haber sayfasını (x.ai/news) toplar.

xAI de RSS akışı sunmuyor, bu yüzden sayfa HTML olarak kazınıyor. xAI'nin
sitesi Tailwind (anlamlı, elle yazılmış utility class'lar) kullanıyor —
Anthropic/Meta'daki gibi derleme-hash'li class isimlerinden daha kararlı,
ama yine de RSS kadar garantili değil. Her haber kartı bir "/news/<slug>"
linki, kısa bir tarih metni ("Mon D, YYYY") ve bir başlık (h1/h2/h3'ten biri —
sayfanın en üstteki "öne çıkan" kartı diğerlerinden farklı bir başlık
etiketi kullanıyor) içeriyor.
"""

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://x.ai/news"
HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)"}

MAX_AGE_DAYS = 60

_LINK_PATTERN = re.compile(r"^/news/[a-z0-9-]+$")
_DATE_PATTERN = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}$")


def fetch_html(url: str = BASE_URL) -> str:
    """Haberler sayfasının ham HTML'ini döner."""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


def _find_date(link_tag) -> str | None:
    for div in link_tag.find_all("div"):
        text = div.get_text(strip=True)
        if _DATE_PATTERN.match(text):
            return text
    return None


def _parse_date(date_text: str) -> str | None:
    try:
        dt = datetime.strptime(date_text, "%b %d, %Y")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


def parse_news(html: str, base_url: str = BASE_URL, max_age_days: int | None = MAX_AGE_DAYS) -> list[dict]:
    """Haberler sayfasındaki yazıları items şemasına uygun listeye çevirir."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days) if max_age_days else None
    soup = BeautifulSoup(html, "html.parser")
    seen_urls: set[str] = set()
    items = []

    for link_tag in soup.find_all("a", href=True):
        href = link_tag["href"]
        if not _LINK_PATTERN.match(href):
            continue
        url = urljoin(base_url, href)
        if url in seen_urls:
            continue

        heading = link_tag.find(["h1", "h2", "h3"])
        date_text = _find_date(link_tag)
        if not heading or not date_text:
            continue
        seen_urls.add(url)

        published_at = _parse_date(date_text)
        if cutoff and published_at and datetime.fromisoformat(published_at) < cutoff:
            continue

        image_tag = link_tag.find("img")
        image_url = urljoin(base_url, image_tag["src"]) if image_tag and image_tag.get("src") else None

        items.append({
            "source": "official_blog",
            "title": heading.get_text(strip=True),
            "url": url,
            "content": None,
            "author": "xAI",
            "published_at": published_at,
            "image_url": image_url,
            "popularity": None,
        })

    return items


def collect() -> list[dict]:
    """xAI haberler sayfasındaki güncel yazıları toplar."""
    return parse_news(fetch_html())


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected = collect()
    added = save_items(collected)
    print(f"xAI: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
