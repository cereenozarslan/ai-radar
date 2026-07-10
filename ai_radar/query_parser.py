"""Doğal dil arama cümlelerini X toplayıcısının anladığı filtrelere çevirir.

Bu, gerçek bir yapay zeka/LLM YORUMLAMASI DEĞİL — sadece sık kullanılan
Türkçe zaman ("son 24 saat") ve etkileşim ("yüksek etkileşim", "popüler")
kalıplarını yakalayan basit, kural tabanlı bir ayrıştırıcı. Anthropic API
gerektirmez, ücretsizdir. Bu yüzden karmaşık/dolaylı cümlelerde yanlış
yorumlayabilir; arama sonucunda hangi filtrelerin uygulandığı kullanıcıya
her zaman geri gösterilmeli (bkz. web.py).
"""

import re

# X'in "recent search" uç noktası en fazla son 7 günü (168 saat) destekliyor
MAX_HOURS = 168

_TIME_PATTERNS = [
    (re.compile(r"son\s+(\d+)\s*saat\w*", re.IGNORECASE), lambda n: n),
    (re.compile(r"son\s+(\d+)\s*g[üu]n\w*", re.IGNORECASE), lambda n: n * 24),
    (re.compile(r"son\s+(\d+)\s*hafta\w*", re.IGNORECASE), lambda n: n * 24 * 7),
    (re.compile(r"son\s+bir\s+hafta\w*|ge[çc]en\s+hafta\w*", re.IGNORECASE), lambda n: 24 * 7),
    (re.compile(r"\bbug[üu]n\b", re.IGNORECASE), lambda n: 24),
    (re.compile(r"\bd[üu]n\b", re.IGNORECASE), lambda n: 48),
]

# "yüksek etkileşim" ve "etkileşimi yüksek" gibi her iki kelime sırasını da yakala
_ENGAGEMENT_KEYWORDS = re.compile(
    r"y[üu]ksek\s+etkile[şs]im\w*|etkile[şs]im\w*\s+y[üu]ksek|"
    r"pop[üu]ler|viral|[çc]ok\s+be[ğg]enilen|[çc]ok\s+konu[şs]ulan|trend",
    re.IGNORECASE,
)

# Ayrıştırıldıktan sonra konu metninde kalabilecek, anlamı olmayan bağlaç/dolgu kelimeler.
# "son" kasıtlı olarak burada yok: zaman kalıpları ("son N saat") kendi "son"unu zaten
# ayrı tüketiyor, kalan tek başına "son" genelde "Claude'ın son gelişmesi" gibi konunun
# kendisine ait bir sıfat oluyor.
_FILLER_WORDS = re.compile(
    r"\b(hakk[ıi]nda|ile\s+ilgili|paylaş[ıi]lm[ıi][şs]\w*|paylaşılan|"
    r"tweet(?:leri|ler)?|twetleri|getir|bul|ara(?:t)?|bana|olan|i[çc]indeki|"
    r"sadece|yaln[ıi]zca)\b",
    re.IGNORECASE,
)

DEFAULT_MIN_ENGAGEMENT_WHEN_REQUESTED = 20


def parse_natural_query(text: str) -> dict:
    """Serbest metni {'topic', 'hours', 'min_engagement'} filtrelerine çevirir.

    Örnek: "Claude'ın son gelişmesi hakkında etkileşimi yüksek son 24 saatte
    paylaşılmış tweetleri getir" ->
        {"topic": "Claude'ın son gelişmesi", "hours": 24, "min_engagement": 20}
    """
    remaining = text

    hours = None
    for pattern, to_hours in _TIME_PATTERNS:
        match = pattern.search(remaining)
        if match:
            n = int(match.group(1)) if match.groups() else 0
            hours = min(to_hours(n), MAX_HOURS)
            remaining = remaining[: match.start()] + remaining[match.end():]
            break

    min_engagement = 0
    if _ENGAGEMENT_KEYWORDS.search(remaining):
        min_engagement = DEFAULT_MIN_ENGAGEMENT_WHEN_REQUESTED
        remaining = _ENGAGEMENT_KEYWORDS.sub("", remaining)

    topic = _FILLER_WORDS.sub("", remaining)
    topic = re.sub(r"\s+", " ", topic).strip(" ,.-")

    return {
        "topic": topic or None,
        "hours": hours,
        "min_engagement": min_engagement,
    }
