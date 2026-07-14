from ai_radar.collectors.anthropic_news import parse_news

# Gercek anthropic.com/news sayfasinin sadelestirilmis bir ornegi:
# - ayni yazi hem "one cikanlar" (h2/h4 basliklar) hem "kronolojik liste"
#   (baslik icin duz span) sablonunda tekrar ediyor -> tekillestirme test edilmeli
# - navigasyon linki gibi <time> etiketi olmayan /news/ linkleri atlanmali
ANTHROPIC_STYLE_HTML = """
<html><body>
<nav><a href="/news/">Tum Haberler</a></nav>

<a class="FeaturedGrid-hash-content" href="/news/hard-questions">
  <h2 class="FeaturedGrid-hash-featuredTitle">Inviting hard questions</h2>
  <div class="FeaturedGrid-hash-featuredItemContent">
    <div class="FeaturedGrid-hash-meta">
      <span class="caption bold">Announcements</span>
      <time class="FeaturedGrid-hash-date caption bold">Jul 9, 2026</time>
    </div>
    <p class="FeaturedGrid-hash-body">We are asking the public for their hardest questions.</p>
  </div>
</a>

<a class="FeaturedGrid-hash-sideLink" href="/news/redeploying-fable-5">
  <div class="FeaturedGrid-hash-meta">
    <span class="caption bold">Announcements</span>
    <time class="FeaturedGrid-hash-date caption bold">Jun 30, 2026</time>
  </div>
  <h4 class="FeaturedGrid-hash-title">Redeploying Fable 5</h4>
  <p class="FeaturedGrid-hash-body">Fable 5 returns globally July 1.</p>
</a>

<a class="PublicationList-hash-listItem" href="/news/hard-questions">
  <div class="PublicationList-hash-meta">
    <time class="PublicationList-hash-date body-3">Jul 9, 2026</time>
    <span class="PublicationList-hash-subject body-3">Announcements</span>
  </div>
  <span class="PublicationList-hash-title body-3">Inviting hard questions</span>
</a>

<a class="PublicationList-hash-listItem" href="/news/reflect-with-claude">
  <div class="PublicationList-hash-meta">
    <time class="PublicationList-hash-date body-3">Jul 9, 2026</time>
    <span class="PublicationList-hash-subject body-3">Announcements</span>
  </div>
  <span class="PublicationList-hash-title body-3">Introducing a way to reflect on how you use Claude</span>
</a>
</body></html>
"""


def test_parse_news_extracts_featured_grid_entry_fields():
    items = parse_news(ANTHROPIC_STYLE_HTML)
    item = next(it for it in items if it["url"] == "https://www.anthropic.com/news/hard-questions")

    assert item["source"] == "official_blog"
    assert item["title"] == "Inviting hard questions"
    assert item["author"] == "Anthropic"
    assert item["content"] == "We are asking the public for their hardest questions."
    assert item["published_at"] == "2026-07-09T00:00:00+00:00"
    assert item["image_url"] is None


def test_parse_news_extracts_title_from_h4_heading():
    items = parse_news(ANTHROPIC_STYLE_HTML)
    item = next(it for it in items if it["url"] == "https://www.anthropic.com/news/redeploying-fable-5")
    assert item["title"] == "Redeploying Fable 5"


def test_parse_news_extracts_title_from_publication_list_span_when_no_heading():
    items = parse_news(ANTHROPIC_STYLE_HTML)
    item = next(it for it in items if it["url"] == "https://www.anthropic.com/news/reflect-with-claude")
    assert item["title"] == "Introducing a way to reflect on how you use Claude"
    # Bu sablonda ozet (p etiketi) yok
    assert item["content"] is None


def test_parse_news_deduplicates_entries_appearing_in_both_templates():
    items = parse_news(ANTHROPIC_STYLE_HTML)
    urls = [it["url"] for it in items]
    assert urls.count("https://www.anthropic.com/news/hard-questions") == 1


def test_parse_news_skips_links_without_time_tag():
    items = parse_news(ANTHROPIC_STYLE_HTML)
    urls = [it["url"] for it in items]
    assert "https://www.anthropic.com/news/" not in urls


def test_parse_news_handles_page_with_no_articles():
    assert parse_news("<html><body><nav><a href='/news/'>Tum Haberler</a></nav></body></html>") == []
