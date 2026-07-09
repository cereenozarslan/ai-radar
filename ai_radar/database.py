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
    """schema.sql dosyasını çalıştırarak tabloları (yoksa) oluşturur."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
