# ============================================
# 🐲 Ejderha Müzik Botu - Akıllı Önbellek (Cache) Motoru
# ============================================
# TTL (Time-To-Live) ve LRU (Least Recently Used) tabanlı
# bellek içi asenkron önbellekleme sistemi.
#
# Öne çıkan özellikler:
# - YouTube arama ve metadata sonuçlarını 1 saat (3600s) saklar.
# - Tekrarlanan istekleri anında bellekten döner (sıfır ağ gecikmesi).
# - Otomatik boyut denetimi (LRU ile en eski girdiyi tahliye eder).
# - Asenkron fonksiyonlar için @cached dekoratörü sunar.

import time
import asyncio
import logging
from collections import OrderedDict
from typing import Any, Optional, Callable, Dict, Tuple
from functools import wraps

from bot.config import CACHE_TTL

logger = logging.getLogger(__name__)


class TTLCache:
    """
    Asenkron ve iş parçacığı (thread) güvenli TTL + LRU Önbellek sınıfı.
    Belirlenen süre (TTL) dolduğunda veya maksimum boyuta (maxsize)
    ulaşıldığında elemanları otomatik olarak temizler.
    """

    def __init__(self, maxsize: int = 1000, default_ttl: int = CACHE_TTL):
        self._maxsize: int = maxsize
        self._default_ttl: int = default_ttl
        # Key -> (expire_timestamp, value)
        self._cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._lock: asyncio.Lock = asyncio.Lock()
        self._hits: int = 0
        self._misses: int = 0

    async def get(self, key: str) -> Optional[Any]:
        """
        Önbellekten bir anahtarın değerini çeker.
        Süresi dolmuşsa siler ve None döner.
        """
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            expire_at, value = self._cache[key]
            # Zaman aşımı kontrolü
            if time.time() > expire_at:
                del self._cache[key]
                self._misses += 1
                return None

            # LRU prensibi: Erişilen anahtarı en sona (en güncel konuma) taşı
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Önbelleğe yeni bir anahtar-değer çifti ekler veya günceller.
        Maksimum kapasite aşılırsa en eski elemanı tahliye eder.
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expire_at = time.time() + effective_ttl

        async with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._maxsize:
                # En eski elemanı tahliye et (LRU)
                oldest_key, _ = self._cache.popitem(last=False)
                logger.debug(f"🗑️ Önbellek doldu, en eski anahtar tahliye edildi: {oldest_key}")

            self._cache[key] = (expire_at, value)

    async def delete(self, key: str) -> bool:
        """Belirtilen anahtarı önbellekten manuel olarak kaldırır."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Tüm önbelleği sıfırlar."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info("🧹 Önbellek tamamen temizlendi.")

    async def cleanup_expired(self) -> int:
        """Süresi dolmuş tüm eski girdileri temizler ve silinen sayıyı döner."""
        now = time.time()
        removed_count = 0
        async with self._lock:
            expired_keys = [k for k, (exp, _) in self._cache.items() if now > exp]
            for k in expired_keys:
                del self._cache[k]
                removed_count += 1
        if removed_count > 0:
            logger.debug(f"🧹 {removed_count} adet süresi dolmuş önbellek girdisi temizlendi.")
        return removed_count

    def size(self) -> int:
        """Önbellekteki güncel kayıt sayısını döner."""
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """Önbellek isabet ve boyut istatistiklerini raporlar."""
        total = self._hits + self._misses
        hit_ratio = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio_percent": round(hit_ratio, 2),
        }


# ── Global Ön Tanımlı Önbellek Örnekleri ───────────────────────

# YouTube arama & meta verileri için 1 saatlik (3600 sn) arama önbelleği
search_cache = TTLCache(maxsize=1000, default_ttl=CACHE_TTL)

# Medya doğrudan akış URL'leri için 30 dakikalık önbellek
stream_cache = TTLCache(maxsize=500, default_ttl=1800)


def cached(cache_instance: TTLCache, ttl: Optional[int] = None):
    """
    Asenkron fonksiyonların dönüş değerlerini otomatik önbelleğe alan dekoratör.
    Fonksiyon adı ve argümanlarını kullanarak benzersiz bir önbellek anahtarı üretir.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Benzersiz cache anahtarı oluştur
            arg_str = ":".join(str(a) for a in args)
            kwarg_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = f"{func.__name__}:{arg_str}:{kwarg_str}"

            # Önbellekte varsa hemen dön
            cached_val = await cache_instance.get(cache_key)
            if cached_val is not None:
                return cached_val

            # Yoksa asıl fonksiyonu çalıştır
            result = await func(*args, **kwargs)
            if result is not None:
                await cache_instance.set(cache_key, result, ttl=ttl)

            return result
        return wrapper
    return decorator
