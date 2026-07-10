from ai_radar.collectors.parsing import parse_count


def test_parse_count_handles_plain_number():
    assert parse_count("73") == 73


def test_parse_count_handles_thousands_separator():
    assert parse_count("6,776") == 6776


def test_parse_count_handles_k_suffix():
    assert parse_count("12.3k") == 12300


def test_parse_count_handles_m_suffix():
    assert parse_count("1.5m") == 1_500_000


def test_parse_count_returns_none_for_empty_or_invalid():
    assert parse_count("") is None
    assert parse_count(None) is None
    assert parse_count("bilinmeyen") is None
