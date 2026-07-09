from datetime import datetime, timezone
from types import SimpleNamespace

from ai_radar.collectors.x_twitter import to_item_dict

# Not: Bu testler gerçek bir X API isteği göndermez, tweepy nesnelerini
# taklit eden basit SimpleNamespace'ler kullanır (network yok, maliyet yok).


def test_to_item_dict_converts_tweet_correctly():
    tweet = SimpleNamespace(
        id=123456789,
        text="Yeni bir LLM modeli duyuruldu, detaylar burada",
        author_id=42,
        created_at=datetime(2026, 7, 9, tzinfo=timezone.utc),
    )
    users_by_id = {42: SimpleNamespace(id=42, username="birkullanici")}

    item = to_item_dict(tweet, users_by_id)

    assert item["source"] == "x_twitter"
    assert item["url"] == "https://x.com/i/web/status/123456789"
    assert item["author"] == "birkullanici"
    assert item["content"] == tweet.text
    assert item["published_at"] is not None


def test_to_item_dict_handles_long_text_and_missing_user():
    long_text = "a" * 100
    tweet = SimpleNamespace(id=1, text=long_text, author_id=99, created_at=None)

    item = to_item_dict(tweet, users_by_id={})

    assert len(item["title"]) == 80
    assert item["title"].endswith("...")
    assert item["author"] is None
    assert item["published_at"] is None
