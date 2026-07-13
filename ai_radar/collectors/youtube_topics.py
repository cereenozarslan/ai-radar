"""YouTube Data API v3 üzerinden takip edilen konularla ilgili videoları toplar.

Resmi, ücretsiz bir Google API'si (günlük 10.000 birim kota; bir arama
isteği ~100 birim, istatistik isteği ~1 birim — konu başına toplam ~101
birim, kotanın çok altında). Ödeme gerekmez, sadece bir Google Cloud
projesinde etkinleştirilmiş bir API anahtarı yeterli.
"""

from datetime import datetime, timedelta, timezone

import requests

from ai_radar.config import config

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

MAX_RESULTS = 15
RECENT_DAYS = 30  # "güncel" kabul edilen pencere


def _published_after(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def search_video_ids(topic: str, max_results: int = MAX_RESULTS, days: int = RECENT_DAYS) -> list[str]:
    """Bir konuyla ilgili, son `days` gün içinde yayımlanmış videoların id'lerini arar."""
    resp = requests.get(
        SEARCH_URL,
        params={
            "part": "snippet",
            "q": topic,
            "type": "video",
            "order": "viewCount",
            "maxResults": max_results,
            "publishedAfter": _published_after(days),
            "relevanceLanguage": "tr",
            "key": config.YOUTUBE_API_KEY,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        item["id"]["videoId"]
        for item in data.get("items", [])
        if item.get("id", {}).get("videoId")
    ]


def fetch_video_stats(video_ids: list[str]) -> list[dict]:
    """Verilen video id'leri için başlık/istatistik bilgisini (tek istekte) çeker."""
    if not video_ids:
        return []
    resp = requests.get(
        VIDEOS_URL,
        params={
            "part": "snippet,statistics",
            "id": ",".join(video_ids),
            "key": config.YOUTUBE_API_KEY,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def compute_engagement_score(stats: dict) -> int:
    """Sadece izlenmeye göre sıralamak "viral ama etkileşimsiz" videoları öne
    çıkarabiliyor. Beğeni/yorum, bir tıklamadan (izlenme) çok daha "pahalı"
    bir etkileşim biçimi olduğu için ağırlıkları belirgin şekilde yüksek —
    böylece gerçekten etkileşimi yüksek videolar, sadece çok izlenmiş
    videuların önüne geçebiliyor."""
    views = int(stats.get("viewCount", 0) or 0)
    likes = int(stats.get("likeCount", 0) or 0)
    comments = int(stats.get("commentCount", 0) or 0)
    return views + likes * 100 + comments * 200


def parse_videos(raw_items: list[dict], topic: str) -> list[dict]:
    """Ham videos.list kayıtlarını topic_videos şemasına uygun listeye çevirir.

    Sonuç, etkileşim skoruna göre (en yüksekten en düşüğe) sıralı döner.
    """
    items = []
    for item in raw_items:
        video_id = item.get("id")
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        if not video_id or not snippet.get("title"):
            continue

        thumbnails = snippet.get("thumbnails") or {}
        thumb = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}

        items.append({
            "topic": topic,
            "video_id": video_id,
            "title": snippet["title"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "channel_title": snippet.get("channelTitle"),
            "published_at": snippet.get("publishedAt"),
            "image_url": thumb.get("url"),
            "view_count": int(stats.get("viewCount", 0) or 0),
            "like_count": int(stats.get("likeCount", 0) or 0),
            "comment_count": int(stats.get("commentCount", 0) or 0),
            "engagement_score": compute_engagement_score(stats),
        })

    items.sort(key=lambda v: v["engagement_score"], reverse=True)
    return items


def collect_for_topic(topic: str) -> list[dict]:
    """Bir konu için en alakalı/güncel videoları toplar (etkileşime göre sıralı)."""
    video_ids = search_video_ids(topic)
    raw_items = fetch_video_stats(video_ids)
    return parse_videos(raw_items, topic)
