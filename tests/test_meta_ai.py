from ai_radar.collectors.meta_ai import parse_blog

# Gercek ai.meta.com/blog sayfasinin sadelestirilmis bir ornegi:
# - ust kisimdaki "one cikan" resimli kart tarihsiz (atlanmali)
# - asagidaki "izgara" kartinda hem kategori hem baslik h4'u var (SONUNCU h4 baslik)
# - her karti TEK bir /blog/ linki cevreliyor
META_STYLE_HTML = """
<html><body>
<a href="https://ai.meta.com/blog/introducing-muse-spark-meta-model-api/">
  <div><img src="thumb.png"/></div>
</a>

<div class="_8xm6">
  <p>Blog</p>
  <p>July 09, 2026</p>
  <h4>Research</h4>
  <h4>Introducing Muse Spark 1.1</h4>
  <a href="https://ai.meta.com/blog/introducing-muse-spark-meta-model-api/">Learn More</a>
</div>

<div class="_8xm6">
  <p>March 10, 2026</p>
  <h4>Mapping the World's Forests with Greater Precision</h4>
  <a href="https://ai.meta.com/blog/world-resources-institute-dino-canopy-height-maps-v2/">Learn More</a>
</div>
</body></html>
"""


def test_parse_blog_extracts_title_and_date_from_card_with_category_and_title():
    items = parse_blog(META_STYLE_HTML, max_age_days=None)
    item = next(it for it in items if "introducing-muse-spark" in it["url"])

    assert item["source"] == "official_blog"
    assert item["author"] == "Meta AI"
    assert item["title"] == "Introducing Muse Spark 1.1"
    assert item["published_at"] == "2026-07-09T00:00:00+00:00"


def test_parse_blog_handles_card_with_single_heading():
    items = parse_blog(META_STYLE_HTML, max_age_days=None)
    item = next(it for it in items if "canopy-height-maps" in it["url"])
    assert item["title"] == "Mapping the World's Forests with Greater Precision"
    assert item["published_at"] == "2026-03-10T00:00:00+00:00"


def test_parse_blog_skips_link_occurrence_without_nearby_date():
    # Ust kisimdaki resimli kartin URL'i asagidaki karti ile ayni oldugu icin
    # tekillestirme sonrasi tek kayit kalmali (2 degil).
    items = parse_blog(META_STYLE_HTML, max_age_days=None)
    urls = [it["url"] for it in items]
    assert urls.count("https://ai.meta.com/blog/introducing-muse-spark-meta-model-api/") == 1


def test_parse_blog_filters_out_entries_older_than_max_age_days():
    items = parse_blog(META_STYLE_HTML, max_age_days=60)
    urls = {it["url"] for it in items}
    assert "https://ai.meta.com/blog/world-resources-institute-dino-canopy-height-maps-v2/" not in urls


def test_parse_blog_handles_page_with_no_articles():
    assert parse_blog("<html><body></body></html>") == []
