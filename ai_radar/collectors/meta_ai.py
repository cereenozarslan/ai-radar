"""Meta AI'nin resmi blog sayfasını (ai.meta.com/blog) toplar.

Anthropic'te olduğu gibi RSS akışı yok, bu yüzden sayfanın HTML'i kazınıyor.
Meta'nın class isimleri de (Anthropic gibi) derleme sırasında üretilen kısa
hash'ler (ör. "_8xm6") — bunlara güvenmek yerine YAPIYA dayanıyoruz: her yazı
kartı tam olarak BİR "/blog/<slug>/" linki, bir tarih paragrafı ("Month DD,
YYYY" biçiminde) ve en az bir başlık (h4) içeriyor. Bu üçü aynı kartta bir
arada bulunduğunda güvenle eşleştiriyoruz; aksi halde (ör. sayfanın üstündeki
salt-görsel öne çıkan kartlarda tarih yok) o karşılaşmayı atlayıp aynı linkin
başka bir kopyasını arıyoruz.
"""

import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://ai.meta.com/blog/"
HEADERS = {"User-Agent": "ai-radar-bot/0.1 (+https://github.com)"}

MAX_AGE_DAYS = 60

_LINK_PATTERN = re.compile(r"^https://ai\.meta\.com/blog/[a-z0-9-]+/?$")
_DATE_PATTERN = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4}"
)


def fetch_html(url: str = BASE_URL) -> str:
    """Blog sayfasının ham HTML'ini döner."""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


def _distinct_links(node) -> set[str]:
    return {a["href"] for a in node.find_all("a", href=True) if _LINK_PATTERN.match(a["href"])}


def _find_date_and_title(link_tag, max_hops: int = 8):
    """link_tag'den yukarı doğru, TEK bir yazıya ait en dar kabı arar.

    Bir üst seviyede birden fazla farklı yazı linki varsa (yani birden fazla
    kartı kapsayan daha geniş bir kutuya çıktık demektir), aramayı durdurup
    bu karşılaşmayı başarısız sayıyoruz — aynı linkin sayfada başka bir
    kopyası varsa (Meta her yazıyı hem öne çıkanlar hem ana ızgarada gösterebiliyor),
    onun üzerinden tekrar denenir.
    """
    node = link_tag
    for _ in range(max_hops):
        node = node.parent
        if node is None or not hasattr(node, "find_all"):
            break
        if len(_distinct_links(node)) > 1:
            return None, None
        date_tag = node.find("p", string=_DATE_PATTERN)
        headings = node.find_all("h4")
        if date_tag and headings:
            # Kartta hem kategori (ör. "Research") hem başlık h4'ü oluyor;
            # başlık her zaman SONUNCU h4.
            return date_tag.get_text(strip=True), headings[-1].get_text(strip=True)
    return None, None


def _parse_date(date_text: str) -> str | None:
    try:
        dt = datetime.strptime(date_text.replace(",", ""), "%B %d %Y")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


def _find_image(soup: BeautifulSoup, href: str) -> str | None:
    # Aynı yazının linki sayfada birden çok yerde geçiyor (üstteki "öne çıkanlar"
    # resimli kartı, alttaki tarih/başlık kartı vb.) — görsel genelde sadece
    # ÜSTTEKİ resimli kartta bulunuyor, bu yüzden href'in TÜM kopyalarını tarayıp
    # img'i olan ilkini kullanıyoruz.
    for link_tag in soup.find_all("a", href=href):
        img_tag = link_tag.find("img")
        if img_tag and img_tag.get("src"):
            return img_tag["src"]
    return None


def parse_blog(html: str, max_age_days: int | None = MAX_AGE_DAYS) -> list[dict]:
    """Blog sayfasındaki yazıları items şemasına uygun listeye çevirir."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days) if max_age_days else None
    soup = BeautifulSoup(html, "html.parser")
    resolved: dict[str, tuple[str, str | None]] = {}

    for link_tag in soup.find_all("a", href=True):
        href = link_tag["href"]
        if not _LINK_PATTERN.match(href) or href in resolved:
            continue
        date_text, title = _find_date_and_title(link_tag)
        if not date_text or not title:
            continue
        published_at = _parse_date(date_text)
        if cutoff and published_at and datetime.fromisoformat(published_at) < cutoff:
            continue
        resolved[href] = (title, published_at)

    return [
        {
            "source": "official_blog",
            "title": title,
            "url": href,
            "content": None,
            "author": "Meta AI",
            "published_at": published_at,
            "image_url": _find_image(soup, href),
            "popularity": None,
        }
        for href, (title, published_at) in resolved.items()
    ]


def collect() -> list[dict]:
    """Meta AI blogundaki güncel yazıları toplar."""
    return parse_blog(fetch_html())


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected = collect()
    added = save_items(collected)
    print(f"Meta AI: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
