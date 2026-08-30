# ============================================
# 🐲 Ejderha Müzik Botu - Yapılandırma Modülü
# ============================================
# .env dosyasından tüm ayarları yükler ve doğrular.
# Eksik kritik değişkenlerde anlamlı hata mesajı verir.

import os
import sys
from typing import Optional

from dotenv import load_dotenv  # type: ignore[import-untyped]
from utils.session_cleaner import clean_session_string

# .env dosyasını yükle
load_dotenv()


def _get_required(key: str) -> str:
    """Zorunlu bir ortam değişkenini alır. Yoksa hata fırlatır."""
    value = os.getenv(key)
    if not value:
        print(f"🐲 HATA: '{key}' ortam değişkeni bulunamadı!")
        print("🐲 Lütfen .env dosyanızı kontrol edin. (.env.example dosyasına bakın)")
        sys.exit(1)
    return value


# ── Zorunlu Değişkenler ──────────────────────────────────────
BOT_TOKEN: str = _get_required("BOT_TOKEN").strip().strip("'\"").strip()
API_ID: int = int(_get_required("API_ID").strip().strip("'\"").strip())
API_HASH: str = _get_required("API_HASH").strip().strip("'\"").strip()
SESSION_STRING: str = clean_session_string(_get_required("SESSION_STRING"))

# ── Opsiyonel Değişkenler ────────────────────────────────────
AUDIO_BITRATE: int = int(os.getenv("AUDIO_BITRATE", "320").strip().strip("'\""))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip().strip("'\"").upper()

# Telegram Log Grubu (Bot loglarını bu gruba gönderir)
_log_group_raw: Optional[str] = os.getenv("LOG_GROUP_ID")
LOG_GROUP_ID: Optional[int] = int(_log_group_raw.strip().strip("'\"")) if _log_group_raw and _log_group_raw.strip() else None


# YouTube Cookies Yapılandırması (Bot engeli / 403 aşmak için)
_cookies_env_path: str = os.getenv("COOKIES_FILE_PATH", "cookies.txt")
_base_dir: str = os.path.dirname(os.path.dirname(__file__))

# Eğer ortam değişkeninden doğrudan cookie metni (COOKIES_DATA) verilmişse dosyaya yaz
_cookies_data_env: Optional[str] = os.getenv("COOKIES_DATA") or os.getenv("YOUTUBE_COOKIES")
if _cookies_data_env and _cookies_data_env.strip():
    _auto_cookies_file = os.path.join(_base_dir, "cookies.txt")
    try:
        with open(_auto_cookies_file, "w", encoding="utf-8") as _f:
            _f.write(_cookies_data_env.strip())
    except Exception:
        pass

_possible_cookie_paths = [
    _cookies_env_path,
    os.path.join(_base_dir, _cookies_env_path),
    os.path.join(_base_dir, "cookies.txt"),
]
COOKIES_FILE: Optional[str] = None
for _cp in _possible_cookie_paths:
    if os.path.exists(_cp) and os.path.isfile(_cp) and os.path.getsize(_cp) > 10:
        COOKIES_FILE = os.path.abspath(_cp)
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
