"""Sinyal skoru: ücretsiz, kural tabanlı 1-10 arası "önem" puanı.

LLM kullanmaz (bkz. schema.sql'deki signal_score/signal_reason yorumu — orijinal
niyet LLM'diydi, ama kullanıcı ücretsiz bir formül istedi). İki bileşeni birleştirir:

  - popülerlik: kaydın, KENDİ KAYNAĞININ (NuvemMag/GitHub/X) popularity dağılımı
    içindeki yüzdelik dilimi (0-1). Kaynaklar arası ham sayılar karşılaştırılamaz
    (GitHub yıldızı onlarca-binlerce, NuvemMag görüntülenmesi onlarca-yüzlerce),
    bu yüzden her kaynak kendi içinde sıralanır.
  - tazelik: fetched_at'e göre üstel azalan bir eğri (yarı ömür FRESHNESS_HALF_LIFE_HOURS).
    published_at yerine fetched_at kullanılıyor çünkü GitHub Trending'de published_at
    hiç yok (repo'ların "yayın" tarihi olmaz).

Popülerlik dağılımı yeni kayıtlar geldikçe değiştiği için skor veritabanına
yazılmaz; her /api/items isteğinde bellek içinde taze hesaplanır.
"""

from datetime import datetime, timezone

FRESHNESS_HALF_LIFE_HOURS = 48
_NEUTRAL_POPULARITY_PERCENTILE = 0.5


def _parse_fetched_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _freshness_component(fetched_at: str | None, now: datetime) -> float:
    dt = _parse_fetched_at(fetched_at)
    if dt is None:
        return _NEUTRAL_POPULARITY_PERCENTILE
    hours = max(0.0, (now - dt).total_seconds() / 3600)
    return 0.5 ** (hours / FRESHNESS_HALF_LIFE_HOURS)


def _popularity_percentiles_by_url(source_items: list[dict]) -> dict[str, float]:
    """Bir kaynağın kendi kayıtları içinde url -> 0-1 yüzdelik dilim eşlemesi döner."""
    with_pop = sorted(
        (it for it in source_items if it.get("popularity") is not None),
        key=lambda it: it["popularity"],
    )
    n = len(with_pop)
    return {
        it["url"]: (rank / (n - 1) if n > 1 else 1.0)
        for rank, it in enumerate(with_pop)
    }


def compute_signal_scores(items: list[dict], now: datetime | None = None) -> None:
    """Her item dict'ine, kaynağının kendi dağılımına göre 1-10 arası 'signal_score' ekler.

    Bellek içindeki dict'leri yerinde (in-place) günceller; her item'ın "source",
    "url", "popularity" ve "fetched_at" alanlarına sahip olduğu varsayılır.
    """
    now = now or datetime.now(timezone.utc)

    by_source: dict[str, list[dict]] = {}
    for it in items:
        by_source.setdefault(it["source"], []).append(it)

    for source_items in by_source.values():
        percentile_by_url = _popularity_percentiles_by_url(source_items)
        for it in source_items:
            popularity_component = percentile_by_url.get(it["url"], _NEUTRAL_POPULARITY_PERCENTILE)
            freshness_component = _freshness_component(it.get("fetched_at"), now)
            raw = 0.5 * popularity_component + 0.5 * freshness_component
            it["signal_score"] = round(1 + raw * 9)
