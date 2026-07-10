from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import ai_radar.collectors.x_twitter as x_twitter
from ai_radar.collectors.x_twitter import (
    build_query,
    clamp_max_results,
    collect,
    compute_start_time,
    engagement_score,
    to_item_dict,
)

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


def test_build_query_wraps_multi_word_topic_in_quotes():
    """Birden fazla kelimeli konular tam öbek (phrase) olarak aranmalı."""
    query = build_query("Meta Muse")

    assert '"Meta Muse"' in query
    assert "-is:reply" in query
    assert "-is:retweet" in query
    assert "-has:cashtags" in query


def test_build_query_leaves_single_word_topic_unquoted():
    """Tek kelimelik konularda tırnak gerekmez."""
    query = build_query("LLM")
    assert query.startswith("LLM ")
    assert '"' not in query


def test_clamp_max_results_enforces_x_api_bounds():
    """X'in recent search uç noktası 10-100 aralığı dışındaki değerleri reddediyor."""
    assert clamp_max_results(5) == 10
    assert clamp_max_results(500) == 100
    assert clamp_max_results(50) == 50


def test_engagement_score_weights_retweets_double():
    """Retweet, beğeni/yanıt/alıntıdan 2 kat ağırlıklı sayılmalı."""
    tweet = SimpleNamespace(public_metrics={
        "like_count": 10, "retweet_count": 3, "reply_count": 1, "quote_count": 0,
    })
    assert engagement_score(tweet) == 10 + 3 * 2 + 1 + 0


def test_engagement_score_handles_missing_metrics():
    tweet = SimpleNamespace(public_metrics=None)
    assert engagement_score(tweet) == 0


def test_collect_sorts_by_engagement_and_applies_min_threshold(monkeypatch):
    """collect(), düşük etkileşimli tweetleri eleyip kalanları etkileşime göre sıralamalı."""
    def make_tweet(id_, likes):
        return SimpleNamespace(
            id=id_, text=f"tweet-{id_}", author_id=1,
            created_at=None,
            public_metrics={"like_count": likes, "retweet_count": 0, "reply_count": 0, "quote_count": 0},
        )

    fake_response = SimpleNamespace(
        data=[make_tweet(1, likes=2), make_tweet(2, likes=50), make_tweet(3, likes=20)],
        includes={"users": [SimpleNamespace(id=1, username="birkullanici")]},
    )

    monkeypatch.setattr(
        x_twitter, "search_recent",
        lambda query, max_results, start_time=None: fake_response,
    )

    items = collect(topic="Fable 5", min_engagement=5)

    # id=1 (2 begeni) esik altinda kaldigi icin elenmeli
    assert [item["title"] for item in items] == ["tweet-2", "tweet-3"]


def test_compute_start_time_returns_x_api_compatible_format():
    """X API 'YYYY-MM-DDTHH:MM:SSZ' formatinda bir zaman damgasi bekliyor."""
    result = compute_start_time(24)
    assert result.endswith("Z")
    # Bicimin gecerli oldugunu (parse edilebildigini) dogrula
    datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")


def test_compute_start_time_is_roughly_n_hours_ago():
    result = compute_start_time(24)
    parsed = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    expected = datetime.now(timezone.utc) - timedelta(hours=24)
    assert abs((parsed - expected).total_seconds()) < 5


def test_collect_passes_computed_start_time_to_search_recent(monkeypatch):
    """collect(hours=...) verildiginde search_recent'e dogru start_time gitmeli."""
    captured = {}

    def fake_search_recent(query, max_results, start_time=None):
        captured["start_time"] = start_time
        return SimpleNamespace(data=[], includes={})

    monkeypatch.setattr(x_twitter, "search_recent", fake_search_recent)

    collect(topic="Claude", hours=24)

    assert captured["start_time"] is not None
    assert captured["start_time"].endswith("Z")
