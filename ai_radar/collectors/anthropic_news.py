"""Anthropic'in resmi haber sayfasını (anthropic.com/news) toplar.

Anthropic, OpenAI/DeepMind'ın aksine RSS akışı sağlamıyor (rss.xml, /news/rss.xml
gibi adresler 404 dönüyor) — bu yüzden bu koleksiyoncu, official_blogs.py'daki
RSS yaklaşımından farklı olarak, sayfanın kendi HTML'ini çekip ayrıştırıyor
(NuvemMag/GitHub Trending'de yaptığımız gibi).

RSS ile fark: RSS sitenin bize "buyur, veriyi düzenli bir formatta veriyorum"
diye kasıtlı sunduğu bir sözleşme; HTML kazıma ise sitenin GÖRÜNÜMÜNE bağımlı
oluyor. Anthropic'in class isimleri derleme sırasında üretilen hash'ler
(ör. "FeaturedGrid-module-scss-module__W1FydW__title") olduğundan onlara
güvenmiyoruz; onun yerine sayfanın HER haber linkinde ortak olan YAPIYA
(bir <a href="/news/...">, içinde bir <time> etiketi) dayanıyoruz. Bu yine de
RSS kadar sağlam değil: Anthropic sitesinin HTML iskeletini değiştirmesi
(örn. <time> etiketini kaldırması) bu koleksiyoncuyu bozabilir, RSS'i bozmaz.
"""

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.anthropic.com/news"
HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)"}

# Sayfadaki gerçek haber linkleri hep "/news/<slug>" formatında; menü, altbilgi
# gibi diğer linkleri elemek için hem bu kalıbı hem de içinde bir <time>
# etiketi olma şartını arıyoruz (aşağıdaki parse_news'e bakın).
_NEWS_LINK_PATTERN = re.compile(r"^/news/[a-z0-9-]+$")


def fetch_html(url: str = BASE_URL) -> str:
    """Haberler sayfasının ham HTML'ini döner."""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


def _find_title(link_tag) -> str | None:
    # Sayfada aynı haber iki farklı şablonla görünebiliyor: birinde başlık bir
    # h2/h3/h4 başlık etiketinde, diğerinde (kronolojik liste) class adında
    # "title" geçen sade bir span'da.
    heading = link_tag.find(["h2", "h3", "h4"])
    if heading:
        return heading.get_text(strip=True)

    for el in link_tag.find_all(["span", "div"]):
        classes = " ".join(el.get("class", []))
        if "title" in classes.lower():
            return el.get_text(strip=True)
    return None


def _parse_date(time_tag) -> str | None:
    if not time_tag:
        return None
    try:
        dt = datetime.strptime(time_tag.get_text(strip=True), "%b %d, %Y")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


def parse_news(html: str) -> list[dict]:
    """Haberler sayfasındaki yazıları items şemasına uygun listeye çevirir.

    Aynı yazı sayfada (öne çıkanlar + kronolojik liste) tekrar edebildiğinden
    href'e göre tekilleştiriyoruz, ilk karşılaşılanı tutuyoruz.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen_urls: set[str] = set()
    items = []

    for link_tag in soup.find_all("a", href=True):
        href = link_tag["href"]
        if not _NEWS_LINK_PATTERN.match(href):
            continue
        time_tag = link_tag.find("time")
        if not time_tag:
            continue
        url = "https://www.anthropic.com" + href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = _find_title(link_tag)
        if not title:
            continue

        excerpt = link_tag.find("p")

        items.append({
            "source": "official_blog",
            "title": title,
            "url": url,
            "content": excerpt.get_text(strip=True) if excerpt else None,
            "author": "Anthropic",
            "published_at": _parse_date(time_tag),
            "image_url": None,
            "popularity": None,
        })

    return items


def collect() -> list[dict]:
    """Anthropic haberler sayfasındaki güncel yazıları toplar."""
    return parse_news(fetch_html())


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected = collect()
    added = save_items(collected)
    print(f"Anthropic: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
