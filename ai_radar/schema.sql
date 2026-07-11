-- AI-Radar veritabanı şeması
-- items: tüm kaynaklardan toplanan haber/içerik kayıtları

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- 'hackernews', 'github_trending', 'reddit' gibi
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,          -- UNIQUE: aynı url tekrar eklenemez (dedup)
    content TEXT,
    author TEXT,
    published_at TEXT,
    image_url TEXT,                     -- haber görseli / repo sahibi avatarı / tweet yazarının profil fotoğrafı
    signal_score INTEGER,              -- 1-10 arası önem puanı; LLM puanlamadan önce NULL
    signal_reason TEXT,                 -- LLM'in verdiği tek cümlelik gerekçe
    is_read INTEGER NOT NULL DEFAULT 0,  -- 0/1: kullanıcı bu kaydı açtı mı ("yeni" rozeti için)
    is_saved INTEGER NOT NULL DEFAULT 0, -- 0/1: kullanıcı yıldızlayıp kaydetti mi
    popularity INTEGER,                  -- kaynağın kendi popülerlik ölçüsü: NuvemMag=görüntülenme, GitHub=yıldız, X=etkileşim
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Dashboard'daki skor/kaynak filtrelerini hızlandırmak için indeksler
CREATE INDEX IF NOT EXISTS idx_items_signal_score ON items(signal_score);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);

-- "Takip ettiklerinin gündemi" için kullanıcının arayüzden yönettiği hesap listesi.
-- X'in kendi "following" listesini çekmek yerine (ayrı, ücretli bir API isteği) bu
-- yerel listeyi kullanıyoruz; hem kredi tasarrufu hem tam kontrol sağlıyor.
CREATE TABLE IF NOT EXISTS followed_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);
