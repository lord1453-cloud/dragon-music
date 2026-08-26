# ============================================
# 🐲 Ejderha Müzik Botu - YouTube Yardımcıları
# ============================================
# yt-dlp kullanarak YouTube'dan arama, ses akışı
# URL'si çekme ve MP3 indirme fonksiyonları.
#
# OPTİMİZASYON v2 - TAKILMA DÜZELTME:
# - Stream dosyaları OGG/Opus formatında indirilir (PyTgCalls native)
#   MP3 decode overhead'ı ortadan kalkar
# - yt-dlp concurrent fragment + hızlı timeout
# - Dosya bütünlüğü kontrolü (bozuk dosya tespiti)
# - Cache sistemi ile tekrar indirme önlenir
# - Ayrılmış ThreadPoolExecutor ile event loop korunur

import os
import asyncio
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

from bot.config import AUDIO_BITRATE, DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# ── Ayrılmış Thread Pool ──────────────────────────────────────
# yt-dlp indirme işlemleri için ayrı bir thread pool kullanılır.
# Bu sayede event loop'un bloklanması önlenir ve eş zamanlı
# indirme sayısı kontrol altında tutulur.
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ytdl")

# ── yt-dlp Temel Ayarları ─────────────────────────────────────
_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "geo_bypass": True,
    "source_address": "0.0.0.0",
    # Hızlı indirme için eş zamanlı fragment sayısı
    "concurrent_fragment_downloads": 4,
    # Bağlantı zaman aşımı (saniye) - uzun beklemeleri önler
    "socket_timeout": 15,
    # Yeniden deneme sayısı
    "retries": 3,
}

# Minimum geçerli dosya boyutu (byte) - bundan küçükse bozuk kabul edilir
MIN_VALID_FILE_SIZE = 10_000  # 10 KB


def _format_duration(seconds: int) -> str:
    """Saniye cinsinden süreyi MM:SS veya HH:MM:SS formatına çevirir."""
    if not seconds:
        return "Bilinmiyor"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _is_valid_file(path: str) -> bool:
    """Dosyanın var olduğunu ve minimum boyutta olduğunu kontrol eder."""
    return os.path.exists(path) and os.path.getsize(path) > MIN_VALID_FILE_SIZE


async def search_youtube(query: str) -> Optional[dict]:
    """
    YouTube'da şarkı arar ve ilk sonucun bilgilerini döndürür.

    Args:
        query: Arama sorgusu veya doğrudan YouTube linki

    Returns:
        Şarkı bilgileri dict'i: {title, url, duration, duration_str, thumbnail}
        veya None (sonuç bulunamazsa)
    """
    opts = {
        **_BASE_OPTS,
        "default_search": "ytsearch",
        "extract_flat": False,
        "format": "bestaudio/best",
        # Sadece bilgi çekiyoruz, hızlı olsun
        "skip_download": True,
    }

    def _search():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Eğer doğrudan link değilse, arama yap
                if not query.startswith(("http://", "https://")):
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)
                    if not info or "entries" not in info or not info["entries"]:
                        return None
                    info = info["entries"][0]
                else:
                    info = ydl.extract_info(query, download=False)

                if not info:
                    return None

                return {
                    "title": info.get("title", "Bilinmeyen Şarkı"),
                    "url": info.get("webpage_url", query),
                    "duration": info.get("duration", 0),
                    "duration_str": _format_duration(info.get("duration", 0)),
                    "thumbnail": info.get("thumbnail", ""),
                }
        except Exception as e:
            logger.error(f"YouTube arama hatası: {e}")
            return None

    # Ayrılmış thread pool'da çalıştır (event loop bloklanmaz)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _search)


async def get_stream_url(url: str) -> Optional[str]:
    """
    Verilen YouTube URL'si için ses akışı URL'sini çeker.

    Args:
        url: YouTube video URL'si

    Returns:
        Ses akışı doğrudan URL'si veya None
    """
    opts = {
        **_BASE_OPTS,
        "format": "bestaudio/best",
    }

    def _extract():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                # Doğrudan ses URL'sini al
                return info.get("url")
        except Exception as e:
            logger.error(f"Stream URL çekme hatası: {e}")
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _extract)


async def download_audio(query: str) -> Optional[dict]:
    """
    Şarkıyı MP3 olarak indirir (kullanıcıya gönderilecek dosya için).

    Args:
        query: Arama sorgusu veya YouTube linki

    Returns:
        İndirilen dosya bilgileri: {title, file_path, duration, duration_str}
        veya None (hata durumunda)
    """
    # Önce şarkıyı bul
    info = await search_youtube(query)
    if not info:
        return None

    # Güvenli dosya adı oluştur
    safe_title = "".join(c for c in info["title"] if c.isalnum() or c in " -_").strip()
    if not safe_title:
        safe_title = "ejderha_muzik"
    output_path = os.path.join(DOWNLOADS_DIR, f"{safe_title}.mp3")

    opts = {
        **_BASE_OPTS,
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

    def _download():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([info["url"]])
            # İndirilen dosyanın yolunu ve boyutunu kontrol et
            if _is_valid_file(output_path):
                return {
                    "title": info["title"],
                    "file_path": output_path,
                    "duration": info["duration"],
                    "duration_str": info["duration_str"],
                }
            return None
        except Exception as e:
            logger.error(f"İndirme hatası: {e}")
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _download)


async def get_audio_file_for_stream(url: str) -> Optional[str]:
    """
    Sesli sohbette çalmak için şarkıyı optimize edilmiş formatta indirir.
    PyTgCalls AudioPiped için stabil ve akıcı dosya üretir.

    TAKILMA ÇÖZÜMÜ:
    - OGG/Opus formatı kullanılır (Telegram VC'nin native codec'i)
      MP3 → PCM decode adımı atlanır, CPU yükü azalır
    - 48kHz stereo çıkış (PyTgCalls standart)
    - Dosya TAMAMEN indirilir, sonra çalma başlar
    - Cache sistemi ile aynı şarkı tekrar indirilmez
    - Bozuk dosya tespiti ve otomatik yeniden indirme

    Args:
        url: YouTube video URL'si

    Returns:
        İndirilen ses dosyasının yolu veya None
    """
    # Her indirme için benzersiz dosya adı
    file_hash = hash(url) & 0xFFFFFFFF
    output_template = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.%(ext)s")
    # OGG formatı - PyTgCalls native, decode overhead yok
    final_path = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.ogg")
    # Fallback: MP3 formatı (OGG başarısız olursa)
    fallback_path = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.mp3")

    # Cache kontrolü - zaten indirilmiş ve geçerli mi?
    if _is_valid_file(final_path):
        logger.info(f"Cache'den kullanılıyor (ogg): {final_path}")
        return final_path
    if _is_valid_file(fallback_path):
        logger.info(f"Cache'den kullanılıyor (mp3): {fallback_path}")
        return fallback_path

    # Bozuk cache dosyasını temizle
    for p in [final_path, fallback_path]:
        if os.path.exists(p):
            os.remove(p)

    opts = {
        **_BASE_OPTS,
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                # Opus: YouTube native codec (48kHz)
                # MP3/Vorbis re-encoding yapılmaz, indirme çok daha hızlı ve kayıpsız olur
                "preferredcodec": "opus",
                "preferredquality": "128",
            }
        ],
        # FFmpeg post-processor argümanları
        "postprocessor_args": {
            "FFmpegExtractAudio": [
                "-ac", "2",           # Stereo (PyTgCalls beklentisi)
                "-ar", "48000",       # 48kHz sample rate (Telegram VC standart)
            ],
        },
    }

    def _download():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            # OGG dosyasını kontrol et
            if _is_valid_file(final_path):
                logger.info(f"Stream dosyası indirildi (ogg): {final_path}")
                return final_path

            # OGG bulunamazsa MP3 dene (fallback)
            if _is_valid_file(fallback_path):
                logger.info(f"Stream dosyası indirildi (mp3 fallback): {fallback_path}")
                return fallback_path

            # Hiçbiri bulunamadıysa, downloads klasöründe uygun dosya ara
            for ext in [".ogg", ".mp3", ".m4a", ".opus", ".webm"]:
                candidate = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}{ext}")
                if _is_valid_file(candidate):
                    logger.info(f"Stream dosyası bulundu ({ext}): {candidate}")
                    return candidate

            logger.error(f"Stream dosyası bulunamadı: stream_{file_hash}.*")
            return None
        except Exception as e:
            logger.error(f"Stream dosyası indirme hatası: {e}")
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _download)


async def cleanup_old_streams(keep_path: Optional[str] = None):
    """
    Eski stream dosyalarını arka planda temizler.
    Bellek ve disk kullanımını düşük tutar.
    """
    import glob

    def _clean():
        try:
            for f in glob.glob(os.path.join(DOWNLOADS_DIR, "stream_*")):
                if keep_path and os.path.abspath(f) == os.path.abspath(keep_path):
                    continue
                try:
                    os.remove(f)
                except Exception:
                    pass
        except Exception:
            pass

    await asyncio.to_thread(_clean)


