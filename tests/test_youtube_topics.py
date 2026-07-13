from ai_radar.collectors.youtube_topics import compute_engagement_score, parse_videos

RAW_ITEMS = [
    {
        "id": "high-views-low-engagement",
        "snippet": {
            "title": "Cok Izlenen Ama Az Etkilesimli Video",
            "channelTitle": "Kanal A",
            "publishedAt": "2026-07-01T00:00:00Z",
            "thumbnails": {"high": {"url": "https://example.com/high.jpg"}},
        },
        "statistics": {"viewCount": "1000000", "likeCount": "100", "commentCount": "10"},
    },
    {
        "id": "lower-views-high-engagement",
        "snippet": {
            "title": "Az Izlenen Ama Cok Etkilesimli Video",
            "channelTitle": "Kanal B",
            "publishedAt": "2026-07-05T00:00:00Z",
            "thumbnails": {"medium": {"url": "https://example.com/medium.jpg"}},
        },
        "statistics": {"viewCount": "50000", "likeCount": "20000", "commentCount": "5000"},
    },
    {
        "id": "no-title-skipped",
        "snippet": {"channelTitle": "Kanal C"},
        "statistics": {"viewCount": "999999"},
    },
]


def test_compute_engagement_score_weights_likes_and_comments_heavily():
    low_engagement = compute_engagement_score({"viewCount": "1000000", "likeCount": "100", "commentCount": "10"})
    high_engagement = compute_engagement_score({"viewCount": "50000", "likeCount": "20000", "commentCount": "5000"})
    assert high_engagement > low_engagement


def test_parse_videos_maps_fields_correctly():
    videos = parse_videos(RAW_ITEMS, topic="Claude")

    assert len(videos) == 2  # basliksiz kayit atlanmali
    first = next(v for v in videos if v["video_id"] == "high-views-low-engagement")
    assert first["topic"] == "Claude"
    assert first["title"] == "Cok Izlenen Ama Az Etkilesimli Video"
    assert first["url"] == "https://www.youtube.com/watch?v=high-views-low-engagement"
    assert first["channel_title"] == "Kanal A"
    assert first["published_at"] == "2026-07-01T00:00:00Z"
    assert first["image_url"] == "https://example.com/high.jpg"
    assert first["view_count"] == 1000000
    assert first["like_count"] == 100
    assert first["comment_count"] == 10


def test_parse_videos_falls_back_to_medium_thumbnail():
    videos = parse_videos(RAW_ITEMS, topic="Claude")
    second = next(v for v in videos if v["video_id"] == "lower-views-high-engagement")
    assert second["image_url"] == "https://example.com/medium.jpg"


def test_parse_videos_skips_items_without_title():
    videos = parse_videos(RAW_ITEMS, topic="Claude")
    ids = [v["video_id"] for v in videos]
    assert "no-title-skipped" not in ids


def test_parse_videos_sorts_by_engagement_score_descending():
    videos = parse_videos(RAW_ITEMS, topic="Claude")
    assert videos[0]["video_id"] == "lower-views-high-engagement"
    assert videos[1]["video_id"] == "high-views-low-engagement"


def test_parse_videos_handles_missing_statistics_gracefully():
    raw = [{
        "id": "no-stats",
        "snippet": {"title": "Istatistiksiz Video", "channelTitle": "Kanal D", "publishedAt": None, "thumbnails": {}},
    }]
    videos = parse_videos(raw, topic="Claude")
    assert len(videos) == 1
    assert videos[0]["view_count"] == 0
    assert videos[0]["like_count"] == 0
    assert videos[0]["comment_count"] == 0
    assert videos[0]["image_url"] is None
