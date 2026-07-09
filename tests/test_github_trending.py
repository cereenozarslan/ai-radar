from ai_radar.collectors.github_trending import parse_trending

# Gerçek github.com/trending sayfasının yapısını taklit eden minimal bir HTML örneği
SAMPLE_HTML = """
<html><body>
<article class="Box-row">
    <h2 class="h3 lh-condensed">
        <a href="/anthropics/claude-code">
            <span class="text-normal">anthropics /</span>
            claude-code
        </a>
    </h2>
    <p class="col-9 color-fg-muted my-1 pr-4">Bir yapay zeka destekli komut satırı aracı</p>
</article>
<article class="Box-row">
    <h2 class="h3 lh-condensed">
        <a href="/someone/no-description">
            <span class="text-normal">someone /</span>
            no-description
        </a>
    </h2>
</article>
</body></html>
"""


def test_parse_trending_extracts_repo_fields():
    """Trending HTML'inden repo adı, url, açıklama ve yazar doğru çıkarılmalı."""
    items = parse_trending(SAMPLE_HTML)

    assert len(items) == 2
    first = items[0]
    assert first["source"] == "github_trending"
    assert first["title"] == "anthropics/claude-code"
    assert first["url"] == "https://github.com/anthropics/claude-code"
    assert first["author"] == "anthropics"
    assert "yapay zeka" in first["content"]


def test_parse_trending_handles_missing_description():
    """Açıklaması olmayan repolar için content None olmalı, hata fırlatılmamalı."""
    items = parse_trending(SAMPLE_HTML)
    second = items[1]
    assert second["title"] == "someone/no-description"
    assert second["content"] is None
