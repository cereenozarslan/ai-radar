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


def init_db(db_path: Path | None = None) -> None:
    """schema.sql dosyasını çalıştırarak tabloları (yoksa) oluşturur.

    Ayrıca, daha önce oluşturulmuş (CREATE TABLE IF NOT EXISTS'in dokunmadığı)
    eski veritabanlarına sonradan eklenen sütunları (ör. image_url) da ekler.
    """
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)

        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
        if "image_url" not in existing_columns:
            conn.execute("ALTER TABLE items ADD COLUMN image_url TEXT")

        conn.commit()
    finally:
        conn.close()
