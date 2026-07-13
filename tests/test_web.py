from fastapi.testclient import TestClient

import ai_radar.web as web
from ai_radar.database import get_connection as web_get_connection

# Not: Bu testler gerçek X API isteği göndermez; x_twitter.collect() mock'lanır.


def test_search_endpoint_returns_interpreted_filters_and_items(monkeypatch):
    def fake_collect(topic=None, query=None, max_results=10, min_engagement=0, hours=None):
        assert topic == "Claude"
        assert hours == 24
        assert min_engagement == 20
        return [{
            "source": "x_twitter", "title": "örnek", "url": "https://x.com/i/web/status/1",
            "content": "örnek", "author": "biri", "published_at": None,
        }]

    monkeypatch.setattr(web.x_twitter, "collect", fake_collect)
    monkeypatch.setattr(web, "save_items", lambda items: len(items))

    client = TestClient(web.app)
    resp = client.get("/api/search", params={"q": "Claude son 24 saatte yüksek etkileşim"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["interpreted"]["hours"] == 24
    assert data["interpreted"]["min_engagement"] == 20
    assert data["result_count"] == 1
    assert data["added_count"] == 1
    assert data["items"][0]["title"] == "örnek"


def test_search_endpoint_rejects_empty_query():
    client = TestClient(web.app)
    resp = client.get("/api/search", params={"q": "   "})
    assert resp.status_code == 400


def test_search_endpoint_returns_502_on_x_api_error(monkeypatch):
    def failing_collect(**kwargs):
        raise RuntimeError("X API kota doldu")

    monkeypatch.setattr(web.x_twitter, "collect", failing_collect)

    client = TestClient(web.app)
    resp = client.get("/api/search", params={"q": "Claude"})

    assert resp.status_code == 502
    assert "X API hatası" in resp.json()["detail"]


def test_refresh_x_without_topic_uses_default_query(monkeypatch):
    """topic verilmezse collect() topic=None ile çağrılmalı (DEFAULT_QUERY'ye düşer)."""
    captured = {}

    def fake_collect(topic=None, **kwargs):
        captured["topic"] = topic
        return [{
            "source": "x_twitter", "title": "örnek", "url": "https://x.com/i/web/status/1",
            "content": "örnek", "author": "biri", "published_at": None,
        }]

    monkeypatch.setattr(web.x_twitter, "collect", fake_collect)
    monkeypatch.setattr(web, "save_items", lambda items: len(items))

    client = TestClient(web.app)
    resp = client.post("/api/refresh-x")

    assert resp.status_code == 200
    assert captured["topic"] is None
    data = resp.json()
    assert data["result_count"] == 1
    assert data["added_count"] == 1


def test_refresh_x_with_topic_passes_it_through(monkeypatch):
    captured = {}

    def fake_collect(topic=None, **kwargs):
        captured["topic"] = topic
        return []

    monkeypatch.setattr(web.x_twitter, "collect", fake_collect)

    client = TestClient(web.app)
    resp = client.post("/api/refresh-x", params={"topic": "Anthropic"})

    assert resp.status_code == 200
    assert captured["topic"] == "Anthropic"
    assert resp.json()["topic"] == "Anthropic"


def test_refresh_x_returns_502_on_x_api_error(monkeypatch):
    def failing_collect(topic=None, **kwargs):
        raise RuntimeError("X API kota doldu")

    monkeypatch.setattr(web.x_twitter, "collect", failing_collect)

    client = TestClient(web.app)
    resp = client.post("/api/refresh-x")

    assert resp.status_code == 502
    assert "X API hatası" in resp.json()["detail"]


def test_index_serves_html():
    client = TestClient(web.app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_list_items_returns_database_contents(tmp_path, monkeypatch):
    from ai_radar.database import get_connection, init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO items (source, title, url, image_url) VALUES (?, ?, ?, ?)",
        ("nuvemmag", "test haber", "https://example.com/1", "https://example.com/foto.jpg"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(web, "get_connection", lambda: get_connection(db_path))

    client = TestClient(web.app)
    resp = client.get("/api/items")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "test haber"
    assert data[0]["source"] == "nuvemmag"
    assert data[0]["image_url"] == "https://example.com/foto.jpg"


def _make_followed_accounts_db(tmp_path, usernames):
    from ai_radar.database import get_connection, init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = get_connection(db_path)
    for username in usernames:
        conn.execute("INSERT INTO followed_accounts (username) VALUES (?)", (username,))
    conn.commit()
    conn.close()
    return db_path


def _make_followed_topics_db(tmp_path, topics, snapshots=()):
    """snapshots: [(topic, checked_at_iso, total_engagement, mention_count), ...]"""
    from ai_radar.database import get_connection, init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = get_connection(db_path)
    for topic in topics:
        conn.execute("INSERT INTO followed_topics (topic) VALUES (?)", (topic,))
    for topic, checked_at, total_engagement, mention_count in snapshots:
        conn.execute(
            "INSERT INTO topic_engagement_snapshots (topic, checked_at, total_engagement, mention_count) "
            "VALUES (?, ?, ?, ?)",
            (topic, checked_at, total_engagement, mention_count),
        )
    conn.commit()
    conn.close()
    return db_path


def test_list_followed_topics_returns_growth_info(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    snapshots = [
        ("OpenAI", (now - timedelta(hours=2)).isoformat(), 100, 5),
        ("OpenAI", (now - timedelta(hours=18)).isoformat(), 40, 2),
    ]
    db_path = _make_followed_topics_db(tmp_path, ["OpenAI"], snapshots)
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.get("/api/followed-topics")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["topic"] == "OpenAI"
    assert data[0]["growth_pct"] == 150
    assert data[0]["is_rising"] is True


def test_list_followed_topics_not_rising_without_enough_history(tmp_path, monkeypatch):
    db_path = _make_followed_topics_db(tmp_path, ["Anthropic"])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.get("/api/followed-topics")

    data = resp.json()
    assert data[0]["growth_pct"] is None
    assert data[0]["is_rising"] is False


def test_add_followed_topic_and_ignore_duplicate(tmp_path, monkeypatch):
    db_path = _make_followed_topics_db(tmp_path, [])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.post("/api/followed-topics", params={"topic": "Meta"})
    assert resp.status_code == 200
    assert resp.json()["topic"] == "Meta"

    resp2 = client.post("/api/followed-topics", params={"topic": "Meta"})
    assert resp2.status_code == 200

    resp3 = client.get("/api/followed-topics")
    assert [row["topic"] for row in resp3.json()] == ["Meta"]


def test_add_followed_topic_rejects_empty(tmp_path, monkeypatch):
    db_path = _make_followed_topics_db(tmp_path, [])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.post("/api/followed-topics", params={"topic": "   "})

    assert resp.status_code == 400


def test_remove_followed_topic_deletes_topic_and_snapshots(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    snapshots = [("Meta", datetime.now(timezone.utc).isoformat(), 10, 1)]
    db_path = _make_followed_topics_db(tmp_path, ["Meta"], snapshots)
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.delete("/api/followed-topics/Meta")

    assert resp.status_code == 200
    assert client.get("/api/followed-topics").json() == []

    conn = web_get_connection(db_path)
    remaining = conn.execute("SELECT COUNT(*) FROM topic_engagement_snapshots WHERE topic = ?", ("Meta",)).fetchone()[0]
    conn.close()
    assert remaining == 0


def test_remove_followed_topic_returns_404_for_unknown_topic(tmp_path, monkeypatch):
    db_path = _make_followed_topics_db(tmp_path, [])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.delete("/api/followed-topics/BilinmeyenKonu")

    assert resp.status_code == 404


def test_following_digest_uses_local_followed_accounts_list(tmp_path, monkeypatch):
    """X_FOLLOW_USERNAME tanımlı değilse, sadece arayüzden eklenen yerel liste kullanılmalı."""
    db_path = _make_followed_accounts_db(tmp_path, ["birkullanici"])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))
    monkeypatch.setattr(web.config, "X_FOLLOW_USERNAME", None)

    def fake_digest(usernames, hours=36):
        assert usernames == ["birkullanici"]
        assert hours == 36
        return [{
            "source": "x_following", "title": "örnek", "url": "https://x.com/i/web/status/1",
            "content": "örnek", "author": "biri", "published_at": None,
        }]

    monkeypatch.setattr(web.x_twitter, "collect_following_digest_for_usernames", fake_digest)
    monkeypatch.setattr(web, "save_items", lambda items: len(items))

    client = TestClient(web.app)
    resp = client.get("/api/following-digest")

    assert resp.status_code == 200
    data = resp.json()
    assert data["result_count"] == 1
    assert data["added_count"] == 1
    assert data["items"][0]["source"] == "x_following"


def test_following_digest_uses_real_x_following_list_when_configured(tmp_path, monkeypatch):
    """Yerel liste boş olsa bile, X_FOLLOW_USERNAME tanımlıysa X'in gerçek takip
    listesi kullanılmalı (eski davranış korunmalı)."""
    db_path = _make_followed_accounts_db(tmp_path, [])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))
    monkeypatch.setattr(web.config, "X_FOLLOW_USERNAME", "gercekhesabim")
    monkeypatch.setattr(web.x_twitter, "get_following_usernames", lambda username: ["takipedilen1"])

    def fake_digest(usernames, hours=36):
        assert usernames == ["takipedilen1"]
        return [{
            "source": "x_following", "title": "örnek", "url": "https://x.com/i/web/status/2",
            "content": "örnek", "author": "biri", "published_at": None,
        }]

    monkeypatch.setattr(web.x_twitter, "collect_following_digest_for_usernames", fake_digest)
    monkeypatch.setattr(web, "save_items", lambda items: len(items))

    client = TestClient(web.app)
    resp = client.get("/api/following-digest")

    assert resp.status_code == 200
    assert resp.json()["result_count"] == 1


def test_following_digest_combines_local_list_and_real_x_following(tmp_path, monkeypatch):
    """Her ikisi de tanımlıysa, iki kaynaktaki kullanıcı adları birleşip
    (tekrarsız) tek listede toplanmalı."""
    db_path = _make_followed_accounts_db(tmp_path, ["manuel_eklenen", "ortak"])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))
    monkeypatch.setattr(web.config, "X_FOLLOW_USERNAME", "gercekhesabim")
    monkeypatch.setattr(web.x_twitter, "get_following_usernames", lambda username: ["gercek_takip", "ortak"])

    captured = {}

    def fake_digest(usernames, hours=36):
        captured["usernames"] = usernames
        return []

    monkeypatch.setattr(web.x_twitter, "collect_following_digest_for_usernames", fake_digest)

    client = TestClient(web.app)
    resp = client.get("/api/following-digest")

    assert resp.status_code == 200
    assert captured["usernames"] == ["gercek_takip", "manuel_eklenen", "ortak"]


def test_following_digest_requires_at_least_one_followed_account(tmp_path, monkeypatch):
    db_path = _make_followed_accounts_db(tmp_path, [])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))
    monkeypatch.setattr(web.config, "X_FOLLOW_USERNAME", None)

    client = TestClient(web.app)
    resp = client.get("/api/following-digest")

    assert resp.status_code == 400


def test_following_digest_returns_502_on_x_api_error(tmp_path, monkeypatch):
    db_path = _make_followed_accounts_db(tmp_path, ["birkullanici"])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))
    monkeypatch.setattr(web.config, "X_FOLLOW_USERNAME", None)

    def failing_digest(usernames, hours=36):
        raise RuntimeError("X API kota doldu")

    monkeypatch.setattr(web.x_twitter, "collect_following_digest_for_usernames", failing_digest)

    client = TestClient(web.app)
    resp = client.get("/api/following-digest")

    assert resp.status_code == 502


def test_following_digest_returns_502_when_fetching_real_following_list_fails(tmp_path, monkeypatch):
    db_path = _make_followed_accounts_db(tmp_path, [])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))
    monkeypatch.setattr(web.config, "X_FOLLOW_USERNAME", "gercekhesabim")

    def failing_get_following(username):
        raise RuntimeError("X API kota doldu")

    monkeypatch.setattr(web.x_twitter, "get_following_usernames", failing_get_following)

    client = TestClient(web.app)
    resp = client.get("/api/following-digest")

    assert resp.status_code == 502


def test_list_followed_accounts_returns_usernames_sorted(tmp_path, monkeypatch):
    db_path = _make_followed_accounts_db(tmp_path, ["zeynep", "ahmet"])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.get("/api/followed-accounts")

    assert resp.status_code == 200
    usernames = [row["username"] for row in resp.json()]
    assert usernames == ["ahmet", "zeynep"]


def test_add_followed_account_strips_at_sign(tmp_path, monkeypatch):
    db_path = _make_followed_accounts_db(tmp_path, [])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.post("/api/followed-accounts", params={"username": "@birisi"})

    assert resp.status_code == 200
    assert resp.json()["username"] == "birisi"

    resp2 = client.get("/api/followed-accounts")
    assert [row["username"] for row in resp2.json()] == ["birisi"]


def test_add_followed_account_ignores_duplicate(tmp_path, monkeypatch):
    db_path = _make_followed_accounts_db(tmp_path, ["birisi"])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.post("/api/followed-accounts", params={"username": "birisi"})

    assert resp.status_code == 200
    resp2 = client.get("/api/followed-accounts")
    assert len(resp2.json()) == 1


def test_add_followed_account_rejects_empty_username(tmp_path, monkeypatch):
    db_path = _make_followed_accounts_db(tmp_path, [])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.post("/api/followed-accounts", params={"username": "   "})

    assert resp.status_code == 400


def test_remove_followed_account_deletes_row(tmp_path, monkeypatch):
    db_path = _make_followed_accounts_db(tmp_path, ["birisi"])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    conn = web_get_connection(db_path)
    account_id = conn.execute("SELECT id FROM followed_accounts WHERE username = ?", ("birisi",)).fetchone()[0]
    conn.close()

    client = TestClient(web.app)
    resp = client.delete(f"/api/followed-accounts/{account_id}")

    assert resp.status_code == 200
    resp2 = client.get("/api/followed-accounts")
    assert resp2.json() == []


def test_remove_followed_account_returns_404_for_unknown_id(tmp_path, monkeypatch):
    db_path = _make_followed_accounts_db(tmp_path, [])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.delete("/api/followed-accounts/999999")

    assert resp.status_code == 404


def _make_test_db(tmp_path):
    from ai_radar.database import get_connection, init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO items (source, title, url) VALUES (?, ?, ?)",
        ("nuvemmag", "test haber", "https://example.com/1"),
    )
    conn.commit()
    item_id = conn.execute("SELECT id FROM items WHERE url = ?", ("https://example.com/1",)).fetchone()[0]
    conn.close()
    return db_path, item_id


def test_mark_read_sets_is_read(tmp_path, monkeypatch):
    from ai_radar.database import get_connection

    db_path, item_id = _make_test_db(tmp_path)
    monkeypatch.setattr(web, "get_connection", lambda: get_connection(db_path))

    client = TestClient(web.app)
    resp = client.post(f"/api/items/{item_id}/mark-read")

    assert resp.status_code == 200
    assert resp.json() == {"id": item_id, "is_read": True}

    conn = get_connection(db_path)
    row = conn.execute("SELECT is_read FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    assert row[0] == 1


def test_toggle_save_flips_state_each_call(tmp_path, monkeypatch):
    from ai_radar.database import get_connection

    db_path, item_id = _make_test_db(tmp_path)
    monkeypatch.setattr(web, "get_connection", lambda: get_connection(db_path))

    client = TestClient(web.app)

    resp1 = client.post(f"/api/items/{item_id}/toggle-save")
    assert resp1.json() == {"id": item_id, "is_saved": True}

    resp2 = client.post(f"/api/items/{item_id}/toggle-save")
    assert resp2.json() == {"id": item_id, "is_saved": False}


def test_toggle_save_returns_404_for_unknown_item(tmp_path, monkeypatch):
    from ai_radar.database import get_connection

    db_path, _ = _make_test_db(tmp_path)
    monkeypatch.setattr(web, "get_connection", lambda: get_connection(db_path))

    client = TestClient(web.app)
    resp = client.post("/api/items/999999/toggle-save")

    assert resp.status_code == 404


def _make_topic_videos_db(tmp_path, rows=()):
    """rows: [(topic, video_id, title, url, engagement_score), ...]"""
    from ai_radar.database import get_connection, init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = get_connection(db_path)
    for topic, video_id, title, url, score in rows:
        conn.execute(
            "INSERT INTO topic_videos (topic, video_id, title, url, engagement_score) VALUES (?, ?, ?, ?, ?)",
            (topic, video_id, title, url, score),
        )
    conn.commit()
    conn.close()
    return db_path


def test_list_topic_videos_returns_cached_rows_sorted_by_engagement(tmp_path, monkeypatch):
    db_path = _make_topic_videos_db(tmp_path, [
        ("Claude", "v1", "Dusuk Etkilesim", "https://youtube.com/v1", 10),
        ("Claude", "v2", "Yuksek Etkilesim", "https://youtube.com/v2", 500),
        ("OpenAI", "v3", "Baska Konu", "https://youtube.com/v3", 999),
    ])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))

    client = TestClient(web.app)
    resp = client.get("/api/topic-videos", params={"topic": "Claude"})

    assert resp.status_code == 200
    data = resp.json()
    assert [v["video_id"] for v in data] == ["v2", "v1"]


def test_refresh_topic_videos_calls_collector_and_replaces_cache(tmp_path, monkeypatch):
    db_path = _make_topic_videos_db(tmp_path, [
        ("Claude", "old", "Eski Video", "https://youtube.com/old", 1),
    ])
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))
    monkeypatch.setattr(web.config, "YOUTUBE_API_KEY", "sahte-anahtar")

    def fake_collect_for_topic(topic):
        return [{
            "topic": topic, "video_id": "new", "title": "Yeni Video",
            "url": "https://youtube.com/new", "channel_title": "Kanal", "published_at": "2026-07-01T00:00:00Z",
            "image_url": None, "view_count": 100, "like_count": 10, "comment_count": 2, "engagement_score": 1200,
        }]

    monkeypatch.setattr(web.youtube_topics, "collect_for_topic", fake_collect_for_topic)

    client = TestClient(web.app)
    resp = client.post("/api/refresh-topic-videos", params={"topic": "Claude"})

    assert resp.status_code == 200
    assert resp.json() == {"topic": "Claude", "result_count": 1}

    listed = client.get("/api/topic-videos", params={"topic": "Claude"}).json()
    assert [v["video_id"] for v in listed] == ["new"]  # eski satır silinmiş olmali


def test_refresh_topic_videos_requires_api_key(tmp_path, monkeypatch):
    db_path = _make_topic_videos_db(tmp_path)
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))
    monkeypatch.setattr(web.config, "YOUTUBE_API_KEY", None)

    client = TestClient(web.app)
    resp = client.post("/api/refresh-topic-videos", params={"topic": "Claude"})

    assert resp.status_code == 400


def test_refresh_topic_videos_returns_502_on_youtube_api_error(tmp_path, monkeypatch):
    db_path = _make_topic_videos_db(tmp_path)
    monkeypatch.setattr(web, "get_connection", lambda: web_get_connection(db_path))
    monkeypatch.setattr(web.config, "YOUTUBE_API_KEY", "sahte-anahtar")

    def failing_collect(topic):
        raise RuntimeError("YouTube kota hatasi")

    monkeypatch.setattr(web.youtube_topics, "collect_for_topic", failing_collect)

    client = TestClient(web.app)
    resp = client.post("/api/refresh-topic-videos", params={"topic": "Claude"})

    assert resp.status_code == 502
