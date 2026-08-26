# ============================================
# 🐲 Ejderha Müzik Botu - Kuyruk Yöneticisi
# ============================================
# Chat bazlı müzik kuyruğunu yönetir.
# Her grubun kendi bağımsız kuyruğu vardır.

from typing import Optional
import asyncio


class QueueManager:
    """
    Chat bazlı müzik kuyruk yöneticisi.

    Her chat_id için ayrı bir kuyruk tutar.
    Thread-safe asyncio Lock kullanır.
    """

    def __init__(self):
        # chat_id -> şarkı listesi (list of dict)
        self._queues: dict[int, list[dict]] = {}
        # chat_id -> şu an çalan şarkı (dict veya None)
        self._current: dict[int, Optional[dict]] = {}
        # Thread safety için lock
        self._lock = asyncio.Lock()

    async def add(self, chat_id: int, track: dict) -> int:
        """
        Kuyruğa şarkı ekler.

        Args:
            chat_id: Grup/sohbet ID'si
            track: Şarkı bilgileri dict'i (title, url, duration vb.)

        Returns:
            Şarkının kuyruktaki sıra numarası
        """
        async with self._lock:
            if chat_id not in self._queues:
                self._queues[chat_id] = []
            self._queues[chat_id].append(track)
            return len(self._queues[chat_id])

    async def next(self, chat_id: int) -> Optional[dict]:
        """
        Kuyruktaki sıradaki şarkıyı alır ve current olarak ayarlar.

        Args:
            chat_id: Grup/sohbet ID'si

        Returns:
            Sıradaki şarkı dict'i veya None (kuyruk boşsa)
        """
        async with self._lock:
            if chat_id in self._queues and self._queues[chat_id]:
                track = self._queues[chat_id].pop(0)
                self._current[chat_id] = track
                return track
            self._current[chat_id] = None
            return None

    async def get_queue(self, chat_id: int) -> list[dict]:
        """
        Kuyruktaki tüm şarkıları döndürür.

        Args:
            chat_id: Grup/sohbet ID'si

        Returns:
            Şarkı listesi
        """
        async with self._lock:
            return list(self._queues.get(chat_id, []))

    async def current(self, chat_id: int) -> Optional[dict]:
        """
        Şu an çalan şarkıyı döndürür.

        Args:
            chat_id: Grup/sohbet ID'si

        Returns:
            Çalan şarkı dict'i veya None
        """
        async with self._lock:
            return self._current.get(chat_id)

    async def set_current(self, chat_id: int, track: Optional[dict]):
        """
        Şu an çalan şarkıyı ayarlar.

        Args:
            chat_id: Grup/sohbet ID'si
            track: Şarkı bilgileri veya None
        """
        async with self._lock:
            self._current[chat_id] = track

    async def clear(self, chat_id: int):
        """
        Belirli bir sohbetin kuyruğunu temizler.

        Args:
            chat_id: Grup/sohbet ID'si
        """
        async with self._lock:
            self._queues.pop(chat_id, None)
            self._current.pop(chat_id, None)

    async def is_empty(self, chat_id: int) -> bool:
        """
        Kuyruğun boş olup olmadığını kontrol eder.

        Args:
            chat_id: Grup/sohbet ID'si

        Returns:
            True eğer kuyruk boşsa
        """
        async with self._lock:
            return not self._queues.get(chat_id, [])

    async def has_current(self, chat_id: int) -> bool:
        """
        Şu an çalan bir şarkı olup olmadığını kontrol eder.

        Args:
            chat_id: Grup/sohbet ID'si

        Returns:
            True eğer bir şarkı çalıyorsa
        """
        async with self._lock:
            return self._current.get(chat_id) is not None


# ── Tekil (Singleton) Kuyruk Yöneticisi ──────────────────────
# Tüm modüller aynı instance'ı kullanır.
queue = QueueManager()
