from datetime import datetime, timedelta, timezone

from ai_radar.signal_score import compute_signal_scores

NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat()


def test_higher_popularity_scores_higher_within_same_source():
    """Aynı kaynakta, aynı tazelikte, popülerliği yüksek olan daha yüksek puan almalı."""
    items = [
        {"source": "github_trending", "url": "u1", "popularity": 5, "fetched_at": _iso(NOW)},
        {"source": "github_trending", "url": "u2", "popularity": 5000, "fetched_at": _iso(NOW)},
    ]
    compute_signal_scores(items, now=NOW)

    assert items[1]["signal_score"] > items[0]["signal_score"]


def test_fresher_item_scores_higher_at_equal_popularity():
    """Aynı kaynakta, aynı popülerlikte, daha yeni (fetched_at'i şimdiye yakın) daha yüksek puan almalı."""
    items = [
        {"source": "nuvemmag", "url": "u1", "popularity": 10, "fetched_at": _iso(NOW - timedelta(hours=200))},
        {"source": "nuvemmag", "url": "u2", "popularity": 10, "fetched_at": _iso(NOW)},
    ]
    compute_signal_scores(items, now=NOW)

    assert items[1]["signal_score"] > items[0]["signal_score"]


def test_popularity_is_normalized_per_source_not_globally():
    """GitHub'ın binlerce yıldızı ile NuvemMag'ın onlarca görüntülenmesi doğrudan
    karşılaştırılmamalı; her kaynak kendi dağılımı içinde değerlendirilmeli."""
    items = [
        # NuvemMag içinde bu kaydın popülerliği (73), o kaynağın en yükseği (en iyi yüzdelik dilim)
        {"source": "nuvemmag", "url": "n1", "popularity": 5, "fetched_at": _iso(NOW)},
        {"source": "nuvemmag", "url": "n2", "popularity": 73, "fetched_at": _iso(NOW)},
        # GitHub içinde bu kaydın popülerliği (6776) o kaynağın en yükseği olsun
        {"source": "github_trending", "url": "g1", "popularity": 100, "fetched_at": _iso(NOW)},
        {"source": "github_trending", "url": "g2", "popularity": 6776, "fetched_at": _iso(NOW)},
    ]
    compute_signal_scores(items, now=NOW)

    # Her iki kaynaktaki "en popüler" kayıt da kendi kaynağında en yüksek puanı almalı,
    # ham sayılar (73 vs 6776) çok farklı olsa da ikisi de üst sınıra (aynı seviyeye) ulaşmalı
    assert items[1]["signal_score"] == items[3]["signal_score"]


def test_missing_popularity_gets_neutral_score_not_lowest():
    """popularity None olan bir kayıt, en düşük puanı almamalı (nötr muamele görmeli)."""
    items = [
        {"source": "github_trending", "url": "u1", "popularity": None, "fetched_at": _iso(NOW)},
        {"source": "github_trending", "url": "u2", "popularity": 1, "fetched_at": _iso(NOW)},
        {"source": "github_trending", "url": "u3", "popularity": 9999, "fetched_at": _iso(NOW)},
    ]
    compute_signal_scores(items, now=NOW)

    assert items[0]["signal_score"] > items[1]["signal_score"]
    assert items[0]["signal_score"] < items[2]["signal_score"]


def test_single_item_source_does_not_crash_and_scores_high():
    """Kaynakta tek kayıt varsa (yüzdelik dilim hesaplanamaz), hata vermemeli;
    tek kayıt kendi kaynağında zaten 'en popüler' sayılır."""
    items = [{"source": "x_twitter", "url": "u1", "popularity": 42, "fetched_at": _iso(NOW)}]

    compute_signal_scores(items, now=NOW)

    assert items[0]["signal_score"] == 10


def test_all_missing_popularity_in_source_does_not_crash():
    items = [
        {"source": "github_trending", "url": "u1", "popularity": None, "fetched_at": _iso(NOW)},
        {"source": "github_trending", "url": "u2", "popularity": None, "fetched_at": _iso(NOW - timedelta(hours=100))},
    ]
    compute_signal_scores(items, now=NOW)

    assert items[0]["signal_score"] > items[1]["signal_score"]


def test_score_is_always_between_1_and_10():
    items = [
        {"source": "nuvemmag", "url": "u1", "popularity": 1, "fetched_at": _iso(NOW - timedelta(days=30))},
        {"source": "nuvemmag", "url": "u2", "popularity": 999999, "fetched_at": _iso(NOW)},
    ]
    compute_signal_scores(items, now=NOW)

    for it in items:
        assert 1 <= it["signal_score"] <= 10


def test_missing_fetched_at_does_not_crash():
    items = [{"source": "x_twitter", "url": "u1", "popularity": 5, "fetched_at": None}]
    compute_signal_scores(items, now=NOW)
    assert 1 <= items[0]["signal_score"] <= 10
