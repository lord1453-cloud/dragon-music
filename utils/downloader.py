# ============================================
# 🐲 Ejderha Müzik Botu - Asenkron İndirme Motoru
# ============================================
# yt-dlp tabanlı video (MP4) ve ses (MP3) indirme motoru.
#
# Öne çıkan özellikler:
# - Eşzamanlılık kontrolü: asyncio.Semaphore(2) ile aynı anda max 2 indirme.
# - Video kalitesi: 720p veya 480p MP4.
# - Ses kalitesi: 192 kbps veya 128 kbps MP3.
# - Telegram 50 MB dosya boyutu denetimi (Aşarsa anında iptal).
# - Otomatik geçici klasör (data/temp) yönetimi ve bellek (RAM) temizliği (gc.collect).

import os
import gc
import glob
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, Tuple
from contextlib import contextmanager

import yt_dlp

from bot.config import (
    TEMP_DIR,
    MAX_FILE_SIZE,
    MAX_PARALLEL_DOWNLOADS,
    YOUTUBE_COOKIE_FILE,
    YOUTUBE_COOKIES_FROM_BROWSER,
)
from utils.cache import search_cache
from utils.cookie_manager import (
    GUEST_COOKIES_FILE,
    validate_cookie_file,
    get_browser_cookie_config,
    get_cookie_file_path,
)

logger = logging.getLogger(__name__)

# İndirmeler için ayrılmış ThreadPool ve Semafor
_download_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="media_downloader")
_download_semaphore = asyncio.Semaphore(MAX_PARALLEL_DOWNLOADS)

MIN_VALID_SIZE = 10_000  # 10 KB


def _format_duration(seconds: Optional[int]) -> str:
    """Saniye cinsinden süreyi formatlar."""
    if not seconds:
        return "Bilinmiyor"
    try:
        s = int(seconds)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"
    except Exception:
        return "Bilinmiyor"


def _sanitize_filename(name: str) -> str:
    """Dosya adı için geçersiz karakterleri temizler."""
    clean = "".join(c for c in name if c.isalnum() or c in " -_").strip()
    return clean[:60] if clean else f"media_{int(time.time())}"


def _is_bot_challenge(err_msg: Any) -> bool:
    """yt-dlp veya YouTube hata mesajının bot kontrolü olup olmadığını tespit eder (TR ve EN)."""
    err_str = str(err_msg).lower()
    return (
        "bot olmadığınızı" in err_str or
        "oturum açın" in err_str or
        "topluluğumuzu korumamıza yardımcı olur" in err_str or
        "daha fazla bilgi" in err_str or
        "sign in to confirm you're not a bot" in err_str or
        "confirm you're not a bot" in err_str or
        "confirm you’re not a bot" in err_str or
        "bot confirmation" in err_str or
        "use --cookies" in err_str or
        "this video is not available" in err_str or
        "kullanılamıyor" in err_str or
        "kullanilamiyor" in err_str or
        "requested format is not available" in err_str
    )


def _get_auth_strategies() -> list:
    """
    YouTube işlemleri için öncelik sırasına göre indirme/arama stratejilerini üretir:
    1. Geçerli kullanıcı çerez dosyası (cookies.txt)
    2. Otomatik üretilen taze misafir çerezleri (guest_cookies.txt)
    3. Tarayıcı çerezleri (cookiesfrombrowser)
    4. EJS Challenge Solver destekli temiz çerezsiz istek (En kararlı)
    """
    strategies = []

    # 1. Öncelik: Kullanıcı Çerez Dosyası (Geçerli ise)
    cookie_path = get_cookie_file_path(warn_if_missing=False)
    if cookie_path and os.path.exists(cookie_path):
        is_valid, _ = validate_cookie_file(cookie_path)
        if is_valid:
            strategies.append({
                "type": "cookiefile",
                "cookiefile": cookie_path,
                "label": f"User Cookie ({os.path.basename(cookie_path)})",
            })

    # 2. Öncelik: Misafir Çerezleri (GUEST_COOKIES_FILE)
    if os.path.exists(GUEST_COOKIES_FILE) and os.path.getsize(GUEST_COOKIES_FILE) > 10:
        strategies.append({
            "type": "cookiefile",
            "cookiefile": GUEST_COOKIES_FILE,
            "label": "Guest Cookie",
        })

    # 3. Öncelik: Tarayıcı Çerezleri
    browser = get_browser_cookie_config()
    if browser:
        strategies.append({
            "type": "browser",
            "browser": browser,
            "cookiesfrombrowser": (browser,),
            "label": f"Browser Cookies ({browser})",
        })

    # 4. Öncelik: Çerezsiz + EJS Challenge Solver (En kararlı yöntem)
    strategies.append({
        "type": "none",
        "label": "Clean EJS (Çerezsiz)",
    })

    return strategies


def _build_ytdl_opts(strategy: Optional[dict] = None, extra_opts: Optional[dict] = None) -> dict:
    """
    yt-dlp için EJS challenge solver destekli ve hatasız temel seçenekleri oluşturur.
    """
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "socket_timeout": 25,
        "retries": 3,
        "fragment_retries": 3,
        "skip_unavailable_fragments": True,
        "no_color": True,
        "remote_components": ["ejs:github"],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }

    if strategy:
        if strategy.get("type") == "cookiefile" and strategy.get("cookiefile"):
            opts["cookiefile"] = strategy["cookiefile"]
        elif strategy.get("type") == "browser" and strategy.get("cookiesfrombrowser"):
            opts["cookiesfrombrowser"] = strategy["cookiesfrombrowser"]

    if extra_opts:
        opts.update(extra_opts)

    return opts


# ── Medya Arama (Cache Destekli) ──────────────────────────────

async def search_media(query: str, is_video: bool = False) -> Optional[Dict[str, Any]]:
    """
    YouTube üzerinde arama yapar veya doğrudan linki çözümler.
    Arama sonuçlarını utils/cache.py üzerinden 1 saat önbellekler.
    Çoklu kimlik doğrulama stratejisi ve EJS challenge solver destekler.
    """
    cache_key = f"ytdl_search:{'v' if is_video else 'a'}:{query.strip().lower()}"
    cached_info = await search_cache.get(cache_key)
    if cached_info:
        logger.debug(f"⚡ Arama önbellekten getirildi: {query}")
        return cached_info

    def _sync_search():
        strategies = _get_auth_strategies()
        last_error = None
        for strat in strategies:
            strat_label = strat.get("label", "Auth")
            opts = _build_ytdl_opts(strategy=strat, extra_opts={
                "extract_flat": "in_playlist",
                "skip_download": True,
            })
            url = query if query.startswith(("http://", "https://")) else f"ytsearch1:{query}"
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        continue
                    if "entries" in info:
                        entries = [e for e in info["entries"] if e]
                        if not entries:
                            continue
                        info = entries[0]

                    return {
                        "id": info.get("id"),
                        "title": info.get("title", "Bilinmeyen Medya"),
                        "url": info.get("webpage_url") or f"https://www.youtube.com/watch?v={info.get('id')}",
                        "duration": info.get("duration", 0),
                        "duration_str": _format_duration(info.get("duration", 0)),
                        "uploader": info.get("uploader") or info.get("channel", "YouTube"),
                        "thumbnail": info.get("thumbnail"),
                        "filesize_approx": info.get("filesize_approx") or info.get("filesize"),
                    }
            except Exception as e:
                last_error = e
                if _is_bot_challenge(e):
                    logger.warning(f"⚠️ search_media bot doğrulaması ({strat_label}), sonraki stratejiye geçiliyor...")
                else:
                    logger.debug(f"search_media deneme hatası ({strat_label}): {e}")
                continue

        if last_error:
            logger.error(f"search_media hatası ({query}): {last_error}")
        return None

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(_download_executor, _sync_search)
        if result:
            await search_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"search_media genel hatası ({query}): {e}")
        return None


# ── Video İndirme (/video için) ───────────────────────────────

async def download_video(query_or_url: str, quality: str = "720p") -> Dict[str, Any]:
    """
    YouTube videosunu MP4 formatında 720p veya 480p olarak indirir.
    50 MB dosya sınırını kontrol eder.
    """
    async with _download_semaphore:
        # Önce meta veriyi çöz
        info = await search_media(query_or_url, is_video=True)
        if not info:
            return {"success": False, "error": "not_found", "message": "Video bulunamadı!"}

        url = info["url"]
        title = info["title"]
        safe_name = _sanitize_filename(title)
        timestamp = int(time.time())
        output_template = os.path.join(TEMP_DIR, f"vid_{timestamp}_{safe_name}.%(ext)s")
        target_mp4 = os.path.join(TEMP_DIR, f"vid_{timestamp}_{safe_name}.mp4")

        # Format seçimi
        max_height = "720" if "720" in quality else "480"
        video_format = (
            f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"best[height<={max_height}][ext=mp4]/"
            f"best[height<={max_height}]/"
            f"best"
        )

        def _sync_download_video():
            strategies = _get_auth_strategies()
            last_err_msg = ""
            for strat in strategies:
                strat_label = strat.get("label", "Auth")
                opts = _build_ytdl_opts(strategy=strat, extra_opts={
                    "format": video_format,
                    "outtmpl": output_template,
                    "merge_output_format": "mp4",
                    "max_filesize": MAX_FILE_SIZE,
                })
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        logger.info(f"📥 Video indiriliyor ({quality}, {strat_label}): {title}")
                        ydl.download([url])

                    # İndirilen dosyayı tespit et
                    downloaded_file = None
                    if os.path.exists(target_mp4):
                        downloaded_file = target_mp4
                    else:
                        candidates = glob.glob(os.path.join(TEMP_DIR, f"vid_{timestamp}_{safe_name}.*"))
                        if candidates:
                            downloaded_file = candidates[0]

                    if not downloaded_file or not os.path.exists(downloaded_file):
                        continue

                    file_size = os.path.getsize(downloaded_file)
                    if file_size < MIN_VALID_SIZE:
                        cleanup_file(downloaded_file)
                        continue

                    size_mb = round(file_size / (1024 * 1024), 2)
                    # 50 MB sınır kontrolü
                    if file_size > MAX_FILE_SIZE:
                        cleanup_file(downloaded_file)
                        return {
                            "success": False,
                            "error": "oversized",
                            "size_mb": size_mb,
                            "limit_mb": 50,
                            "message": f"Dosya çok büyük ({size_mb} MB > 50 MB). Telegram bot sınırı nedeniyle gönderilemiyor."
                        }

                    return {
                        "success": True,
                        "file_path": downloaded_file,
                        "title": title,
                        "duration": info.get("duration", 0),
                        "duration_str": info.get("duration_str", "Bilinmiyor"),
                        "file_size": file_size,
                        "size_mb": size_mb,
                        "quality": quality,
                        "thumbnail": info.get("thumbnail"),
                    }

                except yt_dlp.utils.MaxDownloadsReached:
                    return {"success": False, "error": "oversized", "message": "Video boyutu 50 MB sınırını aşıyor."}
                except Exception as e:
                    err_str = str(e)
                    if "File is larger than max-filesize" in err_str or "larger than" in err_str:
                        return {
                            "success": False,
                            "error": "oversized",
                            "message": "Video boyutu 50 MB sınırını aşıyor! Telegram botları 50 MB üzeri dosya gönderemez."
                        }
                    last_err_msg = str(e)
                    if _is_bot_challenge(e):
                        logger.warning(f"⚠️ Video indirmede bot doğrulaması tespit edildi ({strat_label}), sonraki strateji deneniyor...")
                    else:
                        logger.warning(f"Video indirme deneme hatası ({strat_label}): {e}")
                    continue

            logger.error(f"Video indirme hatası ({title}): {last_err_msg}")
            return {"success": False, "error": "exception", "message": f"İndirme hatası: {last_err_msg}"}

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_download_executor, _sync_download_video)


# ── Ses İndirme (/indir için) ─────────────────────────────────

async def download_audio(query_or_url: str, bitrate: int = 192) -> Dict[str, Any]:
    """
    Şarkıyı MP3 formatında indirir (192 kbps veya 128 kbps).
    50 MB sınırını kontrol eder.
    Çok stratejili EJS fallback mekanizması içerir.
    """
    async with _download_semaphore:
        info = await search_media(query_or_url, is_video=False)
        if not info:
            return {"success": False, "error": "not_found", "message": "Şarkı bulunamadı!"}

        url = info["url"]
        title = info["title"]
        safe_name = _sanitize_filename(title)
        timestamp = int(time.time())
        output_template = os.path.join(TEMP_DIR, f"aud_{timestamp}_{safe_name}.%(ext)s")
        target_mp3 = os.path.join(TEMP_DIR, f"aud_{timestamp}_{safe_name}.mp3")

        def _sync_download_audio():
            strategies = _get_auth_strategies()
            last_err_msg = ""
            for strat in strategies:
                strat_label = strat.get("label", "Auth")
                opts = _build_ytdl_opts(strategy=strat, extra_opts={
                    "format": "bestaudio/best",
                    "outtmpl": output_template,
                    "max_filesize": MAX_FILE_SIZE,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": str(bitrate),
                        }
                    ],
                })
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        logger.info(f"📥 MP3 ses indiriliyor ({bitrate}kbps, {strat_label}): {title}")
                        ydl.download([url])

                    if not os.path.exists(target_mp3):
                        candidates = glob.glob(os.path.join(TEMP_DIR, f"aud_{timestamp}_{safe_name}.*"))
                        if candidates:
                            final_path = candidates[0]
                        else:
                            continue
                    else:
                        final_path = target_mp3

                    file_size = os.path.getsize(final_path)
                    if file_size < MIN_VALID_SIZE:
                        cleanup_file(final_path)
                        continue

                    size_mb = round(file_size / (1024 * 1024), 2)
                    if file_size > MAX_FILE_SIZE:
                        cleanup_file(final_path)
                        return {
                            "success": False,
                            "error": "oversized",
                            "size_mb": size_mb,
                            "limit_mb": 50,
                            "message": f"Ses dosyası çok büyük ({size_mb} MB > 50 MB)."
                        }

                    return {
                        "success": True,
                        "file_path": final_path,
                        "title": title,
                        "performer": info.get("uploader", "YouTube"),
                        "duration": info.get("duration", 0),
                        "duration_str": info.get("duration_str", "Bilinmiyor"),
                        "file_size": file_size,
                        "size_mb": size_mb,
                        "bitrate": bitrate,
                        "thumbnail": info.get("thumbnail"),
                    }

                except Exception as e:
                    err_str = str(e)
                    if "larger than" in err_str:
                        return {"success": False, "error": "oversized", "message": "Ses dosyası 50 MB sınırını aşıyor."}
                    last_err_msg = str(e)
                    if _is_bot_challenge(e):
                        logger.warning(f"⚠️ Ses indirmede bot doğrulaması tespit edildi ({strat_label}), sonraki strateji deneniyor...")
                    else:
                        logger.warning(f"Ses indirme deneme hatası ({strat_label}): {e}")
                    continue

            logger.error(f"Ses indirme hatası ({title}): {last_err_msg}")
            return {"success": False, "error": "exception", "message": f"İndirme hatası: {last_err_msg}"}

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_download_executor, _sync_download_audio)


# ── Dosya ve Bellek Temizleme Yardımcıları ────────────────────

def cleanup_file(file_path: Optional[str]) -> None:
    """Geçici dosyayı güvenle siler ve RAM'i boşaltmak için gc.collect() tetikler."""
    if not file_path:
        return
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"🧹 Geçici dosya temizlendi: {os.path.basename(file_path)}")
    except Exception as e:
        logger.warning(f"Dosya temizleme uyarısı ({file_path}): {e}")
    finally:
        # Bellek sızıntısını ve RAM şişmesini önle
        gc.collect()


@contextmanager
def temp_file_context(file_path: Optional[str]):
    """With bloğu bitiminde dosyayı otomatik silen ve belleği toparlayan context manager."""
    try:
        yield file_path
    finally:
        cleanup_file(file_path)


def cleanup_all_temp_files() -> int:
    """TEMP_DIR içindeki tüm eski geçici dosyaları temizler."""
    count = 0
    try:
        for f in glob.glob(os.path.join(TEMP_DIR, "*")):
            try:
                if os.path.isfile(f):
                    os.remove(f)
                    count += 1
            except Exception:
                pass
        if count > 0:
            logger.info(f"🧹 {count} adet geçici indirme dosyası temizlendi.")
    except Exception as e:
        logger.warning(f"Geçici klasör temizleme hatası: {e}")
    finally:
        gc.collect()
    return count
