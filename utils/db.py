# ============================================
# 🐲 Ejderha Müzik Botu - SQLite Veritabanı & Tampon Bellek
# ============================================
# JSON dosyaları yerine SQLite tabanlı yüksek hızlı depolama.
#
# Öne çıkan özellikler:
# - WAL (Write-Ahead Logging) modu ile yüksek eşzamanlılık.
# - Tek iş parçacıklı ayrılmış executor ile kilitlenme (database lock) engeli.
# - Tampon (In-Memory Buffer) & Periyodik Flush: Mesaj istatistikleri
#   her mesajda diske yazılmaz, 5 dakikada bir topluca kaydedilir.
# - Otomatik JSON Migrasyonu: data/*.json dosyalarını ilk açılışta
#   veri kaybı olmadan SQLite'a taşır.

import os
import json
import sqlite3
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor

from bot.config import DATABASE_PATH, DATA_DIR, DB_FLUSH_INTERVAL

logger = logging.getLogger(__name__)

# SQLite için tekil thread pool (Database is locked hatalarını önler)
_db_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sqlite_worker")

# ── Bellek İçi Tamponlar (Write Buffer) ────────────────────────
# (date, chat_id, user_id) -> message_count
_pending_messages: Dict[Tuple[str, str, str], int] = {}
# user_id -> (display_name, username, updated_at)
_pending_users: Dict[str, Tuple[str, Optional[str], str]] = {}
# user_id -> (name, given_delta, received_delta)
_pending_slaps: Dict[str, Dict[str, Any]] = {}
_buffer_lock = asyncio.Lock()


def _get_connection() -> sqlite3.Connection:
    """Optimize edilmiş SQLite bağlantısı üretir."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn


def _sync_init_db():
    """Tüm SQLite tablolarını ve indekslerini oluşturur."""
    with _get_connection() as conn:
        cursor = conn.cursor()

        # 1. Filtreler Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filters (
                chat_id TEXT NOT NULL,
                keyword TEXT NOT NULL,
                reply_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, keyword)
            )
        """)

        # 2. Günlük Mesaj İstatistikleri
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                message_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (date, chat_id, user_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_date_chat ON daily_stats (date, chat_id);")

        # 3. Kullanıcı Bilgileri
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_names (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                username TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        # 4. Tokat İstatistikleri
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS slap_stats (
                user_id TEXT PRIMARY KEY,
                user_name TEXT NOT NULL,
                slaps_given INTEGER NOT NULL DEFAULT 0,
                slaps_received INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        """)

        conn.commit()
    logger.info("📦 SQLite tabloları ve indeksleri hazır.")


async def init_db():
    """Asenkron veritabanı başlatıcı."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_db_executor, _sync_init_db)


# ── Otomatik JSON Veri Migrasyonu ────────────────────────────

def _sync_migrate_json():
    """Mevcut JSON dosyalarındaki verileri SQLite'a taşır."""
    filters_file = os.path.join(DATA_DIR, "filters.json")
    stats_file = os.path.join(DATA_DIR, "daily_stats.json")
    names_file = os.path.join(DATA_DIR, "user_names.json")
    slap_file = os.path.join(DATA_DIR, "slap_stats.json")

    with _get_connection() as conn:
        cursor = conn.cursor()

        # 1. Filtreleri Taşı
        if os.path.exists(filters_file):
            try:
                with open(filters_file, "r", encoding="utf-8") as f:
                    filters_data = json.load(f)
                count = 0
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for cid, kws in filters_data.items():
                    for kw, reply in kws.items():
                        cursor.execute("""
                            INSERT OR IGNORE INTO filters (chat_id, keyword, reply_text, created_at)
                            VALUES (?, ?, ?, ?)
                        """, (str(cid), kw.lower().strip(), reply, now_str))
                        count += 1
                if count > 0:
                    logger.info(f"🔄 {count} adet filtre JSON dosyasından SQLite'a aktarıldı.")
            except Exception as e:
                logger.warning(f"Filtre JSON migrasyon uyarısı: {e}")

        # 2. Kullanıcı İsimlerini Taşı
        if os.path.exists(names_file):
            try:
                with open(names_file, "r", encoding="utf-8") as f:
                    names_data = json.load(f)
                count = 0
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for uid, name in names_data.items():
                    cursor.execute("""
                        INSERT OR IGNORE INTO user_names (user_id, display_name, updated_at)
                        VALUES (?, ?, ?)
                    """, (str(uid), str(name), now_str))
                    count += 1
                if count > 0:
                    logger.info(f"🔄 {count} adet kullanıcı adı JSON dosyasından SQLite'a aktarıldı.")
            except Exception as e:
                logger.warning(f"Kullanıcı adı JSON migrasyon uyarısı: {e}")

        # 3. Günlük İstatistikleri Taşı
        if os.path.exists(stats_file):
            try:
                with open(stats_file, "r", encoding="utf-8") as f:
                    stats_data = json.load(f)
                count = 0
                for d_str, day_data in stats_data.items():
                    groups_data = day_data.get("groups", {})
                    for cid, users in groups_data.items():
                        for uid, cnt in users.items():
                            cursor.execute("""
                                INSERT INTO daily_stats (date, chat_id, user_id, message_count)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(date, chat_id, user_id) DO UPDATE SET
                                message_count = MAX(message_count, excluded.message_count)
                            """, (d_str, str(cid), str(uid), int(cnt)))
                            count += 1
                    # Genel grupta olmayanlar (chat_id="global")
                    for uid, cnt in day_data.items():
                        if uid != "groups" and isinstance(cnt, int):
                            cursor.execute("""
                                INSERT INTO daily_stats (date, chat_id, user_id, message_count)
                                VALUES (?, 'global', ?, ?)
                                ON CONFLICT(date, chat_id, user_id) DO UPDATE SET
                                message_count = MAX(message_count, excluded.message_count)
                            """, (d_str, str(uid), int(cnt)))
                            count += 1
                if count > 0:
                    logger.info(f"🔄 {count} adet mesaj istatistiği JSON dosyasından SQLite'a aktarıldı.")
            except Exception as e:
                logger.warning(f"İstatistik JSON migrasyon uyarısı: {e}")

        # 4. Tokat İstatistiklerini Taşı
        if os.path.exists(slap_file):
            try:
                with open(slap_file, "r", encoding="utf-8") as f:
                    slap_data = json.load(f)
                count = 0
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for uid, sinfo in slap_data.items():
                    if isinstance(sinfo, dict):
                        cursor.execute("""
                            INSERT INTO slap_stats (user_id, user_name, slaps_given, slaps_received, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET
                            slaps_given = MAX(slaps_given, excluded.slaps_given),
                            slaps_received = MAX(slaps_received, excluded.slaps_received)
                        """, (
                            str(uid),
                            sinfo.get("name", "Bilinmeyen"),
                            int(sinfo.get("given", 0)),
                            int(sinfo.get("received", 0)),
                            now_str
                        ))
                        count += 1
                if count > 0:
                    logger.info(f"🔄 {count} adet tokat istatistiği JSON dosyasından SQLite'a aktarıldı.")
            except Exception as e:
                logger.warning(f"Tokat JSON migrasyon uyarısı: {e}")

        conn.commit()


async def migrate_json_to_db():
    """Asenkron JSON migrasyon çağrısı."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_db_executor, _sync_migrate_json)


# ── Tampon Boşaltma (Batch Flush) ────────────────────────────

def _sync_flush_buffers(messages_copy, users_copy, slaps_copy):
    """Bellekte biriken tüm değişiklikleri tek bir SQLite transaction'ında yazar."""
    if not messages_copy and not users_copy and not slaps_copy:
        return

    with _get_connection() as conn:
        cursor = conn.cursor()

        # 1. Mesaj Sayaçları
        if messages_copy:
            for (d_str, cid, uid), count in messages_copy.items():
                cursor.execute("""
                    INSERT INTO daily_stats (date, chat_id, user_id, message_count)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(date, chat_id, user_id) DO UPDATE SET
                    message_count = message_count + excluded.message_count
                """, (d_str, cid, uid, count))

        # 2. Kullanıcı Adları
        if users_copy:
            for uid, (disp_name, uname, u_time) in users_copy.items():
                cursor.execute("""
                    INSERT INTO user_names (user_id, display_name, username, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    username = COALESCE(excluded.username, user_names.username),
                    updated_at = excluded.updated_at
                """, (uid, disp_name, uname, u_time))

        # 3. Tokat İstatistikleri
        if slaps_copy:
            for uid, sdata in slaps_copy.items():
                cursor.execute("""
                    INSERT INTO slap_stats (user_id, user_name, slaps_given, slaps_received, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                    user_name = excluded.user_name,
                    slaps_given = slaps_given + excluded.slaps_given,
                    slaps_received = slaps_received + excluded.slaps_received,
                    updated_at = excluded.updated_at
                """, (
                    uid,
                    sdata["name"],
                    sdata["given"],
                    sdata["received"],
                    sdata["updated_at"]
                ))

        conn.commit()
    logger.debug(
        f"💾 SQLite Flush tamamlandı: {len(messages_copy)} mesaj kaydı, "
        f"{len(users_copy)} kullanıcı, {len(slaps_copy)} tokat kaydı diske yazıldı."
    )


async def flush_pending_data():
    """Tampondaki verileri alır ve SQLite'a asenkron kaydeder."""
    global _pending_messages, _pending_users, _pending_slaps
    async with _buffer_lock:
        if not _pending_messages and not _pending_users and not _pending_slaps:
            return
        messages_copy = _pending_messages.copy()
        users_copy = _pending_users.copy()
        slaps_copy = _pending_slaps.copy()
        _pending_messages.clear()
        _pending_users.clear()
        _pending_slaps.clear()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_db_executor, _sync_flush_buffers, messages_copy, users_copy, slaps_copy)


async def periodic_db_flush_worker():
    """5 dakikada bir otomatik çalışan arka plan tampon yazma döngüsü."""
    logger.info(f"⏱️ SQLite periyodik tampon yazıcı başlatıldı (Her {DB_FLUSH_INTERVAL} saniyede bir).")
    while True:
        try:
            await asyncio.sleep(DB_FLUSH_INTERVAL)
            await flush_pending_data()
        except asyncio.CancelledError:
            logger.info("🛑 SQLite flush worker durduruldu, kalan veriler kaydediliyor...")
            await flush_pending_data()
            break
        except Exception as e:
            logger.error(f"SQLite periyodik flush hatası: {e}")


# ── Filtre Fonksiyonları (utils/db.py) ────────────────────────

def _sync_get_all_chat_filters(chat_id: str) -> Dict[str, str]:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT keyword, reply_text FROM filters WHERE chat_id = ?", (str(chat_id),))
        return {row["keyword"]: row["reply_text"] for row in cursor.fetchall()}


async def get_chat_filters(chat_id: int) -> Dict[str, str]:
    """Belirtilen gruba ait tüm filtreleri sözlük olarak döner."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, _sync_get_all_chat_filters, str(chat_id))


def _sync_save_chat_filter(chat_id: str, keyword: str, reply_text: str):
    with _get_connection() as conn:
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO filters (chat_id, keyword, reply_text, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id, keyword) DO UPDATE SET
            reply_text = excluded.reply_text,
            created_at = excluded.created_at
        """, (str(chat_id), keyword.lower().strip(), reply_text, now_str))
        conn.commit()


async def save_chat_filter(chat_id: int, keyword: str, reply_text: str):
    """Yeni bir filtre kaydeder veya günceller."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_db_executor, _sync_save_chat_filter, str(chat_id), keyword, reply_text)


def _sync_delete_chat_filter(chat_id: str, keyword: str) -> bool:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM filters WHERE chat_id = ? AND keyword = ?", (str(chat_id), keyword.lower().strip()))
        conn.commit()
        return cursor.rowcount > 0


async def delete_chat_filter(chat_id: int, keyword: str) -> bool:
    """Belirtilen filtreyi siler."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, _sync_delete_chat_filter, str(chat_id), keyword)


def _sync_clear_all_chat_filters(chat_id: str) -> bool:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM filters WHERE chat_id = ?", (str(chat_id),))
        conn.commit()
        return cursor.rowcount > 0


async def clear_all_chat_filters(chat_id: int) -> bool:
    """Gruptaki tüm filtreleri temizler."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, _sync_clear_all_chat_filters, str(chat_id))


# ── Mesaj İstatistikleri & Aktiflik Fonksiyonları ───────────────

async def record_user_message(user_id: int, user_name: str, chat_id: Optional[int] = None, username: Optional[str] = None):
    """
    Gelen mesajı bellek içi tampona ekler.
    Diske hemen yazmayarak performansı maksimize eder.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    uid_str = str(user_id)
    cid_str = str(chat_id) if chat_id else "global"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async with _buffer_lock:
        # Gruba özel sayaç
        group_key = (today_str, cid_str, uid_str)
        _pending_messages[group_key] = _pending_messages.get(group_key, 0) + 1

        # Genel sayaç
        global_key = (today_str, "global", uid_str)
        _pending_messages[global_key] = _pending_messages.get(global_key, 0) + 1

        # Kullanıcı adı
        _pending_users[uid_str] = (user_name, username, now_str)

        # Tampon aşırı büyürse (örn. 200 mesaj) otomatik boşalt
        if len(_pending_messages) >= 200:
            asyncio.create_task(flush_pending_data())


def _sync_get_daily_leaderboard(date_str: str, chat_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Günün en aktif kullanıcılarını çeker."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        if chat_id:
            cursor.execute("""
                SELECT s.user_id, s.message_count, COALESCE(u.display_name, 'Savaşçı') as name, u.username
                FROM daily_stats s
                LEFT JOIN user_names u ON s.user_id = u.user_id
                WHERE s.date = ? AND s.chat_id = ?
                ORDER BY s.message_count DESC
                LIMIT ?
            """, (date_str, str(chat_id), limit))
        else:
            cursor.execute("""
                SELECT s.user_id, s.message_count, COALESCE(u.display_name, 'Savaşçı') as name, u.username
                FROM daily_stats s
                LEFT JOIN user_names u ON s.user_id = u.user_id
                WHERE s.date = ? AND s.chat_id = 'global'
                ORDER BY s.message_count DESC
                LIMIT ?
            """, (date_str, limit))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


async def get_daily_leaderboard(chat_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Günün en çok mesaj atan kullanıcılarını döner (Tampondaki canlı veriyi de dahil eder)."""
    # Önce tampondaki verileri diske dökerek %100 güncel veri garanti et
    await flush_pending_data()
    today_str = datetime.now().strftime("%Y-%m-%d")
    cid_str = str(chat_id) if chat_id else None
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, _sync_get_daily_leaderboard, today_str, cid_str, limit)


def _sync_get_group_stats(chat_id: str, date_str: str) -> Dict[str, Any]:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(user_id) as active_users, SUM(message_count) as total_messages
            FROM daily_stats
            WHERE date = ? AND chat_id = ?
        """, (date_str, str(chat_id)))
        row = cursor.fetchone()
        return {
            "active_users": row["active_users"] if row and row["active_users"] else 0,
            "total_messages": row["total_messages"] if row and row["total_messages"] else 0,
        }


async def get_group_stats(chat_id: int) -> Dict[str, Any]:
    """Grubun bugünkü toplam mesaj ve aktif üye sayısını döner."""
    await flush_pending_data()
    today_str = datetime.now().strftime("%Y-%m-%d")
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, _sync_get_group_stats, str(chat_id), today_str)


# ── Tokat İstatistikleri (utils/db.py) ─────────────────────────

async def record_slap_event(sender_id: int, sender_name: str, target_id: int, target_name: str):
    """Tokat atan ve yiyen kullanıcıların istatistiklerini tampona işler."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sid_str = str(sender_id)
    tid_str = str(target_id)

    async with _buffer_lock:
        # Atan kişi
        if sid_str not in _pending_slaps:
            _pending_slaps[sid_str] = {"name": sender_name, "given": 0, "received": 0, "updated_at": now_str}
        _pending_slaps[sid_str]["given"] += 1
        _pending_slaps[sid_str]["name"] = sender_name
        _pending_slaps[sid_str]["updated_at"] = now_str

        # Yiyen kişi
        if tid_str not in _pending_slaps:
            _pending_slaps[tid_str] = {"name": target_name, "given": 0, "received": 0, "updated_at": now_str}
        _pending_slaps[tid_str]["received"] += 1
        _pending_slaps[tid_str]["name"] = target_name
        _pending_slaps[tid_str]["updated_at"] = now_str


def _sync_get_slap_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, user_name, slaps_given, slaps_received
            FROM slap_stats
            ORDER BY slaps_given DESC, slaps_received DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]


async def get_slap_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Tokat liderlik tablosunu döner."""
    await flush_pending_data()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, _sync_get_slap_leaderboard, limit)
