"""X (Twitter) API v2 üzerinden belirli bir konuyla ilgili son gönderileri toplar.

tweepy, X'in resmi kütüphanesi değil ama v2 API için topluluğun standart
kabul ettiği istemci; kimlik doğrulama ve sayfalama detaylarını bizim
yerimize hallediyor (PRAW'ın Reddit için yaptığı gibi).

DİKKAT: X'in API'si "pay-per-use" (kullandıkça öde) modelinde çalışıyor.
Bu modüldeki collect()/search_recent() fonksiyonlarını çağırmak GERÇEK
bir API isteği gönderir ve hesap bakiyenizden kredi düşer.

Kullanım (belirli bir konuyu anlık aramak için):
    python -m ai_radar.collectors.x_twitter Fable 5
    python -m ai_radar.collectors.x_twitter "Meta Muse"
Argüman verilmezse DEFAULT_QUERY (genel AI/LLM taraması) kullanılır.
"""

import sys

import tweepy

from ai_radar.config import config

# Gürültü kaynakları: retweet'ler, reply zincirleri (örn. "@biri @baskabiri ...cevap"
# şeklindeki, aranan konuyla yüzeysel ilgisi olan yanıtlar) ve kripto/hisse
# "cashtag" spam'i (örn. "$AMAT opened +9.5% today").
NOISE_FILTERS = "-is:retweet -is:reply -has:cashtags lang:en"

DEFAULT_QUERY = f'(AI OR LLM OR "artificial intelligence") {NOISE_FILTERS}'


def build_query(topic: str) -> str:
    """Bir konu ifadesini (örn. 'Fable 5', 'Meta Muse') arama sorgusuna çevirir.

    Konu birden fazla kelimeden oluşuyorsa tam öbek (exact phrase) olarak aranır;
    aksi halde "Fable" ve "5" kelimelerinin ayrı ayrı geçtiği alakasız sonuçlar
    da eşleşirdi. Aynı gürültü filtreleri (retweet/reply/cashtag hariç) burada da uygulanır.
    """
    phrase = f'"{topic}"' if " " in topic else topic
    return f"{phrase} {NOISE_FILTERS}"


def clamp_max_results(max_results: int) -> int:
    """X'in recent search uç noktası max_results için 10-100 aralığı istiyor."""
    return max(10, min(max_results, 100))


def engagement_score(tweet) -> int:
    """Bir tweet'in etkileşim ağırlığını hesaplar (yüksek etkileşimli içeriği öne çıkarmak için).

    Retweet, sadece görmekten öte "paylaşmaya değer buldum" anlamına geldiği
    için beğeni/yanıt/alıntıdan 2 kat ağırlıklı sayılıyor.
    """
    metrics = tweet.public_metrics or {}
    return (
        metrics.get("like_count", 0)
        + metrics.get("retweet_count", 0) * 2
        + metrics.get("reply_count", 0)
        + metrics.get("quote_count", 0)
    )


def _get_client() -> tweepy.Client:
    """Sadece okuma/arama için yeterli olan app-only (bearer token) istemcisi oluşturur."""
    return tweepy.Client(bearer_token=config.X_BEARER_TOKEN)


def search_recent(query: str, max_results: int = 10) -> tweepy.Response:
    """Son 7 gündeki gönderilerde arama yapar (X'in 'recent search' uç noktası).

    sort_order="relevancy": X'in kendi alaka/etkileşim ağırlıklı sıralaması
    (salt kronolojik "recency" yerine), yüksek etkileşimli gönderileri öne çıkarır.
    """
    client = _get_client()
    return client.search_recent_tweets(
        query=query,
        max_results=clamp_max_results(max_results),
        sort_order="relevancy",
        tweet_fields=["created_at", "author_id", "public_metrics"],
        expansions=["author_id"],
        user_fields=["username"],
    )


def to_item_dict(tweet, users_by_id: dict) -> dict:
    """Tek bir tweet nesnesini items tablosu şemasına çevirir.

    users_by_id: {author_id: user_nesnesi} eşlemesi (search_recent'in
    'includes.users' listesinden oluşturulur), tweet.author_id'den
    kullanıcı adına ulaşmak için kullanılır.
    """
    title = tweet.text if len(tweet.text) <= 80 else tweet.text[:77] + "..."
    user = users_by_id.get(tweet.author_id)

    return {
        "source": "x_twitter",
        "title": title,
        "url": f"https://x.com/i/web/status/{tweet.id}",
        "content": tweet.text,
        "author": user.username if user else None,
        "published_at": tweet.created_at.isoformat() if tweet.created_at else None,
    }


def collect(
    topic: str | None = None,
    query: str | None = None,
    max_results: int = 10,
    min_engagement: int = 0,
) -> list[dict]:
    """Bir konuyu (ör. 'Fable 5') veya ham bir sorguyu arayıp items şemasına çevirir.

    - topic verilirse build_query() ile sorguya çevrilir (önerilen kullanım).
    - query doğrudan verilirse (ileri düzey) aynen kullanılır.
    - hiçbiri verilmezse DEFAULT_QUERY (genel AI/LLM taraması) kullanılır.
    - Sonuçlar etkileşime (beğeni/retweet/yanıt/alıntı) göre çoktan aza sıralanır.
    - min_engagement > 0 verilirse, bu eşiğin altındaki düşük etkileşimli
      gönderiler tamamen elenir (niş/yeni konularda sonuç sayısını azaltabilir,
      bu yüzden varsayılan 0'dır).

    Gerçek bir X API isteği gönderir (kredi harcar).
    """
    if query is None:
        query = build_query(topic) if topic else DEFAULT_QUERY

    response = search_recent(query, max_results)
    if not response.data:
        return []

    tweets = [t for t in response.data if engagement_score(t) >= min_engagement]
    tweets.sort(key=engagement_score, reverse=True)

    users_by_id = {user.id: user for user in (response.includes.get("users") or [])}
    return [to_item_dict(tweet, users_by_id) for tweet in tweets]


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    topic_arg = " ".join(sys.argv[1:]) or None
    collected = collect(topic=topic_arg)
    added = save_items(collected)
    label = topic_arg or "varsayılan AI/LLM sorgusu"
    print(f"X (Twitter) [{label}]: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
