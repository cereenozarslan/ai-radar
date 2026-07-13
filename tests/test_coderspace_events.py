from ai_radar.collectors.coderspace_events import extract_jsonld_events, parse_events

SAMPLE_HTML = """
<html><body>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Event", "name": "Mobven Young Talent AI Hackathon",
 "startDate": "2026-07-24T13:00:00+00:00", "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
 "location": {"@type": "VirtualLocation", "url": "https://coderspace.io/etkinlikler/mobven-ai-hackathon/"},
 "description": "Yapay zeka alaninda yeteneklerini gosterme firsati.",
 "organizer": {"@type": "Organization", "name": "Coderspace"},
 "image": ["https://example.com/small.png", "https://example.com/hero.png"]}
</script>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Event", "name": "Softtech Road to Tech Staj Programi",
 "startDate": "2026-06-16T06:00:00+00:00", "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
 "location": {"@type": "VirtualLocation", "url": "https://coderspace.io/etkinlikler/softtech-staj/"},
 "description": "Staj programi basvurulari basladi.",
 "organizer": {"@type": "Organization", "name": "Coderspace"},
 "image": "https://example.com/softtech.png"}
</script>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": []}
</script>
</body></html>
"""


def test_extract_jsonld_events_only_keeps_event_type():
    events = extract_jsonld_events(SAMPLE_HTML)
    assert len(events) == 2
    assert all(e["@type"] == "Event" for e in events)


def test_extract_jsonld_events_handles_no_scripts():
    assert extract_jsonld_events("<html><body>bos</body></html>") == []


def test_parse_events_keeps_only_ai_related_and_maps_fields():
    events = extract_jsonld_events(SAMPLE_HTML)
    items = parse_events(events)

    assert len(items) == 1
    item = items[0]
    assert item["source"] == "coderspace_events"
    assert item["title"] == "Mobven Young Talent AI Hackathon"
    assert item["url"] == "https://coderspace.io/etkinlikler/mobven-ai-hackathon/"
    assert item["content"] == "Yapay zeka alaninda yeteneklerini gosterme firsati."
    assert item["author"] == "Coderspace"
    assert item["published_at"] == "2026-07-24T13:00:00+00:00"
    assert item["image_url"] == "https://example.com/hero.png"
    assert item["is_online"] is True


def test_parse_events_excludes_unrelated_titles():
    events = extract_jsonld_events(SAMPLE_HTML)
    items = parse_events(events)
    titles = [it["title"] for it in items]
    assert "Softtech Road to Tech Staj Programi" not in titles


def test_parse_events_handles_string_image_and_missing_organizer():
    raw = [{
        "@type": "Event", "name": "Yapay Zeka Semineri",
        "url": "https://coderspace.io/etkinlikler/yz-semineri/",
        "startDate": "2026-09-01T10:00:00+00:00",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "image": "https://example.com/tek-gorsel.png",
    }]
    items = parse_events(raw)
    assert len(items) == 1
    assert items[0]["image_url"] == "https://example.com/tek-gorsel.png"
    assert items[0]["author"] is None
    assert items[0]["is_online"] is False
