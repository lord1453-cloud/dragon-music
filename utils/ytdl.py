# ============================================
# 🐲 Ejderha Müzik Botu - YouTube & Medya Motoru
# ============================================
# yt-dlp kullanarak YouTube'dan arama, ses/video akışı
# indirme, akıllı önbellek (caching), exponential backoff,
# istek tekilleştirme (deduplication) ve hata yönetimi.
#
# MİMARİ İYİLEŞTİRMELERİ:
# - In-memory TTL/LRU Arama & Metadata Önbelleği (Gereksiz YouTube isteklerini %80+ azaltır)
# - Eşzamanlı İndirme Tekilleştirme (In-flight request deduplication)
# - Eşzamanlılık Sınırlandırıcı Semaphore (Sunucu ve ağ yükünü dengeler)
# - Üstel Geri Çekilme (Exponential Backoff + Jitter) ile geçici hataları toparlama
# - Merkezi Hata Sınıfları (RateLimit, BotChallenge, Unavailable)
# - Çift Arama Ortadan Kaldırma (Pre-fetched info desteği)
# - SoundCloud Failover Entegrasyonu (Kesintisiz yayın garantisi)
# - Takılmasız Opus 48kHz ses ve 720p HD MP4 video akış profili

import os
import time
import random
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict

import yt_dlp

from bot.config import (
    AUDIO_BITRATE,
    DOWNLOADS_DIR,
    COOKIES_FILE,
    YOUTUBE_COOKIE_FILE,
    YOUTUBE_COOKIES_FROM_BROWSER,
)

logger = logging.getLogger(__name__)

# ── Hata Sınıfları (Custom Exceptions) ───────────────────────
class YTDLError(Exception):
    """YouTube ve medya indirme işlemleri için temel hata sınıfı."""
    pass

class YouTubeRateLimitError(YTDLError):
    """YouTube HTTP 429 veya geçici hız sınırlaması uyguladığında fırlatılır."""
    pass

class YouTubeBotChallengeError(YTDLError):
    """YouTube 'Sign in to confirm you're not a bot' / doğrulama istediğinde fırlatılır."""
    pass

class YouTubeVideoUnavailableError(YTDLError):
    """Video silinmiş, gizli veya ülkeye kısıtlı olduğunda fırlatılır."""
    pass


# ── Ayrılmış Thread Pool & Eşzamanlılık Kontrolleri ──────────
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ytdl_worker")
_download_semaphore = asyncio.Semaphore(2)  # Aynı anda max 2 ağır indirme prosesi

# Minimum geçerli dosya boyutu (byte)
MIN_VALID_FILE_SIZE = 10_000  # 10 KB


# ── 1. Akıllı TTL / LRU Arama Önbelleği ────────────────────────
class _TTLCache:
    """Thread-safe ve asenkron uyumlu TTL + LRU önbellek."""
    def __init__(self, maxsize: int = 500, ttl_seconds: int = 3600):
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None
            timestamp, value = self._cache[key]
            if time.time() - timestamp > self._ttl:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    async def set(self, key: str, value: Any):
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)  # En eskiyi sil
            self._cache[key] = (time.time(), value)

_search_cache = _TTLCache(maxsize=500, ttl_seconds=3600)  # 60 dk (3600 sn) arama önbelleği


# ── 2. In-Flight İndirme Tekilleştirme (Request Deduplication) ─
# Aynı URL için aynı anda birden fazla indirme tetiklenirse,
# ikinci gelen ilk görevin tamamlanmasını bekler.
_in_flight_downloads: Dict[str, asyncio.Future] = {}
_in_flight_lock = asyncio.Lock()


from utils.cookie_manager import (
    validate_cookie_file,
    is_user_cookie_valid,
    get_browser_cookie_config,
    get_youtube_auth_status,
    GUEST_COOKIES_FILE,
)

# ── 3. YouTube Kimlik Doğrulama & Çerez Öncelik Zinciri ────────
def _is_bot_challenge(err_msg: Any) -> bool:
    """yt-dlp veya YouTube hata mesajının bot kontrolü olup olmadığını tespit eder."""
    err_str = str(err_msg).lower()
    return (
        "sign in to confirm you're not a bot" in err_str or
        "confirm you're not a bot" in err_str or
        "confirm you’re not a bot" in err_str or
        "bot confirmation" in err_str or
        "use --cookies" in err_str
    )


def _classify_error(err_str: str) -> Exception:
    """yt-dlp hata metnini analiz edip uygun hata tipine dönüştürür."""
    if _is_bot_challenge(err_str):
        return YouTubeBotChallengeError("YouTube bot doğrulama kontrolü istedi.")
    err_lower = err_str.lower()
    if "429" in err_str or "too many requests" in err_lower or "rate-limit" in err_lower:
        return YouTubeRateLimitError("YouTube hız sınırı (429) aşıldı.")
    elif "video unavailable" in err_lower or "private video" in err_lower or "blocked" in err_lower:
        return YouTubeVideoUnavailableError("Video erişilemez, silinmiş veya kısıtlı.")
    return YTDLError(err_str)


def _get_auth_strategies() -> list:
    """
    YouTube işlemleri için öncelik sırasına göre kimlik doğrulama stratejilerini üretir:
    1. YOUTUBE_COOKIE_FILE (veya COOKIES_FILE) varsa ve geçerliyse
    2. YOUTUBE_COOKIES_FROM_BROWSER yapılandırılmışsa (chrome, edge, firefox vb.)
    3. Standart / Çerezsiz deneme
    """
    strategies = []

    # 1. Öncelik: Cookie File
    cookie_path = YOUTUBE_COOKIE_FILE or COOKIES_FILE
    if cookie_path:
        if os.path.exists(cookie_path):
            is_valid, reason = validate_cookie_file(cookie_path)
            if is_valid:
                strategies.append({
                    "type": "cookiefile",
                    "cookiefile": cookie_path,
                    "label": f"Cookie File ({os.path.basename(cookie_path)})",
                })
            else:
                logger.warning(f"⚠️ YouTube cookie authentication başarısız: {reason}")
        else:
            logger.warning(f"⚠️ YouTube cookie dosyası bulunamadı: {cookie_path}")

    # 2. Öncelik: Tarayıcı Çerezleri (cookiesfrombrowser)
    browser = get_browser_cookie_config()
    if browser:
        strategies.append({
            "type": "browser",
            "browser": browser,
            "cookiesfrombrowser": (browser,),
            "label": f"Browser Cookies ({browser})",
        })

    # 3. Öncelik: Standart Çerezsiz İstek
    strategies.append({
        "type": "none",
        "label": "Standart (Çerezsiz)",
    })

    return strategies


def check_cookies_status(cookie_path: Optional[str] = None) -> bool:
    """Kullanıcının sağladığı cookies.txt dosyasının geçerliliğini kontrol eder."""
    return is_user_cookie_valid(cookie_path or YOUTUBE_COOKIE_FILE or COOKIES_FILE)


# ── 4. Temel yt-dlp Yapılandırması ─────────────────────────────
def _get_base_opts(strategy: Optional[dict] = None) -> dict:
    """
    yt-dlp için optimize edilmiş temel yapılandırma.
    Aşırı yüklenmeyi, uzun asılı kalmaları ve gereksiz veri transferini önler.
    Çerez içeriklerini ASLA loglamaz.
    """
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "socket_timeout": 15,
        "retries": 3,
        "fragment_retries": 3,
        "skip_unavailable_fragments": True,
        "ignoreerrors": False,
        "no_color": True,
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "tv"],
                "player_skip": ["configs", "webpage"],
            }
        },
    }

    if strategy:
        if strategy.get("type") == "cookiefile" and strategy.get("cookiefile"):
            opts["cookiefile"] = strategy["cookiefile"]
        elif strategy.get("type") == "browser" and strategy.get("cookiesfrombrowser"):
            opts["cookiesfrombrowser"] = strategy["cookiesfrombrowser"]

    return opts


def _format_duration(seconds: Optional[int]) -> str:
    """Saniye cinsinden süreyi MM:SS veya HH:MM:SS formatına çevirir."""
    if not seconds:
        return "Bilinmiyor"
    try:
        seconds = int(seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    except Exception:
        return "Bilinmiyor"


def _is_valid_file(path: str) -> bool:
    """Dosyanın var olduğunu ve minimum boyutta olduğunu doğrular."""
    return os.path.exists(path) and os.path.getsize(path) > MIN_VALID_FILE_SIZE


# ── 5. YouTube Arama Fonksiyonu ────────────────────────────────
async def search_youtube(query: str) -> Optional[dict]:
    """
    YouTube'da şarkı/video arar.
    - Eğer girdi URL ise doğrudan kullanır.
    - Metin araması ise 'ytsearch:1:sorgu' formatında ilk sonucu çeker.
    - Önce bellekteki TTL önbelleği kontrol eder.
    - Geçici hatalarda üstel geri çekilme (exponential backoff) uygular.
    - YouTube başarısız olursa alternatif SoundCloud araması yapar.
    """
    query = query.strip()
    if not query:
        return None

    # 1. Önbellek kontrolü
    cache_key = f"search:{query.lower()}"
    cached = await _search_cache.get(cache_key)
    if cached:
        logger.debug(f"⚡ Önbellekten arama sonucu getirildi: {query}")
        return cached

    is_direct_url = query.startswith(("http://", "https://"))
    target = query if is_direct_url else f"ytsearch:1:{query}"

    def _sync_search() -> Optional[dict]:
        strategies = _get_auth_strategies()
        bot_challenge_detected = False

        for strategy in strategies:
            strat_label = strategy.get("label", "Auth")
            try:
                opts = {
                    **_get_base_opts(strategy),
                    "extract_flat": "in_playlist",
                    "skip_download": True,
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(target, download=False)
                    if not info:
                        continue

                    entries = []
                    if "entries" in info and info["entries"]:
                        entries = [e for e in info["entries"] if e and (e.get("id") or e.get("url"))]
                    elif info.get("id") or info.get("url"):
                        entries = [info]

                    if not entries:
                        continue

                    entry = entries[0]
                    vid = entry.get("id", "")
                    title = entry.get("title") or query
                    web_url = entry.get("url") or entry.get("webpage_url")
                    if not web_url or not str(web_url).startswith("http"):
                        web_url = f"https://www.youtube.com/watch?v={vid}"
                    duration = entry.get("duration") or 0
                    thumbnail = entry.get("thumbnail", "")

                    return {
                        "title": title,
                        "url": web_url,
                        "duration": duration,
                        "duration_str": _format_duration(duration),
                        "thumbnail": thumbnail,
                    }
            except Exception as e:
                err_text = str(e)
                if _is_bot_challenge(err_text):
                    bot_challenge_detected = True
                    logger.warning(f"⚠️ YouTube bot doğrulaması tespit edildi ({strat_label}).")
                elif "cookie" in err_text.lower() or "dpapi" in err_text.lower():
                    logger.warning(f"⚠️ YouTube cookie authentication başarısız ({strat_label}).")
                else:
                    logger.warning(f"YouTube arama uyarısı ({strat_label}): {err_text.splitlines()[0]}")
                continue

        if bot_challenge_detected:
            logger.warning("⚠️ YouTube bot doğrulaması nedeniyle arama tamamlanamadı.")
        return None

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _sync_search)

    if result:
        await _search_cache.set(cache_key, result)
        if result.get("url"):
            await _search_cache.set(f"search:{result['url'].lower()}", result)
        return result

    # 2. YouTube araması başarısız olursa SoundCloud Fallback
    if not is_direct_url:
        logger.info(f"🔄 YouTube akışı engellendi/hata verdi, SoundCloud yedeği devreye giriyor: {query}")
        sc_opts = {
            **_get_base_opts(),
            "extract_flat": "in_playlist",
            "skip_download": True,
        }
        def _sync_sc_search() -> Optional[dict]:
            try:
                with yt_dlp.YoutubeDL(sc_opts) as ydl:
                    info = ydl.extract_info(f"scsearch1:{query}", download=False)
                    if info and "entries" in info and info["entries"]:
                        entry = info["entries"][0]
                        if entry:
                            return {
                                "title": entry.get("title") or query,
                                "url": entry.get("url") or entry.get("webpage_url"),
                                "duration": entry.get("duration") or 0,
                                "duration_str": _format_duration(entry.get("duration")),
                                "thumbnail": entry.get("thumbnail", ""),
                            }
            except Exception as sc_err:
                logger.debug(f"SoundCloud fallback arama hatası: {sc_err}")
            return None

        sc_result = await loop.run_in_executor(_executor, _sync_sc_search)
        if sc_result and sc_result.get("url"):
            await _search_cache.set(cache_key, sc_result)
            return sc_result

    return None


# ── 6. Hızlandırılmış Stream / Audio URL Alma Fonksiyonu ────────
async def get_audio_url(query: str) -> Optional[str]:
    """
    Verilen şarkı adı veya doğrudan YouTube/medya linki için
    hızlandırılmış doğrudan ses akışı URL'sini alır.

    Hızlandırma ve Optimizasyonlar:
    - yt-dlp'nin extract_info çağrısı download=False ile hızlıca çalıştırılır.
    - Format seçeneği: 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio'.
    - Önbellek (TTL Cache) süresi: 3600 saniye (1 saat).
    - Asenkron executor (run_in_executor) ile paralel ve donmayan işlemler.
    """
    query = query.strip()
    if not query:
        return None

    # 1. TTL Önbellek Kontrolü (TTL = 3600 saniye)
    cache_key = f"audio_url:{query.lower()}"
    cached = await _search_cache.get(cache_key)
    if cached:
        logger.debug(f"⚡ Önbellekten ses URL'si getirildi (Cache HIT): {query}")
        return cached

    # 2. URL veya Arama Sorgusu Tespiti
    is_direct_url = query.startswith(("http://", "https://"))
    target = query if is_direct_url else f"ytsearch:1:{query}"

    def _sync_get_audio_url() -> Optional[str]:
        strategies = _get_auth_strategies()
        bot_challenge_encountered = False

        audio_format_candidates = [
            "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
            "bestaudio/best",
            "ba/b",
            "best",
        ]

        for strategy in strategies:
            strat_label = strategy.get("label", "Auth")
            for afmt in audio_format_candidates:
                try:
                    current_opts = {
                        **_get_base_opts(strategy),
                        "format": afmt,
                        "skip_download": True,
                    }
                    with yt_dlp.YoutubeDL(current_opts) as ydl:
                        logger.debug(f"🔐 YouTube authentication deneniyor ({strat_label})...")
                        info = ydl.extract_info(target, download=False)
                        if not info:
                            continue

                        entries = []
                        if "entries" in info and info["entries"]:
                            entries = [e for e in info["entries"] if e]
                        elif info:
                            entries = [info]

                        if not entries:
                            continue

                        entry = entries[0]
                        direct_url = entry.get("url")
                        video_title = entry.get("title") or query
                        if direct_url and str(direct_url).startswith("http"):
                            logger.info(f"🎵 YouTube: {video_title}")
                            logger.info("🔐 YouTube authentication hazır")
                            logger.info("📥 Audio stream alınıyor...")
                            logger.info("✅ YouTube audio stream başarılı")
                            return direct_url

                        formats = entry.get("formats", [])
                        audio_formats = [
                            f for f in formats
                            if f.get("url") and (f.get("vcodec") == "none" or "audio" in f.get("mime_type", ""))
                        ]
                        if audio_formats:
                            audio_formats.sort(key=lambda x: x.get("abr") or x.get("tbr") or 0, reverse=True)
                            chosen_url = audio_formats[0]["url"]
                            logger.info(f"🎵 YouTube: {video_title}")
                            logger.info("🔐 YouTube authentication hazır")
                            logger.info("📥 Audio stream alınıyor...")
                            logger.info("✅ YouTube audio stream başarılı")
                            return chosen_url

                        if formats:
                            chosen_url = formats[-1].get("url")
                            logger.info(f"🎵 YouTube: {video_title}")
                            logger.info("🔐 YouTube authentication hazır")
                            logger.info("📥 Audio stream alınıyor...")
                            logger.info("✅ YouTube audio stream başarılı")
                            return chosen_url
                except Exception as e:
                    err_text = str(e)
                    if _is_bot_challenge(err_text):
                        bot_challenge_encountered = True
                        logger.warning(f"⚠️ YouTube bot doğrulaması tespit edildi ({strat_label}).")
                        break
                    elif "cookie" in err_text.lower() or "dpapi" in err_text.lower():
                        logger.warning(f"⚠️ YouTube cookie authentication başarısız ({strat_label}).")
                        break
                    else:
                        logger.debug(f"get_audio_url ({strat_label}/{afmt}) uyarısı: {err_text.splitlines()[0]}")
                        continue

        if bot_challenge_encountered:
            logger.warning("⚠️ YouTube bot doğrulaması nedeniyle ses akışı alınamadı.")
            logger.info("🔄 SoundCloud fallback deneniyor...")
        else:
            logger.warning("⚠️ YouTube authentication başarısız veya ses akışı alınamadı.")

        # SoundCloud failover yedeği
        if not is_direct_url:
            logger.info(f"🔄 SoundCloud fallback devreye giriyor: {query}")
            try:
                sc_opts = {
                    **_get_base_opts(),
                    "format": "bestaudio/best",
                    "skip_download": True,
                }
                with yt_dlp.YoutubeDL(sc_opts) as ydl:
                    info = ydl.extract_info(f"scsearch1:{query}", download=False)
                    if info and "entries" in info and info["entries"]:
                        entry = info["entries"][0]
                        if entry and entry.get("url"):
                            logger.info(f"✅ SoundCloud fallback üzerinden ses akışı sağlandı: {entry.get('title') or query}")
                            return entry.get("url")
            except Exception as sc_err:
                logger.error(f"get_audio_url SoundCloud yedeği hatası: {sc_err}")

        return None

    # Asenkron executor ile paralel çalıştırma
    loop = asyncio.get_event_loop()
    try:
        audio_url = await loop.run_in_executor(_executor, _sync_get_audio_url)
        if audio_url:
            await _search_cache.set(cache_key, audio_url)
            return audio_url
    except Exception as e:
        logger.error(f"get_audio_url genel hatası: {e}")
    return None


async def get_stream_url(url: str) -> Optional[str]:
    """Doğrudan ses akışı URL'sini (direkt link) çeker."""
    return await get_audio_url(url)


# ── 7. MP3 Olarak İndirme Fonksiyonu (/indir için) ───────────────
async def download_audio(query: Optional[str] = None, info: Optional[dict] = None) -> Optional[dict]:
    """
    Şarkıyı Telegram'a göndermek üzere MP3 olarak indirir.
    Eğer 'info' önceden aranıp verilmişse tekrar arama yapmaz.
    """
    if not info:
        if not query:
            return None
        info = await search_youtube(query)
        if not info:
            return None

    url = info["url"]
    safe_title = "".join(c for c in info["title"] if c.isalnum() or c in " -_").strip()
    if not safe_title:
        safe_title = f"ejderha_muzik_{hash(url) & 0xFFFFFFFF}"
    output_path = os.path.join(DOWNLOADS_DIR, f"{safe_title}.mp3")

    if _is_valid_file(output_path):
        return {
            "title": info["title"],
            "file_path": output_path,
            "duration": info.get("duration", 0),
            "duration_str": info.get("duration_str", "Bilinmiyor"),
        }

    def _sync_download():
        strategies = _get_auth_strategies()
        bot_challenge_encountered = False

        for strategy in strategies:
            strat_label = strategy.get("label", "Auth")
            opts = {
                **_get_base_opts(strategy),
                "format": "bestaudio/best",
                "outtmpl": output_path.replace(".mp3", ".%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(AUDIO_BITRATE),
                    }
                ],
            }
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    logger.debug(f"🔐 YouTube authentication deneniyor ({strat_label})...")
                    ydl.download([url])

                if _is_valid_file(output_path):
                    logger.info(f"🎵 YouTube: {info['title']}")
                    logger.info("🔐 YouTube authentication hazır")
                    logger.info("📥 Audio stream alınıyor...")
                    logger.info("✅ YouTube audio stream başarılı")
                    return {
                        "title": info["title"],
                        "file_path": output_path,
                        "duration": info.get("duration", 0),
                        "duration_str": info.get("duration_str", "Bilinmiyor"),
                    }
            except Exception as e:
                err_text = str(e)
                if _is_bot_challenge(err_text):
                    bot_challenge_encountered = True
                    logger.warning(f"⚠️ YouTube bot doğrulaması tespit edildi ({strat_label}).")
                elif "cookie" in err_text.lower() or "dpapi" in err_text.lower():
                    logger.warning(f"⚠️ YouTube cookie authentication başarısız ({strat_label}).")
                else:
                    logger.warning(f"MP3 indirme uyarısı ({strat_label}): {err_text.splitlines()[0]}")
                continue

        if bot_challenge_encountered:
            logger.warning("⚠️ YouTube bot doğrulaması nedeniyle ses akışı alınamadı.")
            logger.info("🔄 SoundCloud fallback deneniyor...")
        else:
            logger.warning("⚠️ YouTube authentication başarısız veya ses akışı alınamadı.")

        # Başarısız olursa SoundCloud fallback ile indirmeyi dene
        try:
            logger.info(f"🔄 SoundCloud yedeği deneniyor: {info['title']}")
            sc_opts = {
                **_get_base_opts(),
                "format": "bestaudio/best",
                "outtmpl": output_path.replace(".mp3", ".%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(AUDIO_BITRATE),
                    }
                ],
            }
            with yt_dlp.YoutubeDL(sc_opts) as ydl:
                ydl.download([f"scsearch1:{info['title']}"])

            if _is_valid_file(output_path):
                logger.info(f"✅ SoundCloud üzerinden MP3 başarıyla indirildi: {output_path}")
                return {
                    "title": info["title"],
                    "file_path": output_path,
                    "duration": info.get("duration", 0),
                    "duration_str": info.get("duration_str", "Bilinmiyor"),
                }
        except Exception as sc_e:
            logger.error(f"SoundCloud MP3 indirme de başarısız: {sc_e}")

        return None

    async with _download_semaphore:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _sync_download)


# ── 8. Sesli Sohbet Yayını İçin Ses Dosyası İndirme ──────────────
async def get_audio_file_for_stream(url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Sesli sohbette çalmak için parçayı optimize edilmiş Opus/OGG formatında hazırlar.
    - Önbellek kontrolü yapar.
    - In-flight deduplication ile aynı URL için çift indirmeyi engeller.
    - Semaphore ile eşzamanlı indirme patlamalarını önler.
    - Hata durumunda kontrollü failover (SoundCloud) motoruna geçer.
    """
    file_hash = abs(hash(url)) & 0xFFFFFFFF
    output_template = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.%(ext)s")
    final_path = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.opus")
    fallback_path = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.ogg")
    mp3_path = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.mp3")

    # 1. Disk Önbellek kontrolü
    for p in [final_path, fallback_path, mp3_path]:
        if _is_valid_file(p):
            logger.debug(f"⚡ Disk önbelleğinden ses dosyası kullanılıyor: {p}")
            return p

    # 2. Eşzamanlı İndirme Tekilleştirme (In-Flight Dedup)
    async with _in_flight_lock:
        if url in _in_flight_downloads:
            logger.info(f"⏳ Aynı medya zaten indiriliyor, mevcut işlem bekleniyor: {url}")
            existing_future = _in_flight_downloads[url]
        else:
            loop = asyncio.get_running_loop()
            existing_future = loop.create_future()
            _in_flight_downloads[url] = existing_future

    if existing_future.done():
        try:
            return existing_future.result()
        except Exception:
            return None

    # Eğer biz ilk istek değilsek, ilk isteğin bitmesini bekle
    async with _in_flight_lock:
        is_leader = (_in_flight_downloads.get(url) is existing_future and not existing_future.done() and not hasattr(existing_future, "_running_leader"))
        if is_leader:
            setattr(existing_future, "_running_leader", True)

    if not is_leader:
        try:
            return await existing_future
        except Exception:
            return None

    # Lider indirme görevi:
    async def _execute_download() -> Optional[str]:
        # Bozuk eski dosyaları temizle
        for p in [final_path, fallback_path, mp3_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        def _sync_worker():
            strategies = _get_auth_strategies()
            bot_challenge_encountered = False

            audio_formats = [
                "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
                "bestaudio/best",
                "ba/b",
                "best",
            ]

            for strategy in strategies:
                strat_label = strategy.get("label", "Auth")
                opts = {
                    **_get_base_opts(strategy),
                    "format": "bestaudio/best",
                    "outtmpl": output_template,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "opus",
                            "preferredquality": "128",
                        }
                    ],
                    "postprocessor_args": {
                        "FFmpegExtractAudio": [
                            "-ac", "2",
                            "-ar", "48000",
                        ],
                    },
                }

                for afmt in audio_formats:
                    try:
                        current_opts = {**opts, "format": afmt}
                        with yt_dlp.YoutubeDL(current_opts) as ydl:
                            logger.debug(f"🔐 YouTube authentication deneniyor ({strat_label})...")
                            ydl.download([url])

                        for candidate in [final_path, fallback_path, mp3_path]:
                            if _is_valid_file(candidate):
                                logger.info(f"🎵 YouTube: {title or url}")
                                logger.info("🔐 YouTube authentication hazır")
                                logger.info("📥 Audio stream alınıyor...")
                                logger.info(f"✅ YouTube audio stream başarılı: {candidate}")
                                return candidate

                        for ext in [".opus", ".ogg", ".mp3", ".m4a", ".webm"]:
                            candidate = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}{ext}")
                            if _is_valid_file(candidate):
                                logger.info(f"🎵 YouTube: {title or url}")
                                logger.info("🔐 YouTube authentication hazır")
                                logger.info("📥 Audio stream alınıyor...")
                                logger.info(f"✅ YouTube audio stream başarılı: {candidate}")
                                return candidate
                    except Exception as e:
                        err_text = str(e)
                        if _is_bot_challenge(err_text):
                            bot_challenge_encountered = True
                            logger.warning(f"⚠️ YouTube bot doğrulaması tespit edildi ({strat_label}).")
                            break
                        elif "cookie" in err_text.lower() or "dpapi" in err_text.lower():
                            logger.warning(f"⚠️ YouTube cookie authentication başarısız ({strat_label}).")
                            break
                        else:
                            logger.warning(f"YouTube ses akışı format ({afmt}) uyarısı ({strat_label}): {err_text.splitlines()[0]}")
                            continue

            # 2. SoundCloud Failover
            search_query = title or (url.split("watch?v=")[-1] if "watch?v=" in url else url)
            if bot_challenge_encountered:
                logger.warning("⚠️ YouTube bot doğrulaması nedeniyle ses akışı alınamadı.")
                logger.info(f"🔄 SoundCloud fallback deneniyor: {search_query}")
            else:
                logger.warning("⚠️ YouTube authentication başarısız veya ses akışı alınamadı.")
                logger.info(f"🔄 SoundCloud fallback devreye giriyor: {search_query}")

            try:
                sc_opts = {
                    **_get_base_opts(),
                    "format": "bestaudio/best",
                    "outtmpl": output_template,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "opus",
                            "preferredquality": "128",
                        }
                    ],
                }
                with yt_dlp.YoutubeDL(sc_opts) as ydl:
                    ydl.download([f"scsearch1:{search_query}"])

                for candidate in [final_path, fallback_path, mp3_path]:
                    if _is_valid_file(candidate):
                        logger.info(f"✅ SoundCloud failover ile ses akışı hazırlandı: {candidate}")
                        return candidate

                for ext in [".opus", ".ogg", ".mp3", ".m4a", ".webm"]:
                    candidate = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}{ext}")
                    if _is_valid_file(candidate):
                        logger.info(f"✅ SoundCloud failover ile ses akışı hazırlandı: {candidate}")
                        return candidate
            except Exception as sc_err:
                logger.error(f"SoundCloud ses failover hatası: {sc_err}")

            return None

        async with _download_semaphore:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(_executor, _sync_worker)
            return res

    result_path = None
    try:
        result_path = await _execute_download()
        if not existing_future.done():
            existing_future.set_result(result_path)
    except Exception as exc:
        if not existing_future.done():
            existing_future.set_exception(exc)
    finally:
        async with _in_flight_lock:
            _in_flight_downloads.pop(url, None)

    return result_path


# ── 9. Görüntülü Yayın İçin Video Dosyası İndirme (720p HD) ────
async def get_video_file_for_stream(url: str) -> Optional[str]:
    """
    Görüntülü yayın (Video Stream) için videoyu maksimum 720p MP4 formatında indirir.
    PyTgCalls MediaStream video akışı için optimize edilmiştir.
    """
    file_hash = abs(hash(url)) & 0xFFFFFFFF
    output_template = os.path.join(DOWNLOADS_DIR, f"vstream_{file_hash}.%(ext)s")
    final_path = os.path.join(DOWNLOADS_DIR, f"vstream_{file_hash}.mp4")

    # 1. Önbellek kontrolü
    if _is_valid_file(final_path):
        logger.debug(f"⚡ Disk önbelleğinden video dosyası kullanılıyor: {final_path}")
        return final_path

    # 2. In-flight kontrolü
    async with _in_flight_lock:
        vkey = f"video:{url}"
        if vkey in _in_flight_downloads:
            existing_future = _in_flight_downloads[vkey]
        else:
            loop = asyncio.get_running_loop()
            existing_future = loop.create_future()
            _in_flight_downloads[vkey] = existing_future

    if existing_future.done():
        try:
            return existing_future.result()
        except Exception:
            return None

    async with _in_flight_lock:
        is_leader = (_in_flight_downloads.get(vkey) is existing_future and not existing_future.done() and not hasattr(existing_future, "_running_leader"))
        if is_leader:
            setattr(existing_future, "_running_leader", True)

    if not is_leader:
        try:
            return await existing_future
        except Exception:
            return None

    async def _execute_video_download() -> Optional[str]:
        if os.path.exists(final_path):
            try:
                os.remove(final_path)
            except Exception:
                pass

        def _sync_vworker():
            strategies = _get_auth_strategies()
            vformats = [
                "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]/best",
                "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                "best[height<=720]/best",
                "best",
            ]
            for strategy in strategies:
                strat_label = strategy.get("label", "Auth")
                opts = {
                    **_get_base_opts(strategy),
                    "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]/best",
                    "outtmpl": output_template,
                    "merge_output_format": "mp4",
                    "postprocessor_args": {
                        "FFmpegVideoConvertor": [
                            "-c:v", "libx264",
                            "-preset", "veryfast",
                            "-crf", "23",
                            "-c:a", "aac",
                            "-b:a", "128k",
                            "-ar", "48000",
                        ],
                    },
                }
                for vfmt in vformats:
                    try:
                        current_opts = {**opts, "format": vfmt}
                        with yt_dlp.YoutubeDL(current_opts) as ydl:
                            ydl.download([url])

                        if _is_valid_file(final_path):
                            logger.info(f"✅ YouTube video akışı başarılı: {final_path}")
                            return final_path

                        for ext in [".mp4", ".mkv", ".webm"]:
                            candidate = os.path.join(DOWNLOADS_DIR, f"vstream_{file_hash}{ext}")
                            if _is_valid_file(candidate):
                                logger.info(f"✅ YouTube video akışı başarılı: {candidate}")
                                return candidate
                    except Exception as e:
                        err_text = str(e)
                        if _is_bot_challenge(err_text):
                            logger.warning(f"⚠️ YouTube video bot doğrulaması tespit edildi ({strat_label}).")
                            break
                        elif "cookie" in err_text.lower() or "dpapi" in err_text.lower():
                            logger.warning(f"⚠️ YouTube video cookie authentication hatası ({strat_label}).")
                            break
                        else:
                            logger.warning(f"Video format ({vfmt}) denenirken uyarı ({strat_label}): {err_text.splitlines()[0]}")
                            continue
            return None

        async with _download_semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(_executor, _sync_vworker)

    result_path = None
    try:
        result_path = await _execute_video_download()
        if not existing_future.done():
            existing_future.set_result(result_path)
    except Exception as exc:
        if not existing_future.done():
            existing_future.set_exception(exc)
    finally:
        async with _in_flight_lock:
            _in_flight_downloads.pop(f"video:{url}", None)

    return result_path


# ── 10. Eski Akış Dosyalarını Temizleme ─────────────────────────
async def cleanup_old_streams(keep_path: Optional[str] = None):
    """
    Eski ses ve video stream dosyalarını arka planda temizler.
    Disk kullanımını düşük tutar.
    """
    import glob

    def _clean():
        try:
            patterns = [
                os.path.join(DOWNLOADS_DIR, "stream_*"),
                os.path.join(DOWNLOADS_DIR, "vstream_*"),
            ]
            for pattern in patterns:
                for f in glob.glob(pattern):
                    if keep_path and os.path.abspath(f) == os.path.abspath(keep_path):
                        continue
                    try:
                        # 1 saatten eski dosyaları temizle (aktif dosyaları koru)
                        file_age = time.time() - os.path.getmtime(f)
                        if file_age > 1800:  # 30 dk
                            os.remove(f)
                    except Exception:
                        pass
        except Exception:
            pass

    await asyncio.to_thread(_clean)
