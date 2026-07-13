"""coderspace.io etkinlikler sayfasını toplar.

Sayfaya gömülü schema.org JSON-LD (`<script type="application/ld+json">`)
bloklarını kullanıyoruz — kırılgan HTML class/id yapısına bağımlı scraping
yerine, sitenin kendi (SEO amaçlı) yapılandırılmış verisini okuyoruz.
"""

import json
import re

import requests

from ai_radar.collectors.kommunity_events import is_ai_related

EVENTS_URL = "https://coderspace.io/etkinlikler"
HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)"}

_JSONLD_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def extract_jsonld_events(html: str) -> list[dict]:
    """Sayfadaki application/ld+json bloklarından @type=Event olanları döner."""
    events = []
    for block in _JSONLD_RE.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Event":
            events.append(data)
    return events


def parse_events(raw_events: list[dict]) -> list[dict]:
    """Ham JSON-LD Event kayıtlarını items şemasına uygun listeye çevirir.

    Sadece başlığında yapay zeka ile ilgili bir anahtar kelime geçenler
    dahil edilir (Coderspace, stajyer programları/hackathonlar gibi
    YZ dışı birçok etkinlik de listeliyor).
    """
    items = []
    for event in raw_events:
        name = event.get("name") or ""
        location = event.get("location") or {}
        url = event.get("url") or location.get("url")
        if not url or not is_ai_related(name):
            continue

        organizer = event.get("organizer") or {}
        images = event.get("image")
        if isinstance(images, list) and images:
            image_url = images[-1]
        elif isinstance(images, str):
            image_url = images
        else:
            image_url = None

        is_online = "online" in (event.get("eventAttendanceMode") or "").lower()

        items.append({
            "source": "coderspace_events",
            "title": name,
            "url": url,
            "content": event.get("description"),
            "author": organizer.get("name"),
            "published_at": event.get("startDate"),
            "image_url": image_url,
            "popularity": None,
            "is_online": is_online,
        })
    return items


def collect() -> list[dict]:
    """coderspace.io/etkinlikler sayfasındaki yapay zeka etkinliklerini toplar."""
    resp = requests.get(EVENTS_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return parse_events(extract_jsonld_events(resp.text))


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected_items = collect()
    added = save_items(collected_items)
    print(f"Coderspace Etkinlikler: {len(collected_items)} kayıt toplandı, {added} yeni kayıt eklendi.")
