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
        "author", "published_at", "image_url", "signal_score",
        "signal_reason", "is_read", "is_saved", "popularity", "fetched_at",
    }


def test_init_db_migrates_old_database_missing_new_columns(tmp_path):
    """image_url/is_read/is_saved eklenmeden önce oluşturulmuş bir veritabanı,
    tekrar init_db() çağrıldığında bu sütunları sonradan kazanmalı (veri kaybı olmadan)."""
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            content TEXT,
            author TEXT,
            published_at TEXT,
            signal_score INTEGER,
            signal_reason TEXT,
            fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute(
        "INSERT INTO items (source, title, url) VALUES (?, ?, ?)",
        ("nuvemmag", "eski kayıt", "https://example.com/eski"),
    )
    conn.commit()
    conn.close()

    init_db(db_path)

    conn = get_connection(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
    row = conn.execute(
        "SELECT title, image_url, is_read, is_saved, popularity FROM items WHERE url = ?",
        ("https://example.com/eski",),
    ).fetchone()
    conn.close()

    assert {"image_url", "is_read", "is_saved", "popularity"} <= columns
    assert row == ("eski kayıt", None, 0, 0, None)


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
