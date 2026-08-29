# ============================================
# 🐲 Ejderha Müzik Botu - Spotify Yardımcıları
# ============================================
# Spotify linklerini regex ile algılar, spotipy kütüphanesiyle
# şarkı/sanatçı bilgilerini çeker ve "Sanatçı - Şarkı Adı"
# formatında YouTube arama sorgusuna dönüştürür.
#
# Yetkilendirme: SpotifyClientCredentials (Client Credentials Flow)
# Fallback: API anahtarı yoksa oEmbed ile başlık çekme

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

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# 1. SPOTİPY YETKİLENDİRME (SpotifyClientCredentials)
# ══════════════════════════════════════════════════════════════
# Client ID ve Client Secret ile Spotify Web API'ye bağlanır.
# Bu flow kullanıcı girişi gerektirmez, sadece uygulama seviyesinde
# erişim sağlar (track, album, playlist bilgisi çekmek için yeterli).

SPOTIFY_CLIENT_ID = "38a701c5ea734a739c94a031912d1ee2"
SPOTIFY_CLIENT_SECRET = "e70fe8963f4840a8a2865fb1a4b11d37"

# Spotipy istemcisini başlat
_sp_client: Optional[spotipy.Spotify] = None


def _get_spotipy_client() -> spotipy.Spotify:
    """
    Spotipy istemcisini lazy-init ile oluşturur ve cache'ler.
    İlk çağrıda SpotifyClientCredentials ile yetkilendirme yapar,
    sonraki çağrılarda aynı instance'ı döndürür.
    """
    global _sp_client
    if _sp_client is not None:
        return _sp_client

    try:
        auth_manager = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
        )
        _sp_client = spotipy.Spotify(auth_manager=auth_manager)
        logger.info("🟢 Spotify API (spotipy) başarıyla yetkilendirildi.")
    except Exception as e:
        logger.error(f"🔴 Spotify yetkilendirme hatası: {e}")
        _sp_client = None

    return _sp_client


# ══════════════════════════════════════════════════════════════
# 2. REGEX İLE SPOTİFY LİNK TESPİTİ
# ══════════════════════════════════════════════════════════════
# Kullanıcıdan gelen mesajın Spotify track linki olup olmadığını
# kontrol eder. Desteklenen formatlar:
#   - https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT
#   - https://open.spotify.com/intl-tr/track/4cOdK2wGLETKBW3PvgPWqT?si=...
#   - spotify:track:4cOdK2wGLETKBW3PvgPWqT

# URL formatı: open.spotify.com/track/... (opsiyonel intl prefix ve query params)
SPOTIFY_TRACK_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:open\.)?spotify\.com\/(?:intl-[a-zA-Z0-9-]+\/)?(track)\/([a-zA-Z0-9]+)(?:\?[^\s]*)?"
)

# URI formatı: spotify:track:...
SPOTIFY_TRACK_URI_REGEX = re.compile(
    r"spotify:(track):([a-zA-Z0-9]+)"
)

# Genişletilmiş regex (album, playlist, artist desteği için)
SPOTIFY_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:open\.)?spotify\.com\/(?:intl-[a-zA-Z0-9-]+\/)?(track|album|playlist|artist)\/([a-zA-Z0-9]+)(?:\?[^\s]*)?"
)
SPOTIFY_URI_REGEX = re.compile(
    r"spotify:(track|album|playlist|artist):([a-zA-Z0-9]+)"
)


def is_spotify_url(text: str) -> bool:
    """
    Metnin geçerli bir Spotify linki veya URI olup olmadığını kontrol eder.

    Args:
        text: Kontrol edilecek metin (kullanıcı mesajı)

    Returns:
        True → metin Spotify linki içeriyor
        False → Spotify linki değil

    Örnekler:
        >>> is_spotify_url("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT")
        True
        >>> is_spotify_url("Manga Cevapsız Sorular")
        False
    """
    if not text:
        return False
    return bool(SPOTIFY_URL_REGEX.search(text) or SPOTIFY_URI_REGEX.search(text))


def is_spotify_track_url(text: str) -> bool:
    """
    Metnin spesifik olarak bir Spotify ŞARKI (track) linki olup olmadığını kontrol eder.
    Sadece track linklerini kabul eder (album, playlist, artist hariç).
    """
    if not text:
        return False
    return bool(SPOTIFY_TRACK_URL_REGEX.search(text) or SPOTIFY_TRACK_URI_REGEX.search(text))


def parse_spotify_url(text: str) -> Optional[Tuple[str, str]]:
    """
    Spotify bağlantısından tür (track, album, playlist, artist) ve ID'yi çıkarır.

    Args:
        text: Spotify linki veya URI'si

    Returns:
        (item_type, item_id) → Örn: ("track", "4cOdK2wGLETKBW3PvgPWqT")
        veya None (eşleşme yoksa)
    """
    m = SPOTIFY_URL_REGEX.search(text)
    if m:
        return m.group(1), m.group(2)
    m = SPOTIFY_URI_REGEX.search(text)
    if m:
        return m.group(1), m.group(2)
    return None


# ══════════════════════════════════════════════════════════════
# 3. METİN DÖNÜŞÜMÜ (Spotify → "Sanatçı - Şarkı Adı")
# ══════════════════════════════════════════════════════════════
# Spotify track ID'sinden şarkı adı ve ilk sanatçı adını çeker,
# "Sanatçı Adı - Şarkı Adı" formatında döndürür.
# Bu string doğrudan yt-dlp'nin ytsearch1: parametresiyle kullanılır.

def get_track_info_from_spotify(track_id: str) -> Optional[str]:
    """
    Spotify track ID'sinden şarkı ve sanatçı bilgisini çeker.
    Döndürdüğü format YouTube aramasına hazır şekildedir.

    Args:
        track_id: Spotify Track ID (Örn: "4cOdK2wGLETKBW3PvgPWqT")

    Returns:
        "Sanatçı Adı - Şarkı Adı" formatında string
        Örn: "Manga - Cevapsız Sorular"
        veya None (hata durumunda)
    """
    sp = _get_spotipy_client()
    if not sp:
        logger.error("Spotify istemcisi oluşturulamadı, track bilgisi çekilemiyor.")
        return None

    try:
        track = sp.track(track_id)
        if not track:
            return None

        # Şarkı adını al
        song_name = track.get("name", "")

        # İlk sanatçının adını al
        artists = track.get("artists", [])
        if artists:
            artist_name = artists[0].get("name", "")
        else:
            artist_name = ""

        # "Sanatçı Adı - Şarkı Adı" formatında döndür
        if artist_name and song_name:
            result = f"{artist_name} - {song_name}"
            logger.info(f"🟢 Spotify → YouTube dönüşümü: {result}")
            return result
        elif song_name:
            return song_name
        else:
            return None

    except Exception as e:
        logger.error(f"Spotify track bilgisi çekme hatası: {e}")
        return None


async def get_track_info_async(track_id: str) -> Optional[str]:
    """
    get_track_info_from_spotify'nin async sarmalayıcısı.
    Spotipy senkron çalıştığı için executor'da çalıştırır,
    böylece event loop bloklanmaz.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_track_info_from_spotify, track_id)


# ══════════════════════════════════════════════════════════════
# FALLBACK: oEmbed ile Başlık Çekme
# ══════════════════════════════════════════════════════════════
# Spotify API anahtarı geçersizse veya hata olursa bu yöntem
# devreye girer. API gerektirmez ama sadece track başlığını verir.

async def _fetch_spotify_oembed(url: str) -> Optional[str]:
    """
    Spotify oEmbed API ile şarkı başlığını çeker (API anahtarsız fallback).
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


# ══════════════════════════════════════════════════════════════
# ANA FONKSİYON: Spotify Linkinden YouTube Arama Sorgusu Üret
# ══════════════════════════════════════════════════════════════

async def get_spotify_tracks(query: str) -> List[str]:
    """
    Spotify bağlantısını çözümler ve YouTube'da aranacak şarkı listesini döndürür.

    Akış:
    1. Regex ile link türü (track/album/playlist) ve ID ayrıştırılır
    2. Spotipy API ile şarkı/sanatçı bilgisi çekilir
    3. "Sanatçı Adı - Şarkı Adı" formatında liste döndürülür
    4. API başarısızsa oEmbed fallback devreye girer

    Args:
        query: Spotify linki veya URI'si

    Returns:
        YouTube arama sorguları listesi
        Örn: ["Manga - Cevapsız Sorular"]
    """
    parsed = parse_spotify_url(query)
    if not parsed:
        return []

    item_type, item_id = parsed
    sp = _get_spotipy_client()
    tracks: List[str] = []

    # ── Spotipy ile API'den veri çek ──────────────────────────
    if sp:
        def _fetch_from_api():
            results = []
            try:
                if item_type == "track":
                    # Tekli şarkı: "Sanatçı - Şarkı Adı"
                    t = sp.track(item_id)
                    artist_name = t["artists"][0]["name"] if t.get("artists") else ""
                    song_name = t.get("name", "")
                    if artist_name and song_name:
                        results.append(f"{artist_name} - {song_name}")

                elif item_type == "album":
                    # Albümdeki tüm şarkılar
                    album = sp.album(item_id)
                    for item in album.get("tracks", {}).get("items", []):
                        artist_name = item["artists"][0]["name"] if item.get("artists") else ""
                        song_name = item.get("name", "")
                        if artist_name and song_name:
                            results.append(f"{artist_name} - {song_name}")

                elif item_type == "playlist":
                    # Çalma listesindeki tüm şarkılar
                    pl = sp.playlist(item_id)
                    for item in pl.get("tracks", {}).get("items", []):
                        t = item.get("track")
                        if t and t.get("name"):
                            artist_name = t["artists"][0]["name"] if t.get("artists") else ""
                            results.append(f"{artist_name} - {t['name']}")

                elif item_type == "artist":
                    # Sanatçının en popüler şarkıları
                    top = sp.artist_top_tracks(item_id)
                    for t in top.get("tracks", []):
                        artist_name = t["artists"][0]["name"] if t.get("artists") else ""
                        results.append(f"{artist_name} - {t.get('name', '')}")

            except Exception as e:
                logger.error(f"Spotipy veri çekme hatası: {e}")
            return results

        try:
            loop = asyncio.get_event_loop()
            tracks = await loop.run_in_executor(None, _fetch_from_api)
        except Exception as e:
            logger.error(f"Spotipy executor hatası: {e}")

    # ── Fallback: oEmbed ile başlık çek ───────────────────────
    if not tracks:
        logger.info(f"Spotify API başarısız, oEmbed fallback deneniyor: {query}")
        clean_url = f"https://open.spotify.com/{item_type}/{item_id}"
        title = await _fetch_spotify_oembed(clean_url)
        if title:
            tracks.append(title)

    return tracks
