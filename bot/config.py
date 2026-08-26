# ============================================
# 🐲 Ejderha Müzik Botu - Yapılandırma Modülü
# ============================================
# .env dosyasından tüm ayarları yükler ve doğrular.
# Eksik kritik değişkenlerde anlamlı hata mesajı verir.

import os
import sys
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()


def _get_required(key: str) -> str:
    """Zorunlu bir ortam değişkenini alır. Yoksa hata fırlatır."""
    value = os.getenv(key)
    if not value:
        print(f"🐲 HATA: '{key}' ortam değişkeni bulunamadı!")
        print(f"🐲 Lütfen .env dosyanızı kontrol edin. (.env.example dosyasına bakın)")
        sys.exit(1)
    return value


# ── Zorunlu Değişkenler ──────────────────────────────────────
BOT_TOKEN: str = _get_required("BOT_TOKEN")
API_ID: int = int(_get_required("API_ID"))
API_HASH: str = _get_required("API_HASH")
SESSION_STRING: str = _get_required("SESSION_STRING")

# ── Opsiyonel Değişkenler ────────────────────────────────────
AUDIO_BITRATE: int = int(os.getenv("AUDIO_BITRATE", "320"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Sabit Değerler ───────────────────────────────────────────
BOT_NAME: str = "🐲 Ejderha Müzik Botu"
BOT_VERSION: str = "1.0.0"
DOWNLOADS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "downloads")

# İndirme klasörünü oluştur
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
