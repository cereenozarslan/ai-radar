from ai_radar.collectors.xai_news import parse_news

# Gercek x.ai/news sayfasinin sadelestirilmis bir ornegi:
# - "one cikan" hero karti h1/h2 kullaniyor, digerleri h3
# - tarih kucuk bir div icinde duz metin ("Mon D, YYYY")
XAI_STYLE_HTML = """
<html><body>
<a href="/news/grok-4-5">
  <div><div>Jul 8, 2026</div></div>
  <h1>Introducing Grok 4.5</h1>
  <h2>Introducing Grok 4.5</h2>
</a>

<a href="/news/grok-voice-agent-builder">
  <img src="/images/news/grok-voice-agent-builder.webp"/>
  <div>Jul 1, 2026</div>
  <h3>Introducing the Voice Agent Builder</h3>
</a>

<a href="/news/old-post">
  <div>Nov 3, 2023</div>
  <h3>Cok eski bir haber</h3>
</a>

<a href="/news/no-date-yet">
  <h3>Tarihi olmayan link, atlanmali</h3>
</a>
</body></html>
"""


def test_parse_news_extracts_hero_card_title_from_h1_or_h2():
    items = parse_news(XAI_STYLE_HTML, base_url="https://x.ai/news", max_age_days=None)
    item = next(it for it in items if it["url"] == "https://x.ai/news/grok-4-5")

    assert item["source"] == "official_blog"
    assert item["author"] == "xAI"
    assert item["title"] == "Introducing Grok 4.5"
    assert item["published_at"] == "2026-07-08T00:00:00+00:00"


def test_parse_news_extracts_regular_card_with_h3_and_image():
    items = parse_news(XAI_STYLE_HTML, base_url="https://x.ai/news", max_age_days=None)
    item = next(it for it in items if it["url"] == "https://x.ai/news/grok-voice-agent-builder")

    assert item["title"] == "Introducing the Voice Agent Builder"
    assert item["image_url"] == "https://x.ai/images/news/grok-voice-agent-builder.webp"


def test_parse_news_skips_links_without_a_date():
    items = parse_news(XAI_STYLE_HTML, base_url="https://x.ai/news", max_age_days=None)
    urls = [it["url"] for it in items]
    assert "https://x.ai/news/no-date-yet" not in urls


def test_parse_news_filters_out_entries_older_than_max_age_days():
    items = parse_news(XAI_STYLE_HTML, base_url="https://x.ai/news", max_age_days=60)
    urls = {it["url"] for it in items}
    assert "https://x.ai/news/old-post" not in urls
    assert "https://x.ai/news/grok-4-5" in urls


def test_parse_news_handles_page_with_no_articles():
    assert parse_news("<html><body></body></html>", base_url="https://x.ai/news") == []
