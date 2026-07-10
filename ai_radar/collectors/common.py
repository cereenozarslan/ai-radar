"""Tüm toplayıcıların ortak kullandığı veritabanına yazma fonksiyonu."""

from pathlib import Path

from ai_radar.database import get_connection


def save_items(items: list[dict], db_path: Path | None = None) -> int:
    """Kayıtları items tablosuna ekler.

    url sütunundaki UNIQUE kısıtı sayesinde aynı url'e sahip bir kayıt
    zaten varsa INSERT OR IGNORE onu sessizce atlar (dedup).
    Döndürülen değer: gerçekten eklenen (tekrar olmayan) kayıt sayısı.
    """
    conn = get_connection(db_path)
    added = 0
    try:
        for item in items:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO items (source, title, url, content, author, published_at, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["source"],
                    item["title"],
                    item["url"],
                    item.get("content"),
                    item.get("author"),
                    item.get("published_at"),
                    item.get("image_url"),
                ),
            )
            if cursor.rowcount > 0:
                added += 1
        conn.commit()
    finally:
        conn.close()
    return added
