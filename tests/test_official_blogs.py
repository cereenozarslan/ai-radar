from ai_radar.collectors.official_blogs import parse_feed

# Gerçek OpenAI RSS akışının yapısını taklit eden minimal bir örnek (görselsiz)
OPENAI_STYLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
    <channel>
        <title><![CDATA[OpenAI News]]></title>
        <link>https://openai.com/news</link>
        <item>
            <title><![CDATA[Getting started with ChatGPT]]></title>
            <description><![CDATA[Learn how to use ChatGPT.]]></description>
            <link>https://openai.com/academy/getting-started</link>
            <guid isPermaLink="true">https://openai.com/academy/getting-started</guid>
            <pubDate>Fri, 10 Jul 2026 00:00:00 GMT</pubDate>
        </item>
        <item>
            <description><![CDATA[Baslik olmadan gelen, atlanmasi gereken kayit.]]></description>
            <link>https://openai.com/no-title</link>
            <pubDate>Fri, 10 Jul 2026 00:00:00 GMT</pubDate>
        </item>
    </channel>
</rss>
"""

# Gerçek DeepMind RSS akışının yapısını taklit eden minimal bir örnek
# (media:thumbnail ile görsel içeren)
DEEPMIND_STYLE_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Google DeepMind News</title><link>https://deepmind.google/blog/</link>
<item>
<title>Introducing computer use in Gemini</title>
<link>https://deepmind.google/blog/introducing-computer-use-in-gemini/</link>
<description>Announcing a new capability.</description>
<pubDate>Wed, 24 Jun 2026 16:30:01 +0000</pubDate>
<guid>https://deepmind.google/blog/introducing-computer-use-in-gemini/</guid>
<media:thumbnail url="https://example.com/thumb.jpg"/>
</item>
</channel>
</rss>
"""


def test_parse_feed_extracts_openai_style_entry_fields():
    items = parse_feed(OPENAI_STYLE_RSS, company="OpenAI")

    assert len(items) == 1
    item = items[0]
    assert item["source"] == "official_blog"
    assert item["title"] == "Getting started with ChatGPT"
    assert item["url"] == "https://openai.com/academy/getting-started"
    assert item["content"] == "Learn how to use ChatGPT."
    assert item["author"] == "OpenAI"
    assert item["published_at"] == "2026-07-10T00:00:00+00:00"
    assert item["image_url"] is None


def test_parse_feed_skips_entries_without_title():
    items = parse_feed(OPENAI_STYLE_RSS, company="OpenAI")
    urls = [it["url"] for it in items]
    assert "https://openai.com/no-title" not in urls


def test_parse_feed_extracts_media_thumbnail_image():
    items = parse_feed(DEEPMIND_STYLE_RSS, company="Google DeepMind")

    assert len(items) == 1
    item = items[0]
    assert item["author"] == "Google DeepMind"
    assert item["image_url"] == "https://example.com/thumb.jpg"
    assert item["title"] == "Introducing computer use in Gemini"


def test_parse_feed_handles_empty_feed():
    assert parse_feed("<rss><channel></channel></rss>", company="OpenAI") == []


# OpenAI'ın gerçek akışı, 2015'e kadar giden binlerce eski yazıyı da içeriyor
# (bkz. MAX_AGE_DAYS aciklamasi) -- bunu taklit eden, eski + yeni + tarihsiz
# kayit iceren bir ornek.
MIXED_AGE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<item>
<title>2015'ten cok eski bir yazi</title>
<link>https://openai.com/eski-yazi</link>
<pubDate>Fri, 11 Dec 2015 08:00:00 GMT</pubDate>
</item>
<item>
<title>Bugune yakin, guncel bir yazi</title>
<link>https://openai.com/guncel-yazi</link>
<pubDate>Mon, 13 Jul 2026 12:00:00 GMT</pubDate>
</item>
<item>
<title>Tarihi hic belirtilmemis yazi</title>
<link>https://openai.com/tarihsiz-yazi</link>
</item>
</channel>
</rss>
"""


def test_parse_feed_filters_out_entries_older_than_max_age_days():
    items = parse_feed(MIXED_AGE_RSS, company="OpenAI", max_age_days=60)
    urls = {it["url"] for it in items}

    assert "https://openai.com/eski-yazi" not in urls
    assert "https://openai.com/guncel-yazi" in urls


def test_parse_feed_keeps_entries_with_no_published_date_regardless_of_cutoff():
    items = parse_feed(MIXED_AGE_RSS, company="OpenAI", max_age_days=60)
    urls = {it["url"] for it in items}
    assert "https://openai.com/tarihsiz-yazi" in urls


def test_parse_feed_keeps_everything_when_max_age_days_is_none():
    items = parse_feed(MIXED_AGE_RSS, company="OpenAI", max_age_days=None)
    assert len(items) == 3
