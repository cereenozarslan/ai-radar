"""X (Twitter) API v2 üzerinden AI/teknoloji ile ilgili son gönderileri toplar.

tweepy, X'in resmi kütüphanesi değil ama v2 API için topluluğun standart
kabul ettiği istemci; kimlik doğrulama ve sayfalama detaylarını bizim
yerimize hallediyor (PRAW'ın Reddit için yaptığı gibi).

DİKKAT: X'in API'si "pay-per-use" (kullandıkça öde) modelinde çalışıyor.
Bu modüldeki collect()/search_recent() fonksiyonlarını çağırmak GERÇEK
bir API isteği gönderir ve hesap bakiyenizden kredi düşer.
"""

import tweepy

from ai_radar.config import config

# Varsayılan arama sorgusu: AI ile ilgili, retweet olmayan, İngilizce gönderiler.
# İhtiyaca göre collect() çağrılırken farklı bir query verilebilir.
DEFAULT_QUERY = '(AI OR LLM OR "artificial intelligence") -is:retweet lang:en'


def _get_client() -> tweepy.Client:
    """Sadece okuma/arama için yeterli olan app-only (bearer token) istemcisi oluşturur."""
    return tweepy.Client(bearer_token=config.X_BEARER_TOKEN)


def search_recent(query: str = DEFAULT_QUERY, max_results: int = 10) -> tweepy.Response:
    """Son 7 gündeki gönderilerde arama yapar (X'in 'recent search' uç noktası)."""
    client = _get_client()
    return client.search_recent_tweets(
        query=query,
        max_results=max_results,
        tweet_fields=["created_at", "author_id"],
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


def collect(query: str = DEFAULT_QUERY, max_results: int = 10) -> list[dict]:
    """Sorguya uyan gönderileri toplayıp items şemasına uygun listeye çevirir.

    Gerçek bir X API isteği gönderir (kredi harcar).
    """
    response = search_recent(query, max_results)
    if not response.data:
        return []

    users_by_id = {user.id: user for user in (response.includes.get("users") or [])}
    return [to_item_dict(tweet, users_by_id) for tweet in response.data]


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    collected = collect()
    added = save_items(collected)
    print(f"X (Twitter): {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
