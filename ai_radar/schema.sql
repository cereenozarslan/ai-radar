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
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Dashboard'daki skor/kaynak filtrelerini hızlandırmak için indeksler
CREATE INDEX IF NOT EXISTS idx_items_signal_score ON items(signal_score);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
