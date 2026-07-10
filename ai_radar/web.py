"""Faz 4'ün öne çekilmiş, sadece X araması için kurulan minimal parçası.

Kullanıcının kendi kendine, sitenin içinden doğal dilde arama yapıp
filtreleri (zaman aralığı, etkileşim eşiği) değiştirebileceği bir arayüz.
Anthropic API kullanmıyor — query_parser.py'deki ücretsiz, kural tabanlı
ayrıştırıcıyı kullanıyor.

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
from ai_radar.query_parser import parse_natural_query

app = FastAPI(title="AI-Radar — X Arama")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


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
