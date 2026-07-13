from ai_radar.collectors.youtube_channels import parse_channel_videos

RAW_ITEMS = [
    {
        "id": "vid1",
        "snippet": {
            "title": "OpenAI is so back... GPT 5.6 Sol first look",
            "description": "OpenAI just released GPT-5.6...",
            "publishedAt": "2026-07-10T17:25:44Z",
            "thumbnails": {"high": {"url": "https://example.com/high.jpg"}},
        },
        "statistics": {"viewCount": "120000", "likeCount": "5000", "commentCount": "300"},
    },
    {
        "id": "vid2",
        "snippet": {"channelTitle": "Kanal"},
        "statistics": {"viewCount": "1"},
    },
]


def test_parse_channel_videos_maps_fields_correctly():
    items = parse_channel_videos(RAW_ITEMS, channel_display_name="Fireship")

    assert len(items) == 1
    item = items[0]
    assert item["source"] == "youtube_channel"
    assert item["title"] == "OpenAI is so back... GPT 5.6 Sol first look"
    assert item["url"] == "https://www.youtube.com/watch?v=vid1"
    assert item["content"] == "OpenAI just released GPT-5.6..."
    assert item["author"] == "Fireship"
    assert item["published_at"] == "2026-07-10T17:25:44Z"
    assert item["image_url"] == "https://example.com/high.jpg"
    assert item["popularity"] == 120000


def test_parse_channel_videos_skips_items_without_title():
    items = parse_channel_videos(RAW_ITEMS, channel_display_name="Fireship")
    ids = [it["url"] for it in items]
    assert "https://www.youtube.com/watch?v=vid2" not in ids


def test_parse_channel_videos_handles_missing_thumbnails_and_stats():
    raw = [{
        "id": "vid3",
        "snippet": {"title": "Baslik var ama kucuk resim/istatistik yok", "publishedAt": None, "thumbnails": {}},
    }]
    items = parse_channel_videos(raw, channel_display_name="Kanal X")
    assert len(items) == 1
    assert items[0]["image_url"] is None
    assert items[0]["popularity"] == 0
