"""Hacker News resmi Firebase API'sinden en çok oy alan hikayeleri toplar.

API anahtarı gerekmez: https://github.com/HackerNews/API
"""

from datetime import datetime, timezone

import requests

HN_BASE_URL = "https://hacker-news.firebaseio.com/v0"
DEFAULT_LIMIT = 30


def fetch_top_story_ids(limit: int = DEFAULT_LIMIT) -> list[int]:
    """En çok oy alan hikayelerin id listesini döner."""
    resp = requests.get(f"{HN_BASE_URL}/topstories.json", timeout=10)
    resp.raise_for_status()
    return resp.json()[:limit]


def fetch_item(item_id: int) -> dict:
    """Tek bir öğenin (hikaye/yorum) ham verisini döner."""
    resp = requests.get(f"{HN_BASE_URL}/item/{item_id}.json", timeout=10)
    resp.raise_for_status()
    return resp.json()


def to_item_dict(raw: dict | None) -> dict | None:
    """HN'in ham JSON verisini items tablosu şemasına çevirir.

    'story' tipinde olmayan (yorum, iş ilanı vb.) veya silinmiş öğeler için None döner.
    """
    if not raw or raw.get("type") != "story" or not raw.get("title"):
        return None

    published_at = None
    if raw.get("time"):
        published_at = datetime.fromtimestamp(raw["time"], tz=timezone.utc).isoformat()

    return {
        "source": "hackernews",
        "title": raw["title"],
        # Ask HN gibi harici url'i olmayan gönderilerde HN sayfasının kendisini kullan
        "url": raw.get("url") or f"https://news.ycombinator.com/item?id={raw['id']}",
        "content": raw.get("text"),
        "author": raw.get("by"),
        "published_at": published_at,
    }


def collect(limit: int = DEFAULT_LIMIT) -> list[dict]:
    """En çok oy alan `limit` kadar hikayeyi toplayıp items şemasına uygun listeye çevirir."""
    items = []
    for item_id in fetch_top_story_ids(limit):
        parsed = to_item_dict(fetch_item(item_id))
        if parsed:
            items.append(parsed)
    return items


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected = collect()
    added = save_items(collected)
    print(f"Hacker News: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
