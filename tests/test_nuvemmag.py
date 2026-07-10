from ai_radar.collectors.nuvemmag import parse_articles, parse_relative_time

# nuvemmag.com'un gerçek "Son Yazılar" HTML yapısını taklit eden minimal örnek
SAMPLE_HTML = """
<html><body>
<div class="post-list-group">
<article class="uck-card uck-card-list">
    <div class="uck-card--content">
        <div class="uck-card-top">
            <span class="date"><i class="gi gi-clock-o"></i> 14 saat&nbsp;önce</span>
        </div>
        <h3 class="headline"><a href="https://nuvemmag.com/ornek-haber/" rel="bookmark">Örnek Haber Başlığı</a></h3>
        <p>Bu haberin kısa özeti burada yer alıyor.</p>
        <div class="uck-card--meta">
            <span class="entry_author"><a href="https://nuvemmag.com/author/nuvemmag/">Nuvem</a></span>
        </div>
    </div>
</article>
<article class="uck-card uck-card-list">
    <div class="uck-card--content">
        <div class="uck-card-top">
            <span class="date"><i class="gi gi-clock-o"></i> 2 gün&nbsp;önce</span>
        </div>
        <h3 class="headline"><a href="https://nuvemmag.com/ozet-yok-haberi/" rel="bookmark">Özeti Olmayan Haber</a></h3>
    </div>
</article>
</div>
</body></html>
"""


def test_parse_articles_extracts_fields_correctly():
    items = parse_articles(SAMPLE_HTML)

    assert len(items) == 2
    first = items[0]
    assert first["source"] == "nuvemmag"
    assert first["title"] == "Örnek Haber Başlığı"
    assert first["url"] == "https://nuvemmag.com/ornek-haber/"
    assert first["content"] == "Bu haberin kısa özeti burada yer alıyor."
    assert first["author"] == "Nuvem"
    assert first["published_at"] is not None


def test_parse_articles_handles_missing_excerpt_and_author():
    items = parse_articles(SAMPLE_HTML)
    second = items[1]

    assert second["title"] == "Özeti Olmayan Haber"
    assert second["content"] is None
    assert second["author"] is None


def test_parse_relative_time_converts_hours_and_days():
    assert parse_relative_time("14 saat önce") is not None
    assert parse_relative_time("2 gün önce") is not None


def test_parse_relative_time_returns_none_for_unrecognized_text():
    assert parse_relative_time("az önce") is None
