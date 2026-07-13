from ai_radar.collectors.kommunity_events import (
    is_ai_related,
    parse_events,
    parse_start_date,
)


def test_is_ai_related_matches_turkish_and_english_keywords():
    assert is_ai_related("Prompt Mühendisliği Atölyesi")
    assert is_ai_related("Yapay Zeka ve Geleceğimiz")
    assert is_ai_related("Machine Learning Meetup")
    assert is_ai_related("LatentShift.ai Conference for engineers shipping AI in production")
    assert is_ai_related("Büyük Dil Modelleri Üzerine Söyleşi")


def test_is_ai_related_handles_circumflex_a_spelling():
    # "zekâ" (^ şapkalı) da "zeka" kadar yaygın bir yazım; normalizasyon
    # bunu kaçırmamalı.
    assert is_ai_related("Yapay Zekâ Zirvesi")


def test_is_ai_related_excludes_ironic_ai_hater_titles():
    # Bağımsız "ai" kelimesi çok geniş yakalıyor; "AI Haters Party" gibi
    # YZ karşıtı/ironik başlıklar başka anahtar kelime içermese bile elenmeli.
    assert not is_ai_related("AI Haters Party: A Night for Real People")


def test_is_ai_related_matches_producer_and_product_names():
    assert is_ai_related("Anthropic'in Yeni Modeli Üzerine Sohbet")
    assert is_ai_related("Claude ile Kod Yazmak")
    assert is_ai_related("OpenAI Devrimi")
    assert is_ai_related("Gemini Kullanıcı Buluşması")
    assert is_ai_related("GitHub Copilot Atölyesi")
    assert is_ai_related("Llama ile Yerel Model Çalıştırma")


def test_is_ai_related_does_not_match_bare_meta():
    # "Meta" bilerek eklenmedi: Instagram/VR/reklam gibi YZ dışı etkinlikleri
    # de yakalar. Meta'nın YZ tarafı "llama" ile zaten kapsanıyor.
    assert not is_ai_related("Meta Reklam Yöneticileri Buluşması")


def test_is_ai_related_ignores_unrelated_titles():
    assert not is_ai_related("Coffee & Code")
    assert not is_ai_related("Mehtap Turu")
    assert not is_ai_related("")
    assert not is_ai_related(None)


def test_parse_start_date_converts_to_iso_with_istanbul_offset():
    field = {"date": "2026-07-24 14:00:00", "timezone": {"timezone_type": 3, "timezone": "Europe/Istanbul"}}
    assert parse_start_date(field) == "2026-07-24T14:00:00+03:00"


def test_parse_start_date_handles_missing_field():
    assert parse_start_date(None) is None
    assert parse_start_date({}) is None


RAW_EVENTS = [
    {
        "name": "Prompt Mühendisliği Atölyesi",
        "slug": "prompt-muhendisligi-atolyesi-916febb6",
        "start_date": {"date": "2026-07-24 14:00:00", "timezone": {"timezone": "Europe/Istanbul"}},
        "has_ended": False,
        "highlight_photo": "https://media.kommunity.com/foo.jpeg",
        "users_count": 42,
        "is_online": False,
        "venue": {"name": "Tech Istanbul | Küçükçekmece"},
        "community": {"name": "Tech Istanbul", "slug": "techistanbul"},
    },
    {
        "name": "Coffee & Code",
        "slug": "coffee-and-code",
        "start_date": {"date": "2026-07-20 14:00:00", "timezone": {"timezone": "Europe/Istanbul"}},
        "has_ended": False,
        "highlight_photo": None,
        "users_count": 5,
        "venue": {"name": "The Marmara Hotel Lounge"},
        "community": {"name": "Istanbul Coders", "slug": "istanbulcoders"},
    },
    {
        "name": "Geçmiş bir Yapay Zeka Etkinliği",
        "slug": "gecmis-etkinlik",
        "start_date": {"date": "2020-01-01 14:00:00", "timezone": {"timezone": "Europe/Istanbul"}},
        "has_ended": True,
        "highlight_photo": None,
        "users_count": 5,
        "venue": {"name": "Bir Yer"},
        "community": {"name": "Bir Topluluk", "slug": "bir-topluluk"},
    },
    {
        "name": "Slug'ı veya topluluk slug'ı olmayan Yapay Zeka Etkinliği",
        "slug": None,
        "start_date": {"date": "2026-07-24 14:00:00", "timezone": {"timezone": "Europe/Istanbul"}},
        "has_ended": False,
        "highlight_photo": None,
        "users_count": 5,
        "venue": {"name": "Bir Yer"},
        "community": {"name": "Bir Topluluk", "slug": "bir-topluluk"},
    },
]


def test_parse_events_keeps_only_ai_related_and_not_ended():
    items = parse_events(RAW_EVENTS, city="Istanbul")

    assert len(items) == 1
    item = items[0]
    assert item["source"] == "kommunity_events"
    assert item["title"] == "Prompt Mühendisliği Atölyesi"
    assert item["url"] == "https://kommunity.com/techistanbul/events/prompt-muhendisligi-atolyesi-916febb6"
    assert item["content"] == "Tech Istanbul | Küçükçekmece · Istanbul"
    assert item["author"] == "Tech Istanbul"
    assert item["published_at"] == "2026-07-24T14:00:00+03:00"
    assert item["image_url"] == "https://media.kommunity.com/foo.jpeg"
    assert item["popularity"] == 42
    assert item["is_online"] is False


def test_parse_events_skips_events_without_slug():
    items = parse_events(RAW_EVENTS, city="Istanbul")
    titles = [it["title"] for it in items]
    assert "Slug'ı veya topluluk slug'ı olmayan Yapay Zeka Etkinliği" not in titles
