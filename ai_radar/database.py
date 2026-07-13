"""SQLite bağlantısı ve şema kurulumu için yardımcı fonksiyonlar."""

import sqlite3
from pathlib import Path

from ai_radar.config import config

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Verilen (veya config'teki varsayılan) yola bağlı bir sqlite3 bağlantısı döner."""
    path = db_path or config.DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


# schema.sql'deki CREATE TABLE IF NOT EXISTS, tablo daha önce oluşturulmuşsa
# yeni eklenen sütunlara dokunmaz. Buradaki liste, sonradan eklenen her
# sütun için eski veritabanlarını da güncelleyen küçük bir migration listesi.
_COLUMN_MIGRATIONS = [
    ("image_url", "ALTER TABLE items ADD COLUMN image_url TEXT"),
    ("is_read", "ALTER TABLE items ADD COLUMN is_read INTEGER NOT NULL DEFAULT 0"),
    ("is_saved", "ALTER TABLE items ADD COLUMN is_saved INTEGER NOT NULL DEFAULT 0"),
    ("popularity", "ALTER TABLE items ADD COLUMN popularity INTEGER"),
    ("is_online", "ALTER TABLE items ADD COLUMN is_online INTEGER"),
]


def init_db(db_path: Path | None = None) -> None:
    """schema.sql dosyasını çalıştırarak tabloları (yoksa) oluşturur.

    Ayrıca, daha önce oluşturulmuş eski veritabanlarına sonradan eklenen
    sütunları da (_COLUMN_MIGRATIONS üzerinden) ekler.
    """
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)

        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
        for column, ddl in _COLUMN_MIGRATIONS:
            if column not in existing_columns:
                conn.execute(ddl)

        conn.commit()
    finally:
        conn.close()
