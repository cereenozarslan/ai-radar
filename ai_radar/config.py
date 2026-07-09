"""Ortam değişkenlerini (.env) okuyup uygulama genelinde kullanılabilir hale getirir."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Proje kök dizini: ai_radar/ paketinin bir üstü
BASE_DIR = Path(__file__).resolve().parent.parent

# .env dosyasını proje kökünden yükle (varsa)
load_dotenv(BASE_DIR / ".env")


class Config:
    """Uygulama ayarlarını tek yerden erişilebilir kılan basit bir sınıf."""

    DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/ai_radar.db")


config = Config()
