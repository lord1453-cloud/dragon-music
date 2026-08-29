# ============================================
# 🐲 Ejderha Müzik Botu - Spotify Yardımcıları
# ============================================
# Spotify linklerini algılar, spotipy ve fallback yöntemleriyle
# şarkı/sanatçı bilgilerini çekerek YouTube arama formatına dönüştürür.

import re
import ssl
import logging
import asyncio
from typing import Optional, List, Tuple
import aiohttp

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = False

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    HAS_SPOTIPY = True
except ImportError:
    HAS_SPOTIPY = False

from bot.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

logger = logging.getLogger(__name__)

# ── Spotify Regex Kalıpları ──────────────────────────────────
SPOTIFY_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:open\.)?spotify\.com\/(?:intl-[a-zA-Z0-9-]+\/)?(track|album|playlist|artist)\/([a-zA-Z0-9]+)(?:\?[^\s]+)?"
)
SPOTIFY_URI_REGEX = re.compile(
    r"spotify:(track|album|playlist|artist):([a-zA-Z0-9]+)"
)

# ── Spotipy İstemcisi Başlatma ────────────────────────────────
_sp_client: Optional[object] = None

def _get_spotipy_client():
    """Spotipy istemcisini yapılandırır ve döndürür."""
    global _sp_client
    if not HAS_SPOTIPY:
        return None
    if _sp_client is not None:
        return _sp_client

    if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
        try:
            auth_manager = SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
            )
            _sp_client = spotipy.Spotify(auth_manager=auth_manager)
            logger.info("🎵 Spotify API (spotipy) başarıyla yetkilendirildi.")
        except Exception as e:
            logger.warning(f"Spotify yetkilendirme hatası: {e}")
            _sp_client = None
    return _sp_client


def is_spotify_url(text: str) -> bool:
    """
    Metnin geçerli bir Spotify linki veya URI olup olmadığını kontrol eder.
    """
    if not text:
        return False
    return bool(SPOTIFY_URL_REGEX.search(text) or SPOTIFY_URI_REGEX.search(text))


def parse_spotify_url(text: str) -> Optional[Tuple[str, str]]:
    """
    Spotify bağlantısından tür (track, album, playlist, artist) ve ID'yi çıkarır.
    
    Returns:
        (item_type, item_id) veya None
    """
    m = SPOTIFY_URL_REGEX.search(text)
    if m:
        return m.group(1), m.group(2)
    m = SPOTIFY_URI_REGEX.search(text)
    if m:
        return m.group(1), m.group(2)
    return None


async def _fetch_spotify_oembed(url: str) -> Optional[str]:
    """
    Spotify API anahtarı olmadan tekli şarkı başlığını oEmbed API ile çeker (Fallback).
    """
    oembed_url = f"https://open.spotify.com/oembed?url={url}"
    try:
        conn = aiohttp.TCPConnector(ssl=_SSL_CTX)
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(oembed_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    title = data.get("title")
                    if title:
                        return title
    except Exception as e:
        logger.debug(f"Spotify oEmbed fallback hatası: {e}")
    return None


async def _fetch_spotify_html_meta(url: str) -> Optional[str]:
    """
    Spotify sayfasından OpenGraph meta etiketlerini okuyarak başlık çeker (İkinci Fallback).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        conn = aiohttp.TCPConnector(ssl=_SSL_CTX)
        async with aiohttp.ClientSession(connector=conn, headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html)
                    if m:
                        return m.group(1)
    except Exception as e:
        logger.debug(f"Spotify HTML meta çekme hatası: {e}")
    return None


async def get_spotify_tracks(query: str) -> List[str]:
    """
    Spotify bağlantısını çözümler ve YouTube'da aranacak şarkı listesini döndürür.

    Args:
        query: Spotify linki veya URI'si

    Returns:
        YouTube arama sorguları listesi (Örn: ["Rick Astley - Never Gonna Give You Up"])
    """
    parsed = parse_spotify_url(query)
    if not parsed:
        return []

    item_type, item_id = parsed
    sp = _get_spotipy_client()
    tracks: List[str] = []

    # 1. Spotipy ile resmi API üzerinden çekmeyi dene
    if sp:
        def _fetch_from_api():
            results = []
            try:
                if item_type == "track":
                    t = sp.track(item_id)
                    artists = ", ".join(a["name"] for a in t.get("artists", []))
                    results.append(f"{artists} - {t.get('name', '')}")

                elif item_type == "album":
                    album = sp.album(item_id)
                    for item in album.get("tracks", {}).get("items", []):
                        artists = ", ".join(a["name"] for a in item.get("artists", []))
                        results.append(f"{artists} - {item.get('name', '')}")

                elif item_type == "playlist":
                    pl = sp.playlist(item_id)
                    for item in pl.get("tracks", {}).get("items", []):
                        t = item.get("track")
                        if t and t.get("name"):
                            artists = ", ".join(a["name"] for a in t.get("artists", []))
                            results.append(f"{artists} - {t.get('name', '')}")

                elif item_type == "artist":
                    top = sp.artist_top_tracks(item_id)
                    for t in top.get("tracks", []):
                        artists = ", ".join(a["name"] for a in t.get("artists", []))
                        results.append(f"{artists} - {t.get('name', '')}")
            except Exception as e:
                logger.error(f"Spotipy veri çekme hatası: {e}")
            return results

        try:
            loop = asyncio.get_event_loop()
            tracks = await loop.run_in_executor(None, _fetch_from_api)
        except Exception as e:
            logger.error(f"Spotipy executor hatası: {e}")

    # 2. Eğer API anahtarı yoksa veya API başarısız olduysa fallback yöntemlerini dene
    if not tracks:
        logger.info(f"Spotify API anahtarı yok/boş, fallback deneniyor: {query}")
        clean_url = f"https://open.spotify.com/{item_type}/{item_id}"
        
        # oEmbed dene
        title = await _fetch_spotify_oembed(clean_url)
        if not title:
            # HTML metadata dene
            title = await _fetch_spotify_html_meta(clean_url)

        if title:
            tracks.append(title)

    return tracks
