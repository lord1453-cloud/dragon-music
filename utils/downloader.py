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
    get_auth_strategies,
    build_ytdl_options,
    is_bot_challenge_error,
    parse_media_query_args,
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
    return is_bot_challenge_error(err_msg)


def _get_auth_strategies(custom_cookie_path: Optional[str] = None, custom_browser: Optional[str] = None) -> list:
    """
    YouTube işlemleri için öncelik sırasına göre çok aşamalı fallback zinciri üretir.
    """
    return get_auth_strategies(custom_cookie_path=custom_cookie_path, custom_browser=custom_browser)


def _build_ytdl_opts(strategy: Optional[dict] = None, extra_opts: Optional[dict] = None) -> dict:
    """
    yt-dlp için EJS challenge solver ve User-Agent rotasyonu destekli seçenekleri oluşturur.
    """
    return build_ytdl_options(strategy=strategy, extra_opts=extra_opts)


# ── Medya Arama (Cache Destekli) ──────────────────────────────

async def search_media(
    query: str,
    is_video: bool = False,
    cookie_path: Optional[str] = None,
    browser: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    YouTube üzerinde arama yapar veya doğrudan linki çözümler.
    Arama sonuçlarını utils/cache.py üzerinden 1 saat önbellekler.
    --cookies-from-browser, --cookies ve çoklu fallback stratejilerini destekler.
    """
    clean_query, parsed_browser, parsed_cookie_path = parse_media_query_args(
        query, default_browser=browser, default_cookie_path=cookie_path
    )
    if not clean_query:
        return None

    cache_key = f"ytdl_search:{'v' if is_video else 'a'}:{clean_query.strip().lower()}"
    cached_info = await search_cache.get(cache_key)
    if cached_info:
        logger.debug(f"⚡ Arama önbellekten getirildi: {clean_query}")
        return cached_info

    def _sync_search():
        strategies = get_auth_strategies(custom_cookie_path=parsed_cookie_path, custom_browser=parsed_browser)
        last_error = None
        for strat in strategies:
            strat_label = strat.get("label", "Auth")
            opts = build_ytdl_options(strategy=strat, extra_opts={
                "extract_flat": "in_playlist",
                "skip_download": True,
            })
            url = clean_query if clean_query.startswith(("http://", "https://")) else f"ytsearch1:{clean_query}"
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
                if is_bot_challenge_error(e):
                    logger.warning(f"⚠️ search_media bot doğrulaması/erişim engeli ({strat_label}), sonraki stratejiye geçiliyor...")
                else:
                    logger.debug(f"search_media deneme hatası ({strat_label}): {e}")
                continue

        # YouTube başarısız olduysa SoundCloud fallback dene
        if not is_video and not clean_query.startswith(("http://", "https://")):
            logger.info(f"🔄 YouTube araması engellendi, SoundCloud yedeği deneniyor: {clean_query}")
            try:
                sc_opts = build_ytdl_options(extra_opts={
                    "extract_flat": "in_playlist",
                    "skip_download": True,
                })
                with yt_dlp.YoutubeDL(sc_opts) as ydl:
                    sc_info = ydl.extract_info(f"scsearch1:{clean_query}", download=False)
                    if sc_info and "entries" in sc_info and sc_info["entries"]:
                        sc_entry = sc_info["entries"][0]
                        if sc_entry:
                            return {
                                "id": sc_entry.get("id"),
                                "title": sc_entry.get("title") or clean_query,
                                "url": sc_entry.get("webpage_url") or sc_entry.get("url"),
                                "duration": sc_entry.get("duration", 0),
                                "duration_str": _format_duration(sc_entry.get("duration", 0)),
                                "uploader": sc_entry.get("uploader", "SoundCloud"),
                                "thumbnail": sc_entry.get("thumbnail"),
                                "filesize_approx": None,
                            }
            except Exception as sc_e:
                logger.debug(f"SoundCloud fallback arama hatası: {sc_e}")

        if last_error:
            logger.error(f"search_media hatası ({clean_query}): {last_error}")
        return None

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(_download_executor, _sync_search)
        if result:
            await search_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"search_media genel hatası ({clean_query}): {e}")
        return None


# ── Video İndirme (/video için) ───────────────────────────────

async def download_video(
    query_or_url: str,
    quality: str = "720p",
    cookie_path: Optional[str] = None,
    browser: Optional[str] = None,
) -> Dict[str, Any]:
    """
    YouTube videosunu MP4 formatında 720p veya 480p olarak indirir.
    50 MB dosya sınırını kontrol eder.
    --cookies-from-browser ve harici cookies.txt parametrelerini destekler.
    """
    clean_query, parsed_browser, parsed_cookie_path = parse_media_query_args(
        query_or_url, default_browser=browser, default_cookie_path=cookie_path
    )
    if not clean_query:
        return {"success": False, "error": "not_found", "message": "Geçersiz arama terimi veya URL!"}

    async with _download_semaphore:
        # Önce meta veriyi çöz
        info = await search_media(
            clean_query, is_video=True, cookie_path=parsed_cookie_path, browser=parsed_browser
        )
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
            strategies = get_auth_strategies(custom_cookie_path=parsed_cookie_path, custom_browser=parsed_browser)
            last_err_msg = ""
            for strat in strategies:
                strat_label = strat.get("label", "Auth")
                opts = build_ytdl_options(strategy=strat, extra_opts={
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
                    if is_bot_challenge_error(e):
                        logger.warning(f"⚠️ Video indirmede bot doğrulaması/erişim engeli ({strat_label}), sonraki strateji deneniyor...")
                    else:
                        logger.warning(f"Video indirme deneme hatası ({strat_label}): {e}")
                    continue

            logger.error(f"Video indirme hatası ({title}): {last_err_msg}")
            return {"success": False, "error": "exception", "message": f"İndirme hatası: {last_err_msg}"}

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_download_executor, _sync_download_video)


# ── Ses İndirme (/indir için) ─────────────────────────────────

async def download_audio(
    query_or_url: str,
    bitrate: int = 192,
    cookie_path: Optional[str] = None,
    browser: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Şarkıyı MP3 formatında indirir (192 kbps veya 128 kbps).
    50 MB sınırını kontrol eder.
    --cookies-from-browser ve harici cookies.txt parametrelerini destekler.
    Çok stratejili EJS fallback mekanizması içerir.
    """
    clean_query, parsed_browser, parsed_cookie_path = parse_media_query_args(
        query_or_url, default_browser=browser, default_cookie_path=cookie_path
    )
    if not clean_query:
        return {"success": False, "error": "not_found", "message": "Geçersiz arama terimi veya URL!"}

    async with _download_semaphore:
        info = await search_media(
            clean_query, is_video=False, cookie_path=parsed_cookie_path, browser=parsed_browser
        )
        if not info:
            return {"success": False, "error": "not_found", "message": "Şarkı bulunamadı!"}

        url = info["url"]
        title = info["title"]
        safe_name = _sanitize_filename(title)
        timestamp = int(time.time())
        output_template = os.path.join(TEMP_DIR, f"aud_{timestamp}_{safe_name}.%(ext)s")
        target_mp3 = os.path.join(TEMP_DIR, f"aud_{timestamp}_{safe_name}.mp3")

        def _sync_download_audio():
            strategies = get_auth_strategies(custom_cookie_path=parsed_cookie_path, custom_browser=parsed_browser)
            last_err_msg = ""
            for strat in strategies:
                strat_label = strat.get("label", "Auth")
                opts = build_ytdl_options(strategy=strat, extra_opts={
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
                    if is_bot_challenge_error(e):
                        logger.warning(f"⚠️ Ses indirmede bot doğrulaması/erişim engeli ({strat_label}), sonraki strateji deneniyor...")
                    else:
                        logger.warning(f"Ses indirme deneme hatası ({strat_label}): {e}")
                    continue

            # YouTube tamamen engellenirse SoundCloud üzerinden MP3 indirmeyi dene
            logger.info(f"🔄 YouTube üzerinden indirme engellendi, SoundCloud failover deneniyor: {title}")
            try:
                sc_opts = build_ytdl_options(extra_opts={
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
                with yt_dlp.YoutubeDL(sc_opts) as ydl:
                    ydl.download([f"scsearch1:{title}"])

                if not os.path.exists(target_mp3):
                    candidates = glob.glob(os.path.join(TEMP_DIR, f"aud_{timestamp}_{safe_name}.*"))
                    if candidates:
                        final_path = candidates[0]
                    else:
                        final_path = None
                else:
                    final_path = target_mp3

                if final_path and os.path.exists(final_path) and os.path.getsize(final_path) > MIN_VALID_SIZE:
                    file_size = os.path.getsize(final_path)
                    size_mb = round(file_size / (1024 * 1024), 2)
                    logger.info(f"✅ SoundCloud failover ile MP3 başarıyla indirildi: {final_path}")
                    return {
                        "success": True,
                        "file_path": final_path,
                        "title": title,
                        "performer": "SoundCloud",
                        "duration": info.get("duration", 0),
                        "duration_str": info.get("duration_str", "Bilinmiyor"),
                        "file_size": file_size,
                        "size_mb": size_mb,
                        "bitrate": bitrate,
                        "thumbnail": info.get("thumbnail"),
                    }
            except Exception as sc_err:
                logger.error(f"SoundCloud MP3 indirme de başarısız: {sc_err}")

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
