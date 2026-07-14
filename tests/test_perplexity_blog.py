from ai_radar.collectors.perplexity_blog import parse_blog

# Gercek perplexity.ai/hub/blog sayfasinin sadelestirilmis bir ornegi:
# Framer, her yazi icin gercek bir <time datetime="ISO"> etiketi kullaniyor.
PERPLEXITY_STYLE_HTML = """
<html><body>
<a href="./blog/introducing-computer-for-counsel">
  <img src="https://framerusercontent.com/images/thumb.png"/>
  <h6>Introducing Computer for Counsel</h6>
  <p><time datetime="2026-06-24T00:00:00.000Z">Jun 24, 2026</time></p>
</a>

<a href="./blog/very-old-post">
  <h6>Cok eski bir yazi</h6>
  <p><time datetime="2023-03-28T00:00:00.000Z">Mar 28, 2023</time></p>
</a>

<a href="./blog/no-title-yet">
  <p><time datetime="2026-06-01T00:00:00.000Z">Jun 1, 2026</time></p>
</a>
</body></html>
"""


def test_parse_blog_extracts_title_url_and_iso_date():
    items = parse_blog(PERPLEXITY_STYLE_HTML, base_url="https://www.perplexity.ai/hub/blog", max_age_days=None)
    item = next(it for it in items if "introducing-computer-for-counsel" in it["url"])

    assert item["source"] == "official_blog"
    assert item["author"] == "Perplexity"
    assert item["title"] == "Introducing Computer for Counsel"
    assert item["url"] == "https://www.perplexity.ai/hub/blog/introducing-computer-for-counsel"
    assert item["published_at"] == "2026-06-24T00:00:00.000+00:00"
    assert item["image_url"] == "https://framerusercontent.com/images/thumb.png"


def test_parse_blog_skips_links_without_a_title_heading():
    items = parse_blog(PERPLEXITY_STYLE_HTML, base_url="https://www.perplexity.ai/hub/blog", max_age_days=None)
    urls = [it["url"] for it in items]
    assert not any("no-title-yet" in u for u in urls)


def test_parse_blog_filters_out_entries_older_than_max_age_days():
    items = parse_blog(PERPLEXITY_STYLE_HTML, base_url="https://www.perplexity.ai/hub/blog", max_age_days=60)
    urls = {it["url"] for it in items}
    assert not any("very-old-post" in u for u in urls)


def test_parse_blog_handles_page_with_no_articles():
    assert parse_blog("<html><body></body></html>", base_url="https://www.perplexity.ai/hub/blog") == []
