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
