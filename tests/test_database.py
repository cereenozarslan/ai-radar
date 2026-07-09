import sqlite3

import pytest

from ai_radar.database import get_connection, init_db


def test_init_db_creates_items_table(tmp_path):
    """init_db çalıştıktan sonra items tablosu ve beklenen sütunlar var olmalı."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.execute("PRAGMA table_info(items)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert columns == {
        "id", "source", "title", "url", "content",
        "author", "published_at", "signal_score",
        "signal_reason", "fetched_at",
    }


def test_url_unique_constraint_enforced(tmp_path):
    """Aynı url ile ikinci kayıt eklenmeye çalışıldığında dedup için hata fırlatılmalı."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO items (source, title, url) VALUES (?, ?, ?)",
        ("hackernews", "Örnek başlık", "https://example.com/haber"),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO items (source, title, url) VALUES (?, ?, ?)",
            ("hackernews", "Aynı url tekrar", "https://example.com/haber"),
        )
    conn.close()
