from datetime import datetime, timedelta, timezone

from ai_radar.topic_trends import compute_topic_growth

NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)


def _iso(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).isoformat()


def test_no_snapshots_returns_no_growth():
    result = compute_topic_growth([], now=NOW)

    assert result == {
        "recent_engagement": 0,
        "prior_engagement": 0,
        "growth_pct": None,
        "is_rising": False,
    }


def test_only_recent_snapshots_cannot_compute_growth_without_baseline():
    """Önceki pencerede hiç veri yoksa (henüz yeterli geçmiş birikmemiş),
    büyüme hesaplanamamalı — sıfıra bölme riski olmamalı."""
    snapshots = [(_iso(1), 50), (_iso(5), 30)]

    result = compute_topic_growth(snapshots, now=NOW)

    assert result["recent_engagement"] == 80
    assert result["prior_engagement"] == 0
    assert result["growth_pct"] is None
    assert result["is_rising"] is False


def test_flags_rising_when_growth_meets_threshold():
    """Son 12 saat, önceki 12 saatin en az 2 katıysa (>=%100 artış) yükseliyor sayılmalı."""
    snapshots = [
        (_iso(2), 100),  # son 12 saat penceresinde
        (_iso(18), 40),  # onceki 12 saat penceresinde (12-24 saat arasi)
    ]

    result = compute_topic_growth(snapshots, now=NOW)

    assert result["recent_engagement"] == 100
    assert result["prior_engagement"] == 40
    assert result["growth_pct"] == 150
    assert result["is_rising"] is True


def test_does_not_flag_rising_below_threshold():
    """Artış var ama %100'ün altındaysa yükseliyor sayılmamalı."""
    snapshots = [(_iso(2), 60), (_iso(18), 40)]

    result = compute_topic_growth(snapshots, now=NOW)

    assert result["growth_pct"] == 50
    assert result["is_rising"] is False


def test_negative_growth_is_not_rising():
    """Son pencere öncekinden düşükse (etkileşim azalmış), yükseliyor sayılmamalı,
    growth_pct negatif olabilir."""
    snapshots = [(_iso(2), 10), (_iso(18), 40)]

    result = compute_topic_growth(snapshots, now=NOW)

    assert result["growth_pct"] == -75
    assert result["is_rising"] is False


def test_snapshots_older_than_24_hours_are_ignored():
    """24 saatten eski anlık görüntüler hiçbir pencereye dahil edilmemeli."""
    snapshots = [(_iso(2), 100), (_iso(18), 40), (_iso(30), 999)]

    result = compute_topic_growth(snapshots, now=NOW)

    assert result["recent_engagement"] == 100
    assert result["prior_engagement"] == 40


def test_window_boundaries_are_inclusive_of_edges():
    """Tam 12 saat önceki bir kayıt 'son' pencereye, tam 24 saat önceki 'önceki'
    pencereye dahil olmalı (sınır değerlerde veri kaybı olmamalı)."""
    snapshots = [(_iso(12), 20), (_iso(24), 10)]

    result = compute_topic_growth(snapshots, now=NOW)

    assert result["recent_engagement"] == 20
    assert result["prior_engagement"] == 10
