"""X (Twitter) API v2 üzerinden belirli bir konuyla ilgili son gönderileri toplar.

tweepy, X'in resmi kütüphanesi değil ama v2 API için topluluğun standart
kabul ettiği istemci; kimlik doğrulama ve sayfalama detaylarını bizim
yerimize hallediyor (PRAW'ın Reddit için yaptığı gibi).

DİKKAT: X'in API'si "pay-per-use" (kullandıkça öde) modelinde çalışıyor.
Bu modüldeki collect()/search_recent() fonksiyonlarını çağırmak GERÇEK
bir API isteği gönderir ve hesap bakiyenizden kredi düşer.

Kullanım (belirli bir konuyu anlık aramak için):
    python -m ai_radar.collectors.x_twitter Claude
    python -m ai_radar.collectors.x_twitter "Meta Muse" --hours 24 --min-engagement 50
Argüman verilmezse DEFAULT_QUERY (genel AI/LLM taraması) kullanılır.
"""

import argparse
from datetime import datetime, timedelta, timezone

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


def compute_start_time(hours: float) -> str:
    """'Son N saat' filtresi için X API'nin beklediği ISO 8601 UTC zaman damgasını üretir.

    X'in recent search uç noktası en fazla son 7 günü (168 saat) destekliyor.
    """
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ")


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


def get_user_id(username: str) -> str:
    """Kullanıcı adından X'in dahili kullanıcı id'sini çözer. Gerçek bir API isteği gönderir."""
    client = _get_client()
    resp = client.get_user(username=username.lstrip("@"))
    if not resp.data:
        raise ValueError(f"'{username}' adında bir X kullanıcısı bulunamadı.")
    return resp.data.id


def get_following_usernames(username: str, max_accounts: int = 200) -> list[str]:
    """Verilen kullanıcının takip ettiği hesapların kullanıcı adlarını döner.

    Yeni takip edilen hesaplar otomatik dahil olur (her çağrıda anlık çekilir,
    ayrıca bir listede saklanmaz). Gerçek bir X API isteği gönderir (kredi harcar).
    """
    client = _get_client()
    user_id = get_user_id(username)

    usernames: list[str] = []
    pagination_token = None
    while len(usernames) < max_accounts:
        resp = client.get_users_following(
            id=user_id,
            max_results=min(1000, max_accounts - len(usernames)),
            user_fields=["username"],
            pagination_token=pagination_token,
        )
        if not resp.data:
            break
        usernames.extend(u.username for u in resp.data)
        pagination_token = (resp.meta or {}).get("next_token")
        if not pagination_token:
            break

    return usernames


# Takip edilen kişilerin gönderileri için gürültü filtresi: NOISE_FILTERS'tan farklı
# olarak "lang:en" YOK, çünkü kullanıcı farklı dillerde hesaplar takip ediyor olabilir.
FOLLOWING_NOISE_FILTERS = "-is:retweet -is:reply"


def build_following_queries(usernames: list[str], max_query_length: int = 480) -> list[str]:
    """Takip edilen hesap listesini X'in sorgu uzunluğu sınırına (512 karakter)
    uyacak şekilde birden fazla '(from:a OR from:b OR ...)' sorgusuna böler.

    Çok sayıda hesap takip ediliyorsa tek bir istekte hepsini soramayız;
    bu yüzden birden fazla arama isteği gerekebilir (her biri kredi harcar).
    """
    if not usernames:
        return []

    def make_query(names: list[str]) -> str:
        body = " OR ".join(f"from:{n}" for n in names)
        return f"({body}) {FOLLOWING_NOISE_FILTERS}"

    queries = []
    current: list[str] = []
    for uname in usernames:
        candidate = current + [uname]
        if len(make_query(candidate)) > max_query_length and current:
            queries.append(make_query(current))
            current = [uname]
        else:
            current = candidate

    if current:
        queries.append(make_query(current))

    return queries


def search_recent(query: str, max_results: int = 10, start_time: str | None = None) -> tweepy.Response:
    """Son 7 gündeki gönderilerde arama yapar (X'in 'recent search' uç noktası).

    sort_order="relevancy": X'in kendi alaka/etkileşim ağırlıklı sıralaması
    (salt kronolojik "recency" yerine), yüksek etkileşimli gönderileri öne çıkarır.
    start_time verilirse, sadece bu zamandan sonraki gönderiler döner ("son N saat" filtresi).
    """
    client = _get_client()
    kwargs = {}
    if start_time is not None:
        kwargs["start_time"] = start_time

    return client.search_recent_tweets(
        query=query,
        max_results=clamp_max_results(max_results),
        sort_order="relevancy",
        tweet_fields=["created_at", "author_id", "public_metrics"],
        expansions=["author_id"],
        user_fields=["username", "profile_image_url"],
        **kwargs,
    )


def to_item_dict(tweet, users_by_id: dict, source: str = "x_twitter") -> dict:
    """Tek bir tweet nesnesini items tablosu şemasına çevirir.

    users_by_id: {author_id: user_nesnesi} eşlemesi (search_recent'in
    'includes.users' listesinden oluşturulur), tweet.author_id'den
    kullanıcı adına ulaşmak için kullanılır.
    source: 'x_twitter' (konu araması) veya 'x_following' (takip edilenler
    gündemi) gibi farklı X kaynaklarını ayırt etmek için.
    """
    title = tweet.text if len(tweet.text) <= 80 else tweet.text[:77] + "..."
    user = users_by_id.get(tweet.author_id)

    image_url = None
    if user and user.profile_image_url:
        # X, küçük "_normal" (48x48) boyutunda döner; daha net görünmesi için büyütüyoruz
        image_url = user.profile_image_url.replace("_normal", "_400x400")

    return {
        "source": source,
        "title": title,
        "url": f"https://x.com/i/web/status/{tweet.id}",
        "content": tweet.text,
        "author": user.username if user else None,
        "published_at": tweet.created_at.isoformat() if tweet.created_at else None,
        "image_url": image_url,
    }


def collect(
    topic: str | None = None,
    query: str | None = None,
    max_results: int = 10,
    min_engagement: int = 0,
    hours: float | None = None,
) -> list[dict]:
    """Bir konuyu (ör. 'Fable 5') veya ham bir sorguyu arayıp items şemasına çevirir.

    - topic verilirse build_query() ile sorguya çevrilir (önerilen kullanım).
    - query doğrudan verilirse (ileri düzey) aynen kullanılır.
    - hiçbiri verilmezse DEFAULT_QUERY (genel AI/LLM taraması) kullanılır.
    - Sonuçlar etkileşime (beğeni/retweet/yanıt/alıntı) göre çoktan aza sıralanır.
    - min_engagement > 0 verilirse, bu eşiğin altındaki düşük etkileşimli
      gönderiler tamamen elenir (niş/yeni konularda sonuç sayısını azaltabilir,
      bu yüzden varsayılan 0'dır).
    - hours verilirse (ör. 24), sadece son o kadar saat içinde paylaşılmış
      gönderiler döner ("son 24 saat" gibi filtreler için).

    Gerçek bir X API isteği gönderir (kredi harcar).
    """
    if query is None:
        query = build_query(topic) if topic else DEFAULT_QUERY

    start_time = compute_start_time(hours) if hours else None
    response = search_recent(query, max_results, start_time=start_time)
    if not response.data:
        return []

    tweets = [t for t in response.data if engagement_score(t) >= min_engagement]
    tweets.sort(key=engagement_score, reverse=True)

    users_by_id = {user.id: user for user in (response.includes.get("users") or [])}
    return [to_item_dict(tweet, users_by_id) for tweet in tweets]


def collect_following_digest(
    username: str,
    hours: float = 36,
    max_results_per_batch: int = 100,
    max_accounts: int = 200,
) -> list[dict]:
    """Kullanıcının takip ettiği hesapların son `hours` saatteki gönderilerini toplar.

    Takip listesi her çağrıda anlık çekilir (yeni takip edilenler otomatik dahil
    olur). Takip edilen hesap sayısına bağlı olarak BİRDEN FAZLA gerçek X API
    isteği gönderebilir (takip listesini çekmek için 1+, her sorgu grubu için 1) —
    her biri kredi harcar.
    """
    usernames = get_following_usernames(username, max_accounts=max_accounts)
    queries = build_following_queries(usernames)

    start_time = compute_start_time(hours)
    seen_ids = set()
    all_tweets = []
    users_by_id = {}

    for query in queries:
        response = search_recent(query, max_results=max_results_per_batch, start_time=start_time)
        if not response.data:
            continue
        for tweet in response.data:
            if tweet.id in seen_ids:
                continue
            seen_ids.add(tweet.id)
            all_tweets.append(tweet)
        for user in (response.includes.get("users") or []):
            users_by_id[user.id] = user

    all_tweets.sort(key=engagement_score, reverse=True)
    return [to_item_dict(tweet, users_by_id, source="x_following") for tweet in all_tweets]


if __name__ == "__main__":
    from ai_radar.collectors.common import save_items

    parser = argparse.ArgumentParser(
        description="X (Twitter) üzerinde bir konuyu arar ve sonuçları veritabanına kaydeder."
    )
    parser.add_argument("topic", nargs="*", help="Aranacak konu, örn: Claude")
    parser.add_argument(
        "--hours", type=float, default=None,
        help="Sadece son N saat içinde paylaşılmış gönderiler (örn: 24)",
    )
    parser.add_argument(
        "--min-engagement", type=int, default=0,
        help="Bu eşiğin altındaki düşük etkileşimli gönderileri ele",
    )
    parser.add_argument(
        "--max-results", type=int, default=10,
        help="En fazla kaç gönderi çekilsin (X'in kuralı: 10-100)",
    )
    args = parser.parse_args()

    topic_arg = " ".join(args.topic) or None
    collected = collect(
        topic=topic_arg,
        max_results=args.max_results,
        min_engagement=args.min_engagement,
        hours=args.hours,
    )
    added = save_items(collected)

    label = topic_arg or "varsayılan AI/LLM sorgusu"
    window = f", son {args.hours:g} saat" if args.hours else ""
    engagement_note = f", min. etkileşim {args.min_engagement}" if args.min_engagement else ""
    print(f"X (Twitter) [{label}{window}{engagement_note}]: {len(collected)} kayıt toplandı, {added} yeni kayıt eklendi.")
