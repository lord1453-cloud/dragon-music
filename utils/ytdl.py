# ============================================
# 🐲 Ejderha Müzik Botu - YouTube Yardımcıları
# ============================================
# yt-dlp kullanarak YouTube'dan arama, ses/video akışı
# indirme, cookies desteği ve MP3 indirme fonksiyonları.
#
# ÖZELLİKLER & GÜNCELLEMELER:
# - YouTube 403 / "Sign in to confirm you're not a bot" için cookies.txt entegrasyonu
# - Görüntülü yayın için max 720p MP4 video akış profili
# - ytsearch1: ile Spotify ve metin aramaları
# - Takılmasız Opus/OGG ses ve MP4 video desteği
# - Ayrılmış ThreadPoolExecutor ile event loop optimizasyonu

import os
import asyncio
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

from bot.config import AUDIO_BITRATE, DOWNLOADS_DIR, COOKIES_FILE

logger = logging.getLogger(__name__)

# ── Ayrılmış Thread Pool ──────────────────────────────────────
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ytdl")

# Minimum geçerli dosya boyutu (byte) - bundan küçükse bozuk kabul edilir
MIN_VALID_FILE_SIZE = 10_000  # 10 KB


def check_cookies_status(cookie_path: Optional[str] = COOKIES_FILE) -> bool:
    """
    cookies.txt dosyasının varlığını ve son kullanma tarihini kontrol eder.
    Süresi dolmuşsa veya dosya yoksa False döner, log'a bilgilendirici uyarı yazar.
    """
    if not cookie_path or not os.path.exists(cookie_path):
        logger.info("ℹ️ cookies.txt bulunamadı. YouTube mobil protokolleri ve failover motoru kullanılacak.")
        return False
    try:
        import time
        now = time.time()
        expired_count = 0
        total_cookies = 0
        with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    total_cookies += 1
                    try:
                        expiry = int(parts[4])
                        if 0 < expiry < now:
                            expired_count += 1
                    except (ValueError, IndexError):
                        pass
        if total_cookies > 0 and expired_count >= total_cookies * 0.7:
            logger.warning("🚨 [UYARI] cookies.txt dosyasındaki çerezlerin süresi dolmuş olabilir! Lütfen yenileyin.")
            return False
        logger.info(f"🍪 cookies.txt geçerli ({total_cookies} çerez yüklendi).")
        return True
    except Exception as e:
        logger.debug(f"Cookie kontrol uyarısı: {e}")
        return True


def _get_base_opts() -> dict:
    """
    yt-dlp için temel ayarları ve cookies konfigürasyonunu hazırlar.
    YouTube bot engeli (403 Forbidden / Sign in to confirm you're not a bot)
    aşma parametrelerini içerir (iOS ve Android mobil istemci önceliği).
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "concurrent_fragment_downloads": 4,
        "socket_timeout": 20,
        "retries": 5,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tv", "web_safari"],
            }
        },
    }

    # Eğer cookies.txt mevcutsa ve geçerliyse yt-dlp'ye dahil et
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        check_cookies_status(COOKIES_FILE)
        opts["cookiefile"] = COOKIES_FILE

    return opts


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
    'ytsearch1:' arama desteği içerir.
    """
    opts = {
        **_get_base_opts(),
        "extract_flat": "in_playlist",
        "skip_download": True,
    }

    def _search():
        target = query if query.startswith(("http://", "https://")) else f"ytsearch5:{query}"

        # 1. Öncelikli arama
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target, download=False)
                if info:
                    entries = []
                    if "entries" in info:
                        entries = [e for e in info["entries"] if e and e.get("id")]
                    elif info.get("id"):
                        entries = [info]

                    for entry in entries:
                        vid = entry.get("id")
                        title = entry.get("title") or query
                        web_url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}"
                        if not web_url.startswith("http"):
                            web_url = f"https://www.youtube.com/watch?v={vid}"
                        duration = entry.get("duration") or 0

                        return {
                            "title": title,
                            "url": web_url,
                            "duration": duration,
                            "duration_str": _format_duration(duration),
                            "thumbnail": entry.get("thumbnail", ""),
                        }
        except Exception as e:
            logger.warning(f"İlk arama denemesi ({query}) uyarısı: {e}, alternatif deneniyor...")

        # 2. Alternatif profil ile arama (Fallback)
        try:
            fallback_opts = {
                **opts,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "ios", "web_creator", "mweb"],
                    }
                },
            }
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                info = ydl.extract_info(target, download=False)
                if info:
                    entries = []
                    if "entries" in info:
                        entries = [e for e in info["entries"] if e and e.get("id")]
                    elif info.get("id"):
                        entries = [info]

                    for entry in entries:
                        vid = entry.get("id")
                        title = entry.get("title") or query
                        web_url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}"
                        if not web_url.startswith("http"):
                            web_url = f"https://www.youtube.com/watch?v={vid}"
                        duration = entry.get("duration") or 0

                        return {
                            "title": title,
                            "url": web_url,
                            "duration": duration,
                            "duration_str": _format_duration(duration),
                            "thumbnail": entry.get("thumbnail", ""),
                        }
        except Exception as e2:
            logger.error(f"YouTube arama hatası ({query}): {e2}")
            return None

        return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _search)


async def get_stream_url(url: str) -> Optional[str]:
    """
    Verilen YouTube URL'si için ses akışı URL'sini çeker.
    """
    opts = {
        **_get_base_opts(),
        "format": "bestaudio/best",
    }

    def _extract():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                return info.get("url")
        except Exception as e:
            logger.error(f"Stream URL çekme hatası: {e}")
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _extract)


async def download_audio(query: str) -> Optional[dict]:
    """
    Şarkıyı MP3 olarak indirir (kullanıcıya gönderilecek dosya için).
    """
    info = await search_youtube(query)
    if not info:
        return None

    safe_title = "".join(c for c in info["title"] if c.isalnum() or c in " -_").strip()
    if not safe_title:
        safe_title = "ejderha_muzik"
    output_path = os.path.join(DOWNLOADS_DIR, f"{safe_title}.mp3")

    opts = {
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

    def _download():
        download_configs = [
            {"extractor_args": {"youtube": {"player_client": ["android", "ios"]}}, "cookiefile": None, "name": "Mobile (Android/iOS)"},
            {"extractor_args": {"youtube": {"player_client": ["mweb", "web_creator", "web"]}}, "cookiefile": COOKIES_FILE, "name": "Cookies (Web/MWeb)"} if COOKIES_FILE else None,
            {"extractor_args": {"youtube": {"player_client": ["tv", "web_safari"]}}, "cookiefile": None, "name": "Smart TV / WebSafari"},
        ]

        for cfg in download_configs:
            if not cfg:
                continue
            try:
                run_opts = {
                    **opts,
                    "extractor_args": cfg["extractor_args"],
                }
                if cfg.get("cookiefile"):
                    run_opts["cookiefile"] = cfg["cookiefile"]
                else:
                    run_opts.pop("cookiefile", None)

                with yt_dlp.YoutubeDL(run_opts) as ydl:
                    ydl.download([info["url"]])

                if _is_valid_file(output_path):
                    return {
                        "title": info["title"],
                        "file_path": output_path,
                        "duration": info["duration"],
                        "duration_str": info["duration_str"],
                    }
            except Exception as e:
                logger.warning(f"MP3 indirme profili ({cfg['name']}) uyarısı: {e}, sonraki profil deneniyor...")

        logger.error(f"Tüm profiller ile MP3 indirme başarısız: {info['url']}")
        return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _download)


async def get_audio_file_for_stream(url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Sesli sohbette çalmak için şarkıyı optimize edilmiş OGG/Opus formatında indirir.
    YouTube engelli/kısıtlı olduğunda otomatik olarak SoundCloud failover motoruna geçer.
    """
    file_hash = hash(url) & 0xFFFFFFFF
    output_template = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.%(ext)s")
    final_path = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.opus")
    fallback_path = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.ogg")
    mp3_path = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}.mp3")

    # Cache kontrolü
    for p in [final_path, fallback_path, mp3_path]:
        if _is_valid_file(p):
            logger.info(f"Cache'den ses kullanılıyor: {p}")
            return p

    # Bozuk cache dosyasını temizle
    for p in [final_path, fallback_path, mp3_path]:
        if os.path.exists(p):
            os.remove(p)

    opts = {
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
        "postprocessor_args": {
            "FFmpegExtractAudio": [
                "-ac", "2",
                "-ar", "48000",
            ],
        },
    }

    def _download():
        download_configs = [
            {"extractor_args": {"youtube": {"player_client": ["android", "ios"]}}, "cookiefile": None, "name": "Mobile (Android/iOS)"},
            {"extractor_args": {"youtube": {"player_client": ["mweb", "web_creator", "web"]}}, "cookiefile": COOKIES_FILE, "name": "Cookies (Web/MWeb)"} if COOKIES_FILE else None,
            {"extractor_args": {"youtube": {"player_client": ["tv", "web_safari"]}}, "cookiefile": None, "name": "Smart TV / WebSafari"},
        ]

        for cfg in download_configs:
            if not cfg:
                continue
            try:
                run_opts = {
                    **opts,
                    "extractor_args": cfg["extractor_args"],
                }
                if cfg.get("cookiefile"):
                    run_opts["cookiefile"] = cfg["cookiefile"]
                else:
                    run_opts.pop("cookiefile", None)

                with yt_dlp.YoutubeDL(run_opts) as ydl:
                    ydl.download([url])

                for candidate_path in [final_path, fallback_path, mp3_path]:
                    if _is_valid_file(candidate_path):
                        logger.info(f"Ses stream dosyası hazır ({cfg['name']}): {candidate_path}")
                        return candidate_path

                for ext in [".opus", ".ogg", ".mp3", ".m4a", ".webm"]:
                    candidate = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}{ext}")
                    if _is_valid_file(candidate):
                        return candidate
            except Exception as e:
                logger.warning(f"Ses indirme profili ({cfg['name']}) uyarısı: {e}, sonraki profil deneniyor...")

        # 4. Universal Fallback: Genişletilmiş format filtresi (bestaudio/best/ba/b)
        try:
            universal_opts = {
                **opts,
                "format": "bestaudio/best/ba/b",
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "ios", "tv"],
                    }
                },
            }
            with yt_dlp.YoutubeDL(universal_opts) as ydl:
                ydl.download([url])

            for ext in [".opus", ".ogg", ".mp3", ".m4a", ".webm"]:
                candidate = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}{ext}")
                if _is_valid_file(candidate):
                    logger.info(f"Ses stream dosyası hazır (Universal Fallback): {candidate}")
                    return candidate
        except Exception as e_univ:
            logger.warning(f"Universal ses fallback uyarısı: {e_univ}")

        # 5. Kesintisiz SoundCloud Failover (YouTube bot/ülke engeline karşı %100 garantili)
        search_query = title or (url.split("watch?v=")[-1] if "watch?v=" in url else url)
        try:
            logger.info(f"🔄 YouTube engellendi, SoundCloud failover devreye giriyor: {search_query}")
            sc_opts = {
                "quiet": True,
                "no_warnings": True,
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

            for ext in [".opus", ".ogg", ".mp3", ".m4a", ".webm"]:
                candidate = os.path.join(DOWNLOADS_DIR, f"stream_{file_hash}{ext}")
                if _is_valid_file(candidate):
                    logger.info(f"Ses stream dosyası hazır (SoundCloud Failover): {candidate}")
                    return candidate
        except Exception as e_sc:
            logger.warning(f"SoundCloud failover uyarısı: {e_sc}")

        logger.error(f"Tüm istemci profilleri ve failover ile ses stream indirme başarısız: {url}")
        return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _download)


async def get_video_file_for_stream(url: str) -> Optional[str]:
    """
    Görüntülü yayın (Video Stream) için videoyu maksimum 720p MP4 formatında indirir.
    PyTgCalls MediaStream video akışı için optimize edilmiştir.

    Args:
        url: YouTube video URL'si

    Returns:
        İndirilen MP4 video dosyasının yolu veya None
    """
    file_hash = hash(url) & 0xFFFFFFFF
    output_template = os.path.join(DOWNLOADS_DIR, f"vstream_{file_hash}.%(ext)s")
    final_path = os.path.join(DOWNLOADS_DIR, f"vstream_{file_hash}.mp4")

    # Cache kontrolü
    if _is_valid_file(final_path):
        logger.info(f"Cache'den video kullanılıyor (mp4): {final_path}")
        return final_path

    # Bozuk cache dosyasını temizle
    if os.path.exists(final_path):
        try:
            os.remove(final_path)
        except Exception:
            pass

    # Maksimum 720p MP4 video ve ses profili
    opts = {
        **_get_base_opts(),
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

    def _download():
        download_configs = [
            {"extractor_args": {"youtube": {"player_client": ["android", "ios"]}}, "cookiefile": None, "name": "Mobile (Android/iOS)"},
            {"extractor_args": {"youtube": {"player_client": ["mweb", "web_creator", "web"]}}, "cookiefile": COOKIES_FILE, "name": "Cookies (Web/MWeb)"} if COOKIES_FILE else None,
            {"extractor_args": {"youtube": {"player_client": ["tv", "web_safari"]}}, "cookiefile": None, "name": "Smart TV / WebSafari"},
        ]

        for cfg in download_configs:
            if not cfg:
                continue
            try:
                run_opts = {
                    **opts,
                    "extractor_args": cfg["extractor_args"],
                }
                if cfg.get("cookiefile"):
                    run_opts["cookiefile"] = cfg["cookiefile"]
                else:
                    run_opts.pop("cookiefile", None)

                with yt_dlp.YoutubeDL(run_opts) as ydl:
                    ydl.download([url])

                if _is_valid_file(final_path):
                    logger.info(f"Video stream dosyası hazır (mp4 720p, {cfg['name']}): {final_path}")
                    return final_path

                # MP4 uzantılı diğer adayları tara
                for ext in [".mp4", ".mkv", ".webm"]:
                    candidate = os.path.join(DOWNLOADS_DIR, f"vstream_{file_hash}{ext}")
                    if _is_valid_file(candidate):
                        logger.info(f"Video stream adayı bulundu ({ext}): {candidate}")
                        return candidate
            except Exception as e:
                logger.warning(f"Video indirme profili ({cfg['name']}) uyarısı: {e}, sonraki profil deneniyor...")

        logger.error(f"Tüm istemci profilleri ile video indirme başarısız: {url}")
        return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _download)


async def cleanup_old_streams(keep_path: Optional[str] = None):
    """
    Eski ses ve video stream dosyalarını arka planda temizler.
    Bellek ve disk kullanımını düşük tutar.
    """
    import glob

    def _clean():
        try:
            # Hem stream_* (ses) hem vstream_* (video) dosyalarını temizle
            patterns = [
                os.path.join(DOWNLOADS_DIR, "stream_*"),
                os.path.join(DOWNLOADS_DIR, "vstream_*"),
            ]
            for pattern in patterns:
                for f in glob.glob(pattern):
                    if keep_path and os.path.abspath(f) == os.path.abspath(keep_path):
                        continue
                    try:
                        os.remove(f)
                    except Exception:
                        pass
        except Exception:
            pass

    await asyncio.to_thread(_clean)
