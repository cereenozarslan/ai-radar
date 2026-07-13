"""YouTube Data API v3 üzerinden takip edilen kanalların son videolarını toplar.

youtube_topics.py'deki konu aramasından farklı olarak burada arama
(search.list, ~100 birim) değil, doğrudan kanalın "uploads" oynatma listesi
(playlistItems.list, ~1 birim) kullanılıyor — çok daha ucuz, çünkü zaten
hangi kanalı istediğimizi (kullanıcının takip listesi) biliyoruz.
"""

import requests

from ai_radar.collectors.youtube_topics import fetch_video_stats
from ai_radar.config import config

CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"

MAX_RESULTS = 15


def resolve_channel(handle: str) -> dict | None:
    """Bir @handle'ı kanal id'sine, "uploads" oynatma listesine ve görünen ada çözer.

    Kanal bulunamazsa None döner (çağıran taraf bunu "geçersiz handle" olarak yorumlar).
    """
    handle = handle.strip()
    if not handle.startswith("@"):
        handle = "@" + handle

    resp = requests.get(
        CHANNELS_URL,
        params={
            "part": "snippet,contentDetails",
            "forHandle": handle,
            "key": config.YOUTUBE_API_KEY,
        },
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None

    channel = items[0]
    snippet = channel.get("snippet") or {}
    thumbnails = snippet.get("thumbnails") or {}
    thumb = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
    uploads_playlist_id = (channel.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads_playlist_id:
        return None

    return {
        "channel_id": channel["id"],
        "uploads_playlist_id": uploads_playlist_id,
        "display_name": snippet.get("title") or handle,
        "thumbnail_url": thumb.get("url"),
    }


def fetch_latest_video_ids(uploads_playlist_id: str, max_results: int = MAX_RESULTS) -> list[str]:
    """Bir kanalın 'uploads' oynatma listesinden en son videoların id'lerini çeker."""
    resp = requests.get(
        PLAYLIST_ITEMS_URL,
        params={
            "part": "contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": max_results,
            "key": config.YOUTUBE_API_KEY,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return [
        item["contentDetails"]["videoId"]
        for item in resp.json().get("items", [])
        if item.get("contentDetails", {}).get("videoId")
    ]


def parse_channel_videos(raw_items: list[dict], channel_display_name: str) -> list[dict]:
    """videos.list ham kayıtlarını items şemasına uygun listeye çevirir (source="youtube_channel")."""
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
            "source": "youtube_channel",
            "title": snippet["title"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "content": snippet.get("description"),
            "author": channel_display_name,
            "published_at": snippet.get("publishedAt"),
            "image_url": thumb.get("url"),
            "popularity": int(stats.get("viewCount", 0) or 0),
        })
    return items


def collect_for_channel(uploads_playlist_id: str, display_name: str) -> list[dict]:
    """Bir kanalın en son videolarını toplayıp items şemasına uygun listeye çevirir."""
    video_ids = fetch_latest_video_ids(uploads_playlist_id)
    raw_items = fetch_video_stats(video_ids)
    return parse_channel_videos(raw_items, display_name)
