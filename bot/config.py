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


# YouTube Kimlik Doğrulama / Cookies Yapılandırması
_base_dir: str = os.path.dirname(os.path.dirname(__file__))

# 1. Ortam değişkeninden doğrudan Netscape çerez içeriği aktarılmışsa dosyaya yaz
_cookies_data_env: Optional[str] = os.getenv("COOKIES_DATA") or os.getenv("YOUTUBE_COOKIES")
if _cookies_data_env and _cookies_data_env.strip():
    _auto_cookies_file = os.path.join(_base_dir, "cookies.txt")
    try:
        with open(_auto_cookies_file, "w", encoding="utf-8") as _f:
            _f.write(_cookies_data_env.strip())
    except Exception:
        pass

# 2. Netscape cookie dosyası yolu tespiti
YOUTUBE_COOKIE_FILE_PATH: Optional[str] = os.getenv("YOUTUBE_COOKIE_FILE") or os.getenv("COOKIES_FILE_PATH")
_possible_cookie_paths = []
if YOUTUBE_COOKIE_FILE_PATH and YOUTUBE_COOKIE_FILE_PATH.strip():
    raw_path = YOUTUBE_COOKIE_FILE_PATH.strip().strip("'\"")
    _possible_cookie_paths.extend([raw_path, os.path.join(_base_dir, raw_path)])
# Standart default arama yolları
_possible_cookie_paths.extend([
    os.path.join(_base_dir, "cookies.txt"),
    "cookies.txt",
    "/app/cookies.txt",
])

YOUTUBE_COOKIE_FILE: Optional[str] = None
for _cp in _possible_cookie_paths:
    if os.path.exists(_cp) and os.path.isfile(_cp) and os.path.getsize(_cp) > 10:
        YOUTUBE_COOKIE_FILE = os.path.abspath(_cp)
        break

# Geriye dönük uyumluluk
COOKIES_FILE: Optional[str] = YOUTUBE_COOKIE_FILE

# 3. Tarayıcıdan otomatik çerez alma yapılandırması (chrome, edge, firefox, brave, opera, vivaldi vb.)
_raw_browser = (os.getenv("YOUTUBE_COOKIES_FROM_BROWSER") or "").strip().strip("'\"").lower()
YOUTUBE_COOKIES_FROM_BROWSER: Optional[str] = _raw_browser if _raw_browser else None

# Spotify API Yapılandırması
SPOTIFY_CLIENT_ID: Optional[str] = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET: Optional[str] = os.getenv("SPOTIFY_CLIENT_SECRET")

# Yönetici ID Listesi (ADMIN_IDS)
_admins_raw = os.getenv("ADMIN_IDS") or os.getenv("ADMINS") or os.getenv("OWNER_ID") or ""
ADMIN_IDS: list = [int(x.strip()) for x in _admins_raw.replace(";", ",").replace(" ", ",").split(",") if x.strip().lstrip("-").isdigit()]

# ── Sabit Değerler ve Dizinler ──────────────────────────────
BOT_NAME: str = "🐲 Ejderha Müzik Botu"
BOT_VERSION: str = "1.3.0"
DOWNLOADS_DIR: str = os.path.join(_base_dir, "downloads")
DATA_DIR: str = os.path.join(_base_dir, "data")
TEMP_DIR: str = os.path.join(DATA_DIR, "temp")
DATABASE_PATH: str = os.path.join(DATA_DIR, "database.db")

# ── Optimizasyon & İndirme Ayarları ─────────────────────────
MAX_QUEUE_SIZE: int = int(os.getenv("MAX_QUEUE_SIZE", "20"))
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # YouTube arama & metadata önbellek süresi (1 saat)
MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50 MB Telegram bot dosya sınırı
MAX_PARALLEL_DOWNLOADS: int = int(os.getenv("MAX_PARALLEL_DOWNLOADS", "2"))  # Aynı anda indirilebilecek max medya sayısı
DB_FLUSH_INTERVAL: int = int(os.getenv("DB_FLUSH_INTERVAL", "300"))  # SQLite tampon yazma aralığı (5 dakika)

# Klasörleri otomatik oluştur
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

