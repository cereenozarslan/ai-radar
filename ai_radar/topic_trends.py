"""Takip edilen bir konunun X'teki etkileşim geçmişinden "yükseliyor mu" hesaplar.

Kural: son 12 saatteki toplam etkileşim, önceki 12 saatteki (12-24 saat önce)
toplam etkileşimden en az RISING_THRESHOLD_PCT kadar fazlaysa "yükseliyor" sayılır.
Önceki pencerede hiç veri yoksa (henüz yeterli geçmiş birikmemişse) büyüme
hesaplanamaz (growth_pct None kalır) — sıfıra bölme riskinden kaçınmak için.

Veri kaynağı: topic_engagement_snapshots tablosu, collect_topic_snapshot() ile
periyodik olarak (ücretli X istekleriyle) doldurulur; bu modül sadece o ham
(checked_at, total_engagement) çiftlerini yorumlayan saf/test edilebilir mantıktır.
"""

from datetime import datetime, timezone

RISING_THRESHOLD_PCT = 100
RECENT_WINDOW_HOURS = 12
PRIOR_WINDOW_HOURS = 24


def _parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def compute_topic_growth(snapshots: list[tuple[str, int]], now: datetime | None = None) -> dict:
    """snapshots: [(checked_at_iso, total_engagement), ...] — sırasız olabilir."""
    now = now or datetime.now(timezone.utc)

    recent_sum = 0
    prior_sum = 0
    for checked_at, total_engagement in snapshots:
        hours_ago = (now - _parse(checked_at)).total_seconds() / 3600
        if 0 <= hours_ago <= RECENT_WINDOW_HOURS:
            recent_sum += total_engagement
        elif RECENT_WINDOW_HOURS < hours_ago <= PRIOR_WINDOW_HOURS:
            prior_sum += total_engagement

    growth_pct = None
    if prior_sum > 0:
        growth_pct = round((recent_sum - prior_sum) / prior_sum * 100)

    return {
        "recent_engagement": recent_sum,
        "prior_engagement": prior_sum,
        "growth_pct": growth_pct,
        "is_rising": growth_pct is not None and growth_pct >= RISING_THRESHOLD_PCT,
    }
