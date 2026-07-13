"""kommunity.com üzerinden Türkiye'deki yapay zeka etkinliklerini toplar.

kommunity.com'un belgelenmiş/resmi bir API'si yok; sitenin kendi ön ucunun
kullandığı genel (kimlik doğrulama gerektirmeyen) JSON uç noktasını
(api.kommunity.com) kullanıyoruz. Bu uç nokta anahtar kelime araması
desteklemiyor ama şehre göre filtrelemeyi destekliyor ve sonuçları tarihe
göre artan sırada (en eskiden en yeniye) döndürüyor — bu yüzden şehir
başına SON birkaç sayfayı (yaklaşan etkinlikler) çekip başlıkta yapay zeka
ile ilgili bir anahtar kelime geçenleri kendimiz filtreliyoruz.
"""

import time
from datetime import datetime

import requests

API_URL = "https://api.kommunity.com/api/v1/events"
HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)", "Accept": "application/json"}

# kommunity.com'un "şehir" filtresi yalnızca tam eşleşen bir şehir adı bekliyor;
# ülke bazlı bir filtre olmadığı için bilinen büyük şehirleri tek tek tarıyoruz.
CITIES = ["Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Eskisehir", "Kocaeli"]

# Şehir başına son kaç sayfa çekilecek (sonuçlar tarihe göre artan sıralı
# olduğundan, listenin SONU en güncel/yaklaşan etkinlikleri içerir).
PAGES_FROM_END = 2

# İki istek arasında kısa bir bekleme: belgelenmemiş, kimlik doğrulamasız bu
# uç noktaya karşı nazik davranmak için (hız sınırına takılmamak).
REQUEST_DELAY_SECONDS = 0.2

_AI_KEYWORDS = [
    "yapay zeka", "artificial intelligence", "machine learning",
    "makine ogrenmesi", "derin ogrenme", "deep learning", "llm", "gpt",
    "chatgpt", "veri bilimi", "data science", "nlp", "prompt muhendisligi",
    "prompt engineering", "chatbot", "uretken yapay zeka", "generative ai",
    "buyuk dil model", " ai ", " ai:", "(ai)", "ai)",
    # Üretici/ürün adları: "Meta" bilerek eklenmedi — Meta'nın YZ dışı (Instagram,
    # VR, reklam vb.) etkinlikleri de yakalar; onların YZ tarafı zaten "llama"
    # ile kapsanıyor.
    "anthropic", "claude", "openai", "gemini", "copilot", "llama",
]

_TR_TO_ASCII = str.maketrans("ıİşŞğĞüÜöÖçÇâÂ", "iIsSgGuUoOcCaA")


def _normalize(text: str) -> str:
    """Türkçe karakterleri ASCII'ye indirger; anahtar kelime karşılaştırmasını
    büyük/küçük harf ve Türkçe'ye özgü harflerden bağımsız yapmak için."""
    return f" {text.translate(_TR_TO_ASCII).lower()} "


def is_ai_related(name: str) -> bool:
    """Etkinlik başlığında yapay zeka ile ilgili bir anahtar kelime geçiyor mu?"""
    normalized = _normalize(name or "")
    return any(keyword in normalized for keyword in _AI_KEYWORDS)


def parse_start_date(start_date_field: dict | None) -> str | None:
    """kommunity'nin {"date": "...", "timezone": {...}} alanını ISO 8601'e çevirir.

    Taradığımız tüm şehirler Türkiye'de olduğu için saat dilimi her zaman
    Europe/Istanbul (2016'dan beri yaz saati uygulaması olmayan sabit
    UTC+03:00) — zoneinfo/tzdata bağımlılığı eklemeden bu sabit ofseti
    doğrudan ekliyoruz.
    """
    if not start_date_field:
        return None
    date_str = start_date_field.get("date")
    if not date_str:
        return None
    try:
        naive = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return date_str
    return naive.isoformat() + "+03:00"


def parse_events(raw_events: list[dict], city: str) -> list[dict]:
    """Ham kommunity.com etkinlik kayıtlarını items şemasına uygun listeye çevirir.

    Sadece başlığında yapay zeka ile ilgili bir anahtar kelime geçen VE henüz
    bitmemiş (has_ended=False) etkinlikler dahil edilir.
    """
    items = []
    for event in raw_events:
        name = event.get("name") or ""
        if event.get("has_ended") or not is_ai_related(name):
            continue

        community = event.get("community") or {}
        venue = event.get("venue") or {}
        slug = event.get("slug")
        community_slug = community.get("slug")
        if not slug or not community_slug:
            continue

        location_bits = [b for b in (venue.get("name"), city) if b]

        items.append({
            "source": "kommunity_events",
            "title": name,
            "url": f"https://kommunity.com/{community_slug}/events/{slug}",
            "content": " · ".join(location_bits) if location_bits else None,
            "author": community.get("name"),
            "published_at": parse_start_date(event.get("start_date")),
            "image_url": event.get("highlight_photo"),
            "popularity": event.get("users_count"),
            "is_online": bool(event.get("is_online")),
        })
    return items


def fetch_city_page(city: str, page: int) -> dict:
    """Bir şehir için etkinlik listesinin tek bir sayfasını (ham JSON) döner."""
    resp = requests.get(API_URL, params={"city": city, "page": page}, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def collect(cities: list[str] | None = None, pages_from_end: int = PAGES_FROM_END) -> list[dict]:
    """Belirtilen şehirlerde yaklaşan yapay zeka etkinliklerini toplar.

    Aynı etkinlik birden fazla şehir taramasında eşleşirse (örn. "Online"
    etkinlikler), url'e göre tekilleştirilir.
    """
    cities = cities or CITIES
    collected: dict[str, dict] = {}

    for city in cities:
        first_page = fetch_city_page(city, 1)
        last_page = first_page.get("meta", {}).get("last_page", 1)
        start_page = max(1, last_page - pages_from_end + 1)

        for page in range(start_page, last_page + 1):
            data = first_page if page == 1 else fetch_city_page(city, page)
            for item in parse_events(data.get("data", []), city):
                collected[item["url"]] = item
            if page != last_page:
                time.sleep(REQUEST_DELAY_SECONDS)

    return list(collected.values())


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected_items = collect()
    added = save_items(collected_items)
    print(f"Kommunity Etkinlikler: {len(collected_items)} kayıt toplandı, {added} yeni kayıt eklendi.")
