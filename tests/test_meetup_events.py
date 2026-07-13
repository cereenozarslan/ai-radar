from ai_radar.collectors.meetup_events import (
    extract_apollo_state,
    parse_group_events,
    parse_search_events,
)

# Gerçek meetup.com sayfasının Next.js __NEXT_DATA__ yapısını taklit eden minimal HTML
SAMPLE_HTML = """
<html><body>
<script id="__NEXT_DATA__" type="application/json">
{"props": {"pageProps": {"__APOLLO_STATE__": {
    "Event:1": {
        "__typename": "Event", "title": "Yapay Zeka Meetup Istanbul",
        "eventUrl": "https://www.meetup.com/foo/events/1/",
        "dateTime": "2026-08-01T18:00:00+03:00", "eventType": "PHYSICAL",
        "venue": {"name": "WeWork", "city": "Istanbul", "country": "tr"},
        "group": {"__ref": "Group:1"}, "featuredEventPhoto": {"__ref": "PhotoInfo:1"}
    },
    "Group:1": {"__typename": "Group", "name": "Istanbul AI Group"},
    "PhotoInfo:1": {"__typename": "PhotoInfo", "highResUrl": "https://example.com/photo.jpg"}
}}}}
</script>
</body></html>
"""


def test_extract_apollo_state_parses_next_data():
    apollo = extract_apollo_state(SAMPLE_HTML)
    assert "Event:1" in apollo
    assert apollo["Event:1"]["title"] == "Yapay Zeka Meetup Istanbul"


def test_extract_apollo_state_handles_missing_script():
    assert extract_apollo_state("<html><body>no data here</body></html>") == {}


PHYSICAL_TR_AI = {
    "__typename": "Event", "title": "Yapay Zeka Meetup Istanbul",
    "eventUrl": "https://www.meetup.com/foo/events/1/",
    "dateTime": "2026-08-01T18:00:00+03:00", "eventType": "PHYSICAL",
    "venue": {"name": "WeWork", "city": "Istanbul", "country": "tr"},
    "group": {"__ref": "Group:1"}, "featuredEventPhoto": {"__ref": "PhotoInfo:1"},
}
PHYSICAL_NON_TR_AI = {
    "__typename": "Event", "title": "AI Meetup Yerevan",
    "eventUrl": "https://www.meetup.com/foo/events/2/",
    "dateTime": "2026-08-01T18:00:00+03:00", "eventType": "PHYSICAL",
    "venue": {"name": "Somewhere", "city": "Yerevan", "country": "am"},
    "group": {"__ref": "Group:1"},
}
PHYSICAL_TR_UNRELATED = {
    "__typename": "Event", "title": "Cyber Security Talks",
    "eventUrl": "https://www.meetup.com/foo/events/3/",
    "dateTime": "2026-08-01T18:00:00+03:00", "eventType": "PHYSICAL",
    "venue": {"name": "Somewhere", "city": "Istanbul", "country": "tr"},
    "group": {"__ref": "Group:1"},
}
ONLINE_AI = {
    "__typename": "Event", "title": "Global AI Governance Webinar",
    "eventUrl": "https://www.meetup.com/foo/events/4/",
    "dateTime": "2026-08-01T18:00:00+03:00", "eventType": "ONLINE",
    "venue": {"name": "Online event", "city": "", "country": ""},
    "group": {"__ref": "Group:1"},
}

APOLLO = {
    "Event:1": PHYSICAL_TR_AI,
    "Event:2": PHYSICAL_NON_TR_AI,
    "Event:3": PHYSICAL_TR_UNRELATED,
    "Event:4": ONLINE_AI,
    "Group:1": {"__typename": "Group", "name": "Istanbul AI Group"},
    "PhotoInfo:1": {"__typename": "PhotoInfo", "highResUrl": "https://example.com/photo.jpg"},
}


def test_parse_search_events_keeps_only_physical_turkey_ai_events():
    items = parse_search_events(APOLLO)

    assert len(items) == 1
    item = items[0]
    assert item["source"] == "meetup_events"
    assert item["title"] == "Yapay Zeka Meetup Istanbul"
    assert item["url"] == "https://www.meetup.com/foo/events/1/"
    assert item["author"] == "Istanbul AI Group"
    assert item["image_url"] == "https://example.com/photo.jpg"
    assert item["content"] == "WeWork · Istanbul"
    assert item["is_online"] is False


def test_parse_search_events_excludes_non_turkey_venue():
    items = parse_search_events(APOLLO)
    urls = [it["url"] for it in items]
    assert "https://www.meetup.com/foo/events/2/" not in urls


def test_parse_search_events_excludes_online_events():
    items = parse_search_events(APOLLO)
    urls = [it["url"] for it in items]
    assert "https://www.meetup.com/foo/events/4/" not in urls


def test_parse_search_events_excludes_unrelated_titles():
    items = parse_search_events(APOLLO)
    urls = [it["url"] for it in items]
    assert "https://www.meetup.com/foo/events/3/" not in urls


def test_parse_group_events_includes_everything_even_online_and_unrelated_titles():
    # Bilinen bir YZ topluluğunun KENDİ sayfası: topluluğun tamamı zaten YZ
    # odaklı olduğu için anahtar kelime/online filtresi uygulanmaz.
    items = parse_group_events(APOLLO)
    urls = {it["url"] for it in items}
    assert urls == {
        "https://www.meetup.com/foo/events/1/",
        "https://www.meetup.com/foo/events/2/",
        "https://www.meetup.com/foo/events/3/",
        "https://www.meetup.com/foo/events/4/",
    }
    online_item = next(it for it in items if it["url"] == "https://www.meetup.com/foo/events/4/")
    assert online_item["is_online"] is True
    assert online_item["content"] == "Online"


def test_parse_group_events_handles_missing_group_and_photo_refs_gracefully():
    apollo = {
        "Event:9": {
            "__typename": "Event", "title": "Referanssız Etkinlik",
            "eventUrl": "https://www.meetup.com/foo/events/9/",
            "dateTime": "2026-08-01T18:00:00+03:00", "eventType": "ONLINE",
            "venue": {"name": "Online event"},
        },
    }
    items = parse_group_events(apollo)
    assert len(items) == 1
    assert items[0]["author"] is None
    assert items[0]["image_url"] is None
