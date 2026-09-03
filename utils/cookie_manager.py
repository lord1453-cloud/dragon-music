# ============================================
# 🐲 Ejderha Müzik Botu - Otomatik Çerez & Oturum Yöneticisi
# ============================================
# YouTube misafir (Guest / Visitor) oturum çerezlerini
# arka planda otomatik olarak üretir, doğrular ve periyodik
# olarak yeniler. Kullanıcı müdahalesi gerektirmez.

import os
import time
import asyncio
import logging
from typing import Optional, Dict, Tuple, Any
import aiohttp
import yarl

from bot.config import YOUTUBE_COOKIE_FILE, YOUTUBE_COOKIES_FROM_BROWSER, COOKIES_FILE

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUEST_COOKIES_FILE = os.path.join(_BASE_DIR, "guest_cookies.txt")

SUPPORTED_BROWSERS = {
    "chrome", "edge", "firefox", "opera", "brave", "vivaldi", "whale", "safari", "chromium"
}

_refresher_task: Optional[asyncio.Task] = None
_cookie_lock = asyncio.Lock()


def validate_cookie_file(cookie_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Netscape formatındaki çerez dosyasını doğrular.
    Çerez içeriğini ASLA loglamaz veya dışarı sızdırmaz.
    (is_valid, reason) döner.
    """
    path = cookie_path or YOUTUBE_COOKIE_FILE or COOKIES_FILE
    if not path:
        return False, "Çerez dosyası belirtilmemiş."
    if not os.path.exists(path):
        return False, f"Çerez dosyası bulunamadı: {os.path.basename(path)}"
    if not os.path.isfile(path):
        return False, f"Çerez yolu bir dosya değil: {os.path.basename(path)}"
    if os.path.getsize(path) < 10:
        return False, f"Çerez dosyası boş veya çok küçük: {os.path.basename(path)}"

    try:
        now = time.time()
        total_cookies = 0
        expired_count = 0
        has_netscape_header = False

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    if "Netscape" in line or "cookie" in line.lower():
                        has_netscape_header = True
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

        if total_cookies == 0:
            return False, f"Çerez dosyasında geçerli çerez bulunamadı: {os.path.basename(path)}"

        # Eğer çerezlerin tamamı eskiyse geçersiz say
        if expired_count >= total_cookies:
            return False, f"Çerezlerin tümünün süresi dolmuş ({expired_count}/{total_cookies})."

        return True, f"Geçerli ({total_cookies} çerez, {expired_count} süresi dolmuş)"
    except Exception as e:
        return False, f"Çerez dosyası okuma hatası: {type(e).__name__}"


def is_user_cookie_valid(cookie_path: Optional[str] = None) -> bool:
    """Geriye dönük uyumluluk için bool döner."""
    valid, _ = validate_cookie_file(cookie_path)
    return valid


def get_browser_cookie_config() -> Optional[str]:
    """Yapılandırılmış ve desteklenen tarayıcı adını döndürür."""
    if not YOUTUBE_COOKIES_FROM_BROWSER:
        return None
    browser = YOUTUBE_COOKIES_FROM_BROWSER.strip().lower()
    if browser in SUPPORTED_BROWSERS:
        return browser
    logger.warning(
        f"⚠️ Desteklenmeyen tarayıcı adı belirtildi: '{browser}'. "
        f"Desteklenenler: {', '.join(sorted(SUPPORTED_BROWSERS))}"
    )
    return None


def get_youtube_auth_status() -> Dict[str, Any]:
    """
    YouTube kimlik doğrulama öncelik zincirini değerlendirir ve durum özeti verir.
    Kesinlikle hassas çerez verisi içermez.
    """
    # 1. Öncelik: Cookie File
    target_file = YOUTUBE_COOKIE_FILE or COOKIES_FILE
    if target_file and os.path.exists(target_file):
        is_valid, reason = validate_cookie_file(target_file)
        if is_valid:
            return {
                "type": "cookie_file",
                "ready": True,
                "detail": f"Cookie file found ({os.path.basename(target_file)})",
                "path": target_file,
            }
        else:
            logger.warning(f"⚠️ YouTube cookie authentication uyarısı: {reason}")

    # 2. Öncelik: Browser Cookies
    browser = get_browser_cookie_config()
    if browser:
        return {
            "type": "browser",
            "ready": True,
            "detail": f"Browser cookies configured ({browser})",
            "browser": browser,
        }

    # 3. Anonim / Çerezsiz
    return {
        "type": "none",
        "ready": False,
        "detail": "No cookie authentication configured",
    }


async def refresh_visitor_cookies(file_path: str = GUEST_COOKIES_FILE) -> bool:
    """
    YouTube'dan taze misafir (Visitor) çerezleri çeker ve Netscape formatında kaydeder.
    """
    async with _cookie_lock:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                target_url = yarl.URL("https://www.youtube.com")
                async with session.get(target_url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        logger.warning(f"YouTube visitor çerez isteği başarısız (HTTP {resp.status})")
                        return False

                    cookies_map: Dict[str, str] = {}
                    # Varsayılan temel tercih çerezleri
                    cookies_map["PREF"] = "f6=40000000&tz=UTC&f7=100&hl=en"
                    cookies_map["SOCS"] = "CAI"
                    cookies_map["GPS"] = "1"

                    extracted = session.cookie_jar.filter_cookies(target_url)
                    for key, morsel in extracted.items():
                        cookies_map[key] = morsel.value

                    lines = [
                        "# Netscape HTTP Cookie File",
                        "# Auto-generated YouTube Guest/Visitor Session by Ejderha Bot",
                        "# Generated at: " + time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                        "",
                    ]

                    future_expiry = int(time.time()) + (86400 * 180)  # 6 ay
                    for c_name, c_val in cookies_map.items():
                        # domain, flag, path, secure, expiry, name, value
                        secure_flag = "TRUE" if c_name.startswith("__Secure-") or c_name in ["SOCS", "VISITOR_INFO1_LIVE", "YSC"] else "FALSE"
                        lines.append(f".youtube.com\tTRUE\t/\t{secure_flag}\t{future_expiry}\t{c_name}\t{c_val}")

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")

                    logger.info("🍪 [OTURUM] Taze YouTube misafir çerezleri başarıyla üretildi ve güncellendi.")
                    return True
        except Exception as e:
            logger.warning(f"Otomatik visitor çerez oluşturma uyarısı: {e}")
            return False


async def get_effective_cookiefile() -> Optional[str]:
    """
    Kullanılacak en uygun ve taze çerez dosyasını döndürür.
    - Kullanıcının cookies.txt'si geçerliyse onu kullanır.
    - Geçersizse veya yoksa otomatik üretilen guest_cookies.txt'yi devreye sokar.
    """
    active_user_cookie = YOUTUBE_COOKIE_FILE or COOKIES_FILE
    if is_user_cookie_valid(active_user_cookie):
        return active_user_cookie

    # Misafir çerezi var mı ve 6 saatten taze mi kontrol et
    need_refresh = True
    if os.path.exists(GUEST_COOKIES_FILE) and os.path.getsize(GUEST_COOKIES_FILE) > 50:
        file_age = time.time() - os.path.getmtime(GUEST_COOKIES_FILE)
        if file_age < 21600:  # 6 saat
            need_refresh = False

    if need_refresh:
        await refresh_visitor_cookies(GUEST_COOKIES_FILE)

    if os.path.exists(GUEST_COOKIES_FILE) and os.path.getsize(GUEST_COOKIES_FILE) > 50:
        return GUEST_COOKIES_FILE

    return None


async def _refresher_loop():
    """Arka planda her 6 saatte bir visitor çerezlerini otomatik tazeleyen döngü."""
    logger.info("🔄 Otomatik çerez yenileme servisi başlatıldı (Periyot: 6 saat).")
    while True:
        try:
            # 6 saat bekle
            await asyncio.sleep(21600)
            active_cookie = YOUTUBE_COOKIE_FILE or COOKIES_FILE
            if not is_user_cookie_valid(active_cookie):
                await refresh_visitor_cookies(GUEST_COOKIES_FILE)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Çerez yenileme döngüsü uyarısı: {e}")
            await asyncio.sleep(300)


def start_cookie_refresher():
    """Çerez yenileyici arka plan görevini başlatır."""
    global _refresher_task
    if _refresher_task is None or _refresher_task.done():
        _refresher_task = asyncio.create_task(_refresher_loop())


def stop_cookie_refresher():
    """Çerez yenileyici arka plan görevini durdurur."""
    global _refresher_task
    if _refresher_task and not _refresher_task.done():
        _refresher_task.cancel()
        _refresher_task = None
