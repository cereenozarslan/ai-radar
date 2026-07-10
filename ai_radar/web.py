"""Faz 4'ün öne çekilmiş, tek sayfalık minimal parçası.

Tek bir sayfada: (1) tüm kaynaklardan (NuvemMag, GitHub Trending, X)
toplanan kayıtların canlı görünümü, (2) X için doğal dilde arama yapıp
filtreleri (zaman aralığı, etkileşim eşiği) kendi kendine değiştirebileceğiniz
bir arama kutusu. Anthropic API kullanmıyor — query_parser.py'deki ücretsiz,
kural tabanlı ayrıştırıcıyı kullanıyor.

DİKKAT: Her arama, GERÇEK bir X API isteği gönderir (kredi harcar).

Çalıştırmak için:
    uvicorn ai_radar.web:app --reload
Sonra tarayıcıda http://127.0.0.1:8000 açın.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from ai_radar.collectors import x_twitter
from ai_radar.collectors.common import save_items
from ai_radar.config import config
from ai_radar.database import get_connection
from ai_radar.query_parser import parse_natural_query

app = FastAPI(title="AI-Radar — X Arama")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/items")
def list_items():
    """Veritabanındaki tüm kayıtları (kaynak bazında) döner — tek sayfalık görünüm için."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT source, title, url, author, published_at, image_url, fetched_at "
        "FROM items ORDER BY source, fetched_at DESC"
    ).fetchall()
    conn.close()

    cols = ["source", "title", "url", "author", "published_at", "image_url", "fetched_at"]
    return [dict(zip(cols, row)) for row in rows]


@app.get("/api/search")
def search(q: str):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Arama metni boş olamaz.")

    parsed = parse_natural_query(q)

    try:
        items = x_twitter.collect(
            topic=parsed["topic"],
            hours=parsed["hours"],
            min_engagement=parsed["min_engagement"],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"X API hatası: {exc}") from exc

    added = save_items(items)

    return {
        "query": q,
        "interpreted": parsed,
        "result_count": len(items),
        "added_count": added,
        "items": items,
    }


@app.get("/api/following-digest")
def following_digest(hours: float = 36):
    """Kullanıcının X'te takip ettiği hesapların son `hours` saatteki gönderilerini toplar.

    X_FOLLOW_USERNAME .env'de tanımlı olmalı. Manuel olarak (bir 'yenile' butonuyla)
    tetiklenmesi amaçlanır — takip listesi büyükse birden fazla gerçek X API isteği
    gönderir (kredi harcar), bu yüzden sayfa her açıldığında otomatik çağrılmaz.
    """
    if not config.X_FOLLOW_USERNAME:
        raise HTTPException(
            status_code=400,
            detail="X_FOLLOW_USERNAME .env dosyasında tanımlı değil.",
        )

    try:
        items = x_twitter.collect_following_digest(config.X_FOLLOW_USERNAME, hours=hours)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"X API hatası: {exc}") from exc

    added = save_items(items)

    return {
        "hours": hours,
        "result_count": len(items),
        "added_count": added,
        "items": items,
    }
