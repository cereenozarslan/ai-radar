from ai_radar.collectors.hackernews import to_item_dict


def test_to_item_dict_converts_story_correctly():
    """Bir HN 'story' öğesi items şemasına doğru çevrilmeli."""
    raw = {
        "id": 123,
        "type": "story",
        "title": "Yeni bir LLM çıktı",
        "url": "https://example.com/haber",
        "by": "birkullanici",
        "time": 1700000000,
    }

    item = to_item_dict(raw)

    assert item["source"] == "hackernews"
    assert item["title"] == "Yeni bir LLM çıktı"
    assert item["url"] == "https://example.com/haber"
    assert item["author"] == "birkullanici"
    assert item["published_at"] is not None


def test_to_item_dict_ignores_non_story_items():
    """Yorum gibi 'story' olmayan öğeler ve url'siz Ask HN gönderileri özel durumlar."""
    comment = {"id": 1, "type": "comment", "text": "bir yorum"}
    assert to_item_dict(comment) is None
    assert to_item_dict(None) is None

    ask_hn = {"id": 2, "type": "story", "title": "Ask HN: ...", "by": "biri", "time": 1700000000}
    item = to_item_dict(ask_hn)
    assert item["url"] == "https://news.ycombinator.com/item?id=2"
