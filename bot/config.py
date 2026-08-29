# ============================================
# 🐲 Ejderha Müzik Botu - Yapılandırma Modülü
# ============================================
# .env dosyasından tüm ayarları yükler ve doğrular.
# Eksik kritik değişkenlerde anlamlı hata mesajı verir.

import os
import sys
from typing import Optional
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

# YouTube Cookies Yapılandırması (Bot engeli / 403 aşmak için)
_cookies_env_path = os.getenv("COOKIES_FILE_PATH", "cookies.txt")
_base_dir = os.path.dirname(os.path.dirname(__file__))
_possible_cookie_paths = [
    _cookies_env_path,
    os.path.join(_base_dir, _cookies_env_path),
    os.path.join(_base_dir, "cookies.txt"),
]
COOKIES_FILE: Optional[str] = None
for cp in _possible_cookie_paths:
    if os.path.exists(cp) and os.path.isfile(cp):
        COOKIES_FILE = os.path.abspath(cp)
        break

# Spotify API Yapılandırması
SPOTIFY_CLIENT_ID: Optional[str] = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET: Optional[str] = os.getenv("SPOTIFY_CLIENT_SECRET")

# ── Sabit Değerler ───────────────────────────────────────────
BOT_NAME: str = "🐲 Ejderha Müzik Botu"
BOT_VERSION: str = "1.1.0"
DOWNLOADS_DIR: str = os.path.join(_base_dir, "downloads")

# İndirme klasörünü oluştur
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

