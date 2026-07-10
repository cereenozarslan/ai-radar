from fastapi.testclient import TestClient

import ai_radar.web as web

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


def test_following_digest_returns_items(monkeypatch):
    def fake_digest(username, hours=36):
        assert username == "birkullanici"
        assert hours == 36
        return [{
            "source": "x_following", "title": "örnek", "url": "https://x.com/i/web/status/1",
            "content": "örnek", "author": "biri", "published_at": None,
        }]

    monkeypatch.setattr(web.config, "X_FOLLOW_USERNAME", "birkullanici")
    monkeypatch.setattr(web.x_twitter, "collect_following_digest", fake_digest)
    monkeypatch.setattr(web, "save_items", lambda items: len(items))

    client = TestClient(web.app)
    resp = client.get("/api/following-digest")

    assert resp.status_code == 200
    data = resp.json()
    assert data["result_count"] == 1
    assert data["added_count"] == 1
    assert data["items"][0]["source"] == "x_following"


def test_following_digest_requires_configured_username(monkeypatch):
    monkeypatch.setattr(web.config, "X_FOLLOW_USERNAME", None)

    client = TestClient(web.app)
    resp = client.get("/api/following-digest")

    assert resp.status_code == 400


def test_following_digest_returns_502_on_x_api_error(monkeypatch):
    monkeypatch.setattr(web.config, "X_FOLLOW_USERNAME", "birkullanici")

    def failing_digest(username, hours=36):
        raise RuntimeError("X API kota doldu")

    monkeypatch.setattr(web.x_twitter, "collect_following_digest", failing_digest)

    client = TestClient(web.app)
    resp = client.get("/api/following-digest")

    assert resp.status_code == 502


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
