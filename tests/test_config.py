from ai_radar.config import config


def test_database_path_has_correct_default_location():
    """DATABASE_PATH, .env'de değer yoksa proje kökündeki data/ai_radar.db'ye işaret etmeli."""
    assert config.DATABASE_PATH.name == "ai_radar.db"
    assert config.DATABASE_PATH.parent.name == "data"
