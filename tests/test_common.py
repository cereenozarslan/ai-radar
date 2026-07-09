from ai_radar.collectors.common import save_items
from ai_radar.database import get_connection, init_db


def test_save_items_deduplicates_by_url(tmp_path):
    """Aynı url'e sahip iki kayıttan sadece biri veritabanına eklenmeli."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    items = [
        {"source": "hackernews", "title": "Başlık 1", "url": "https://example.com/a"},
        {"source": "github_trending", "title": "Başlık 2 (aynı url)", "url": "https://example.com/a"},
        {"source": "hackernews", "title": "Başlık 3", "url": "https://example.com/b"},
    ]

    added = save_items(items, db_path)

    assert added == 2
    conn = get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    conn.close()
    assert count == 2
