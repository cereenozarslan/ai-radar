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

import asyncio
import contextlib
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from ai_radar.collectors import (
    coderspace_events,
    github_trending,
    kommunity_events,
    meetup_events,
    nuvemmag,
    x_twitter,
    youtube_topics,
)
from ai_radar.collectors.common import save_items
from ai_radar.config import config
from ai_radar.database import get_connection, init_db
from ai_radar.query_parser import parse_natural_query
from ai_radar.signal_score import compute_signal_scores
from ai_radar.topic_trends import compute_topic_growth

# NuvemMag ve GitHub Trending ücretsiz (X'in aksine kredi harcamıyor), bu yüzden
# sunucu ayakta olduğu sürece kendiliğinden bu aralıkla yenilenirler.
FREE_COLLECTOR_REFRESH_SECONDS = 3600

# Takip edilen konuların X'teki etkileşimini periyodik "anlık görüntülerle" izliyoruz
# (yükseliş tespiti için). Bu GERÇEK, ücretli X istekleri olduğu için NuvemMag/GitHub'dan
# çok daha seyrek çalışıyor — günde 6 kez (her konu için).
TOPIC_SNAPSHOT_REFRESH_SECONDS = 4 * 3600

# Bu üç kaynağın da resmi/belgelenmiş bir API'si yok; belgelenmemiş uç
# noktalara karşı nazik olmak için diğer ücretsiz toplayıcılardan çok daha
# seyrek çalışıyor (etkinlik listeleri zaten saatlik değişmiyor).
EVENTS_REFRESH_SECONDS = 6 * 3600
EVENT_COLLECTORS = (
    ("kommunity.com", kommunity_events.collect),
    ("meetup.com", meetup_events.collect),
    ("coderspace.io", coderspace_events.collect),
)

# YouTube Data API v3 ücretsiz günlük kotası (10.000 birim) çok geniş, ama
# video istatistikleri (izlenme/beğeni/yorum) saatlik değişmediği için günde
# iki kez yenilemek yeterli.
TOPIC_VIDEOS_REFRESH_SECONDS = 12 * 3600


def _save_topic_videos(topic: str, videos: list[dict]) -> None:
    """Bir konunun video önbelleğini TAMAMEN yeniler (eski satırlar silinir).

    topic_engagement_snapshots'ın aksine burada zaman içindeki geçmişi
    biriktirmiyoruz — her yenileme, o konu için her zaman GÜNCEL bir video
    listesi olmalı.
    """
    conn = get_connection()
    conn.execute("DELETE FROM topic_videos WHERE topic = ?", (topic,))
    for video in videos:
        conn.execute(
            """
            INSERT INTO topic_videos
                (topic, video_id, title, url, channel_title, published_at, image_url, view_count, like_count, comment_count, engagement_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video["topic"], video["video_id"], video["title"], video["url"],
                video.get("channel_title"), video.get("published_at"), video.get("image_url"),
                video.get("view_count"), video.get("like_count"), video.get("comment_count"),
                video.get("engagement_score"),
            ),
        )
    conn.commit()
    conn.close()


async def _refresh_free_collectors_periodically() -> None:
    collectors = (("NuvemMag", nuvemmag.collect), ("GitHub Trending", github_trending.collect))
    while True:
        for name, collect in collectors:
            try:
                items = await asyncio.to_thread(collect)
                added = await asyncio.to_thread(save_items, items)
                print(f"[otomatik yenileme] {name}: {added} yeni kayıt eklendi.")
            except Exception as exc:
                print(f"[otomatik yenileme] {name} başarısız: {exc}")
        await asyncio.sleep(FREE_COLLECTOR_REFRESH_SECONDS)


async def _refresh_events_periodically() -> None:
    # Diğer ücretsiz toplayıcılarla aynı desen: sunucu açılır açılmaz hemen bir
    # kez kontrol eder, sonra döngü sonunda bekler. Kaynaklardan biri
    # başarısız olsa (site yapısı değişmiş vb.) diğerlerini etkilemez.
    while True:
        for name, collect in EVENT_COLLECTORS:
            try:
                items = await asyncio.to_thread(collect)
                added = await asyncio.to_thread(save_items, items)
                print(f"[otomatik yenileme] Etkinlikler ({name}): {added} yeni kayıt eklendi.")
            except Exception as exc:
                print(f"[otomatik yenileme] Etkinlikler ({name}) başarısız: {exc}")
        await asyncio.sleep(EVENTS_REFRESH_SECONDS)


async def _snapshot_followed_topics_periodically() -> None:
    # Ücretsiz koleksiyoncular gibi sunucu her açıldığında HEMEN bir kez kontrol
    # ediyor (sonra döngü sonunda bekliyor) — yoksa kullanıcı sunucuyu sık sık
    # kapatıp açtığında 4 saatlik bekleme hiç tamamlanmıyor ve geçmiş hiç birikmiyor.
    while True:
        conn = get_connection()
        topics = [r[0] for r in conn.execute("SELECT topic FROM followed_topics").fetchall()]
        conn.close()

        for topic in topics:
            try:
                snapshot = await asyncio.to_thread(x_twitter.collect_topic_snapshot, topic)
                conn = get_connection()
                conn.execute(
                    "INSERT INTO topic_engagement_snapshots (topic, total_engagement, mention_count) VALUES (?, ?, ?)",
                    (snapshot["topic"], snapshot["total_engagement"], snapshot["mention_count"]),
                )
                conn.commit()
                conn.close()
                print(
                    f"[konu anlık görüntüsü] {topic}: {snapshot['mention_count']} gönderi, "
                    f"{snapshot['total_engagement']} toplam etkileşim"
                )
            except Exception as exc:
                print(f"[konu anlık görüntüsü] {topic} başarısız: {exc}")

        await asyncio.sleep(TOPIC_SNAPSHOT_REFRESH_SECONDS)


async def _refresh_topic_videos_periodically() -> None:
    # Diğer ücretsiz toplayıcılarla aynı desen: hemen bir kez kontrol eder,
    # sonra döngü sonunda bekler. YouTube anahtarı .env'de yoksa (henüz
    # kurulmadıysa) sessizce atlar.
    while True:
        if not config.YOUTUBE_API_KEY:
            await asyncio.sleep(TOPIC_VIDEOS_REFRESH_SECONDS)
            continue

        conn = get_connection()
        topics = [r[0] for r in conn.execute("SELECT topic FROM followed_topics").fetchall()]
        conn.close()

        for topic in topics:
            try:
                videos = await asyncio.to_thread(youtube_topics.collect_for_topic, topic)
                await asyncio.to_thread(_save_topic_videos, topic, videos)
                print(f"[YouTube] {topic}: {len(videos)} video bulundu.")
            except Exception as exc:
                print(f"[YouTube] {topic} başarısız: {exc}")

        await asyncio.sleep(TOPIC_VIDEOS_REFRESH_SECONDS)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Şemaya sonradan eklenen sütunları (ör. is_online) eski veritabanlarına
    # da uygular — bu çağrı olmadan _COLUMN_MIGRATIONS hiç çalışmıyordu ve
    # yeni bir sütun eklendiğinde uygulama sessizce runtime hatası veriyordu.
    init_db()
    free_task = asyncio.create_task(_refresh_free_collectors_periodically())
    events_task = asyncio.create_task(_refresh_events_periodically())
    topic_task = asyncio.create_task(_snapshot_followed_topics_periodically())
    topic_videos_task = asyncio.create_task(_refresh_topic_videos_periodically())
    try:
        yield
    finally:
        free_task.cancel()
        events_task.cancel()
        topic_task.cancel()
        topic_videos_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await free_task
        with contextlib.suppress(asyncio.CancelledError):
            await events_task
        with contextlib.suppress(asyncio.CancelledError):
            await topic_task
        with contextlib.suppress(asyncio.CancelledError):
            await topic_videos_task


app = FastAPI(title="AI-Radar — X Arama", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/items")
def list_items():
    """Veritabanındaki tüm kayıtları (kaynak bazında) döner — tek sayfalık görünüm için."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, source, title, content, url, author, published_at, image_url, is_read, is_saved, popularity, is_online, fetched_at "
        "FROM items ORDER BY source, fetched_at DESC"
    ).fetchall()
    conn.close()

    cols = [
        "id", "source", "title", "content", "url", "author", "published_at",
        "image_url", "is_read", "is_saved", "popularity", "is_online", "fetched_at",
    ]
    items = [dict(zip(cols, row)) for row in rows]
    compute_signal_scores(items)
    return items


@app.post("/api/items/{item_id}/mark-read")
def mark_read(item_id: int):
    """Bir kaydı 'okundu' işaretler (bağlantıya tıklandığında çağrılır)."""
    conn = get_connection()
    conn.execute("UPDATE items SET is_read = 1 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"id": item_id, "is_read": True}


@app.post("/api/items/{item_id}/toggle-save")
def toggle_save(item_id: int):
    """Bir kaydın 'kaydedildi' (yıldızlandı) durumunu tersine çevirir."""
    conn = get_connection()
    row = conn.execute("SELECT is_saved FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")

    new_value = 0 if row[0] else 1
    conn.execute("UPDATE items SET is_saved = ? WHERE id = ?", (new_value, item_id))
    conn.commit()
    conn.close()
    return {"id": item_id, "is_saved": bool(new_value)}


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


@app.post("/api/refresh-x")
def refresh_x(topic: str | None = None):
    """X'ten manuel olarak taze veri çeker: 'topic' verilirse o konuyu ("Konu: X"
    sayfasındaki Yenile için), verilmezse genel AI/LLM taramasını (X platform
    sekmesindeki Yenile için) yeniler.

    Gerçek bir X API isteği gönderir (kredi harcar) — bu yüzden otomatik
    çağrılmaz, sadece kullanıcı görünüm araç çubuğundaki 'Yenile'ye basınca çalışır.
    """
    try:
        items = x_twitter.collect(topic=topic)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"X API hatası: {exc}") from exc

    added = save_items(items)

    return {
        "topic": topic,
        "result_count": len(items),
        "added_count": added,
    }


@app.get("/api/followed-accounts")
def list_followed_accounts():
    """Arayüzden eklenmiş, takip edilen X hesaplarını döner."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, added_at FROM followed_accounts ORDER BY username"
    ).fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "added_at": r[2]} for r in rows]


@app.post("/api/followed-accounts")
def add_followed_account(username: str):
    """Takip listesine bir X kullanıcı adı ekler (baştaki @ varsa temizlenir)."""
    username = username.strip().lstrip("@")
    if not username:
        raise HTTPException(status_code=400, detail="Kullanıcı adı boş olamaz.")

    conn = get_connection()
    try:
        conn.execute("INSERT INTO followed_accounts (username) VALUES (?)", (username,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # zaten listede var, sessizce yoksay
    finally:
        conn.close()

    return {"username": username}


@app.delete("/api/followed-accounts/{account_id}")
def remove_followed_account(account_id: int):
    """Takip listesinden bir hesabı kaldırır."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM followed_accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
    return {"id": account_id}


@app.get("/api/followed-topics")
def list_followed_topics():
    """Takip edilen konuları, biriken X anlık görüntülerinden hesaplanan
    yükseliş (growth) bilgisiyle birlikte döner (bkz. ai_radar/topic_trends.py)."""
    conn = get_connection()
    topics = [r[0] for r in conn.execute("SELECT topic FROM followed_topics ORDER BY topic").fetchall()]

    result = []
    for topic in topics:
        rows = conn.execute(
            "SELECT checked_at, total_engagement FROM topic_engagement_snapshots WHERE topic = ?",
            (topic,),
        ).fetchall()
        growth = compute_topic_growth([(r[0], r[1]) for r in rows])
        result.append({"topic": topic, **growth})
    conn.close()

    return result


@app.post("/api/followed-topics")
def add_followed_topic(topic: str):
    """Takip listesine bir konu ekler (örn. 'OpenAI', 'Anthropic')."""
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Konu boş olamaz.")

    conn = get_connection()
    try:
        conn.execute("INSERT INTO followed_topics (topic) VALUES (?)", (topic,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # zaten listede var, sessizce yoksay
    finally:
        conn.close()

    return {"topic": topic}


@app.delete("/api/followed-topics/{topic}")
def remove_followed_topic(topic: str):
    """Takip listesinden bir konuyu (ve biriken anlık görüntülerini) kaldırır."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM followed_topics WHERE topic = ?", (topic,))
    conn.execute("DELETE FROM topic_engagement_snapshots WHERE topic = ?", (topic,))
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
    return {"topic": topic}


@app.get("/api/following-digest")
def following_digest(hours: float = 36):
    """Takip edilen hesapların son `hours` saatteki gönderilerini toplar.

    İki kaynak birleştirilir: (1) X_FOLLOW_USERNAME .env'de tanımlıysa, o X
    hesabının GERÇEKTEN takip ettiği herkes (X'in "following" uç noktasından
    anlık çekilir), (2) arayüzden manuel eklenen yerel liste. İkisi de aynı
    anda kullanılabilir; sadece biri tanımlıysa sorun olmaz. Manuel olarak
    (bir 'yenile' butonuyla) tetiklenmesi amaçlanır — hesap sayısına bağlı
    olarak birden fazla gerçek X API isteği gönderir (kredi harcar), bu
    yüzden sayfa her açıldığında otomatik çağrılmaz.
    """
    conn = get_connection()
    rows = conn.execute("SELECT username FROM followed_accounts").fetchall()
    conn.close()
    usernames = {r[0] for r in rows}

    if config.X_FOLLOW_USERNAME:
        try:
            usernames.update(x_twitter.get_following_usernames(config.X_FOLLOW_USERNAME))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"X API hatası: {exc}") from exc

    if not usernames:
        raise HTTPException(
            status_code=400,
            detail="Henüz takip edilecek kimse yok — takip listesine bir hesap ekle "
            "(veya .env'de X_FOLLOW_USERNAME tanımla).",
        )

    try:
        items = x_twitter.collect_following_digest_for_usernames(sorted(usernames), hours=hours)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"X API hatası: {exc}") from exc

    added = save_items(items)

    return {
        "hours": hours,
        "usernames": sorted(usernames),
        "result_count": len(items),
        "added_count": added,
        "items": items,
    }


@app.get("/api/topic-videos")
def list_topic_videos(topic: str):
    """Bir konu için önbelleğe alınmış YouTube video önerilerini döner
    (etkileşim skoruna göre sıralı — en üstteki 3'ü arayüzde kart, gerisi liste)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT video_id, title, url, channel_title, published_at, image_url, "
        "view_count, like_count, comment_count, engagement_score "
        "FROM topic_videos WHERE topic = ? ORDER BY engagement_score DESC",
        (topic,),
    ).fetchall()
    conn.close()

    cols = [
        "video_id", "title", "url", "channel_title", "published_at",
        "image_url", "view_count", "like_count", "comment_count", "engagement_score",
    ]
    return [dict(zip(cols, row)) for row in rows]


@app.post("/api/refresh-topic-videos")
def refresh_topic_videos(topic: str):
    """Bir konu için YouTube video önerilerini şimdi (canlı) yeniler.

    YouTube Data API v3'ün ücretsiz kotası içinde kaldığı için (bkz.
    youtube_topics.py) X'teki gibi bir maliyet uyarısı gerekmiyor.
    """
    if not config.YOUTUBE_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="YOUTUBE_API_KEY tanımlı değil — .env dosyasına eklemen gerekiyor.",
        )

    try:
        videos = youtube_topics.collect_for_topic(topic)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"YouTube API hatası: {exc}") from exc

    _save_topic_videos(topic, videos)

    return {"topic": topic, "result_count": len(videos)}
