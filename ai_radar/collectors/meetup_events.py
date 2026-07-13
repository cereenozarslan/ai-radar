"""meetup.com üzerinden Türkiye'deki yapay zeka etkinliklerini toplar.

Resmi bir API'si yok ama arama sayfası sunucu tarafında render ediliyor ve
sayfaya gömülü `__NEXT_DATA__` (Next.js) JSON'ı içinde Apollo GraphQL
önbelleği olarak tüm etkinlik/topluluk/fotoğraf verisini taşıyor — bunu
ayrıştırıyoruz.

İki ayrı strateji birleştiriliyor:
1. Şehir + anahtar kelime araması: SADECE FİZİKSEL (yüz yüze) etkinlikler,
   ve venue.country alanı "tr" olanlar. (Meetup'ın konum filtresi coğrafi
   yakınlığa göre çalışıyor; komşu ülkelerden alakasız sonuçlar da
   sızabiliyor, bu yüzden ülkeyi ayrıca doğruluyoruz.) Ayrıca başlıkta YZ
   ile ilgili bir anahtar kelime geçmesi şart (Meetup'ın kendi araması
   bazen alakasız sonuçlar da döndürüyor).
2. Bilinen, tamamen YZ odaklı Türkiye topluluklarının (örn. Türkiye Yapay
   Zeka İnisiyatifi) KENDİ etkinlik sayfaları: bunlar online olsa da
   doğrudan dahil edilir, ayrıca anahtar kelime filtresi gerekmez.
"""

import json
import re
import time

import httpx

from ai_radar.collectors.kommunity_events import is_ai_related

BASE_URL = "https://www.meetup.com"
HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)"}

CITIES = ["Istanbul", "Ankara", "Izmir", "Bursa", "Antalya"]
SEARCH_KEYWORDS = ["yapay zeka", "artificial intelligence", "machine learning"]

# Bütünüyle yapay zeka odaklı, bilinen Türkiye toplulukları: bunların TÜM
# etkinlikleri (online dahil) alınır. Meetup URL'lerindeki topluluk kısa adı
# (urlname) — büyük/küçük harf ve Türkçe karakterler dahil birebir kopyalanmalı.
KNOWN_AI_COMMUNITY_GROUPS = ["Turkiye-Yapay-Zeka-İnisiyatifi"]

REQUEST_DELAY_SECONDS = 0.3

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def extract_apollo_state(html: str) -> dict:
    """Sayfa HTML'inden Next.js'in gömülü Apollo GraphQL önbelleğini çıkarır."""
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return data.get("props", {}).get("pageProps", {}).get("__APOLLO_STATE__", {}) or {}


def _resolve_ref(apollo: dict, holder: dict | None, field: str) -> dict:
    """Apollo'nun {"__ref": "Tip:id"} referanslarını gerçek nesneye çevirir."""
    ref = (holder or {}).get(field)
    if not isinstance(ref, dict):
        return {}
    key = ref.get("__ref")
    resolved = apollo.get(key) if key else None
    return resolved or {}


def _event_to_item(event: dict, apollo: dict) -> dict | None:
    """Bir Apollo Event nesnesini items şemasına uygun kayda çevirir."""
    title = event.get("title")
    url = event.get("eventUrl")
    date_time = event.get("dateTime")
    if not title or not url or not date_time:
        return None

    group = _resolve_ref(apollo, event, "group")
    photo = _resolve_ref(apollo, event, "featuredEventPhoto")
    venue = event.get("venue") or {}
    is_online = event.get("eventType") == "ONLINE"

    location_bits = [] if is_online else [b for b in (venue.get("name"), venue.get("city")) if b]
    content = " · ".join(location_bits) if location_bits else ("Online" if is_online else None)

    return {
        "source": "meetup_events",
        "title": title,
        "url": url,
        "content": content,
        "author": group.get("name"),
        "published_at": date_time,
        "image_url": photo.get("highResUrl"),
        "popularity": None,
        "is_online": is_online,
    }


def parse_search_events(apollo: dict) -> list[dict]:
    """Şehir/anahtar kelime aramasından gelen Apollo verisini işler.

    Sadece Türkiye'de (venue.country == "tr") gerçekleşen FİZİKSEL etkinlikler
    VE başlığında YZ ile ilgili bir anahtar kelime geçenler dahil edilir.
    """
    items = []
    for key, event in apollo.items():
        if not key.startswith("Event:") or not event.get("title"):
            continue
        if event.get("eventType") != "PHYSICAL":
            continue
        venue = event.get("venue") or {}
        if (venue.get("country") or "").strip().lower() != "tr":
            continue
        if not is_ai_related(event["title"]):
            continue
        item = _event_to_item(event, apollo)
        if item:
            items.append(item)
    return items


def parse_group_events(apollo: dict) -> list[dict]:
    """Bilinen bir YZ topluluğunun kendi sayfasından gelen tüm etkinlikleri
    (online dahil, ayrıca anahtar kelime filtresi olmadan) işler."""
    items = []
    for key, event in apollo.items():
        if not key.startswith("Event:") or not event.get("title"):
            continue
        item = _event_to_item(event, apollo)
        if item:
            items.append(item)
    return items


def fetch_search_page(city: str, keyword: str) -> dict:
    # requests/urllib3, bazı Meetup URL'lerinde (Türkçe karakter içeren yönlendirme
    # hedeflerinde) sonsuz yönlendirme döngüsüne giriyor (kütüphaneye özgü bir
    # yüzde-kodlama uyuşmazlığı); httpx aynı isteklerde sorunsuz çalışıyor.
    resp = httpx.get(
        f"{BASE_URL}/find/",
        params={"location": f"tr--{city}", "keywords": keyword},
        headers=HEADERS,
        timeout=10,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return extract_apollo_state(resp.text)


def fetch_group_page(group_slug: str) -> dict:
    resp = httpx.get(f"{BASE_URL}/{group_slug}/events/", headers=HEADERS, timeout=10, follow_redirects=True)
    resp.raise_for_status()
    return extract_apollo_state(resp.text)


def collect() -> list[dict]:
    """Türkiye'deki yaklaşan yapay zeka etkinliklerini meetup.com'dan toplar."""
    collected: dict[str, dict] = {}

    for city in CITIES:
        for keyword in SEARCH_KEYWORDS:
            apollo = fetch_search_page(city, keyword)
            for item in parse_search_events(apollo):
                collected[item["url"]] = item
            time.sleep(REQUEST_DELAY_SECONDS)

    for group_slug in KNOWN_AI_COMMUNITY_GROUPS:
        apollo = fetch_group_page(group_slug)
        for item in parse_group_events(apollo):
            collected[item["url"]] = item
        time.sleep(REQUEST_DELAY_SECONDS)

    return list(collected.values())


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected_items = collect()
    added = save_items(collected_items)
    print(f"Meetup Etkinlikler: {len(collected_items)} kayıt toplandı, {added} yeni kayıt eklendi.")
