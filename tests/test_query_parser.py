from ai_radar.query_parser import parse_natural_query


def test_parses_users_original_example_sentence():
    """Kullanıcının verdiği örnek cümle doğru şekilde ayrıştırılmalı.

    "gelişmesi" gibi betimleyici kelimeler ve iyelik eki ("Claude'ın")
    temizlenerek geriye asıl aranacak terim ("Claude") kalmalı — aksi halde
    X araması bu Türkçe ifadeyi tam öbek olarak arar ve hiçbir sonuç bulamaz.
    """
    result = parse_natural_query(
        "Claude'ın son gelişmesi hakkında etkileşimi yüksek son 24 saatte "
        "paylaşılmış tweetleri getir"
    )
    assert result["topic"] == "Claude"
    assert result["hours"] == 24
    assert result["min_engagement"] == 20


def test_strips_turkish_possessive_suffix_from_proper_nouns():
    result = parse_natural_query("OpenAI'nin yeni duyurusu hakkında tweetler")
    assert result["topic"] == "OpenAI"


def test_parses_days_and_popular_keyword():
    result = parse_natural_query("Meta Muse ile ilgili son 3 günde paylaşılan popüler tweetler")
    assert result["topic"] == "Meta Muse"
    assert result["hours"] == 72
    assert result["min_engagement"] == 20


def test_parses_topic_only_without_filters():
    result = parse_natural_query("Fable 5")
    assert result["topic"] == "Fable 5"
    assert result["hours"] is None
    assert result["min_engagement"] == 0


def test_clamps_hours_to_x_api_maximum():
    """X'in recent search uç noktası en fazla 168 saat (7 gün) destekliyor."""
    result = parse_natural_query("son 30 günde paylaşılan GPT-5 tweetleri")
    assert result["hours"] == 168


def test_bugun_keyword_maps_to_24_hours():
    result = parse_natural_query("bugün paylaşılan Claude tweetleri")
    assert result["hours"] == 24


def test_filler_words_removed_from_topic():
    result = parse_natural_query("sadece GPT-5 hakkında viral tweetleri bana getir")
    assert result["topic"] == "GPT-5"
    assert result["min_engagement"] == 20
