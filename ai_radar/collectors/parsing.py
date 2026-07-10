"""Toplayıcılar arasında paylaşılan küçük metin ayrıştırma yardımcıları."""

import re


def parse_count(text: str) -> int | None:
    """'6,776', '185', '12.3k' gibi sayı ifadelerini int'e çevirir.

    NuvemMag'in görüntülenme sayısı ve GitHub'ın yıldız sayısı gibi
    "popülerlik" alanlarını ayrıştırmak için kullanılır.
    """
    if not text:
        return None

    cleaned = text.strip().lower().replace(",", "").replace(" ", "")
    match = re.match(r"^([\d.]+)(k|m)?$", cleaned)
    if not match:
        return None

    number_part, suffix = match.groups()
    try:
        value = float(number_part)
    except ValueError:
        return None

    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000

    return int(value)
