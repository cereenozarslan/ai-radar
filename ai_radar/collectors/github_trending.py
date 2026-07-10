"""GitHub Trending sayfasını toplar.

GitHub'ın resmi bir "trending" API'si yok, bu yüzden https://github.com/trending
sayfası HTML olarak çekilip ayrıştırılıyor. Anahtar/kimlik doğrulama gerekmez.
"""

import requests
from bs4 import BeautifulSoup

TRENDING_URL = "https://github.com/trending"
# GitHub, User-Agent olmayan isteklere bazen farklı davranabiliyor
HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)"}


def fetch_trending_html(language: str | None = None, since: str = "daily") -> str:
    """Trending sayfasının ham HTML'ini döner."""
    url = f"{TRENDING_URL}/{language}" if language else TRENDING_URL
    resp = requests.get(url, params={"since": since}, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


def parse_trending(html: str) -> list[dict]:
    """Trending sayfası HTML'ini items şemasına uygun kayıt listesine çevirir."""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for article in soup.select("article.Box-row"):
        link = article.select_one("h2 a")
        if not link or not link.get("href"):
            continue

        full_name = link["href"].strip("/")  # "owner/repo" formatı
        if "/" not in full_name:
            continue

        description_tag = article.select_one("p")
        description = description_tag.get_text(strip=True) if description_tag else None

        owner = full_name.split("/")[0]

        items.append({
            "source": "github_trending",
            "title": full_name,
            "url": f"https://github.com/{full_name}",
            "content": description,
            "author": owner,
            "published_at": None,
            # GitHub'ın belgelenmiş kısayolu: kullanıcı adı + ".png" avatar görselini döner
            "image_url": f"https://github.com/{owner}.png",
        })

    return items


def collect(language: str | None = None, since: str = "daily") -> list[dict]:
    """Trending repoları toplayıp items şemasına uygun listeye çevirir."""
    html = fetch_trending_html(language, since)
    return parse_trending(html)


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected = collect()
    added = save_items(collected)
    print(f"GitHub Trending: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
