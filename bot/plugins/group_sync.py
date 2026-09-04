# ============================================
# 🐲 Ejderha Müzik Botu - Grup Senkronizasyonu
# ============================================
# Botun ve Userbot'un bulunduğu tüm sohbetleri (grup, süper grup, kanal)
# tarar; kurucu, üye sayısı ve yetki bilgilerini toplayıp
# Harici Admin Paneli için SQLite veritabanına (data/panel_data.db) yazar.

import os
import sqlite3
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus, ChatMembersFilter

from bot.config import BOT_VERSION
from bot.clients import user_client
from utils.decorators import clean_command

logger = logging.getLogger(__name__)

# ── Veritabanı Yolu ───────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "panel_data.db")


# ── SQLite Veritabanı Başlatma ─────────────────────────────────
def init_panel_db():
    """panel_data.db SQLite tablolarını oluşturur."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Gruplar Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            chat_type TEXT,
            username TEXT,
            owner_id INTEGER,
            owner_name TEXT,
            owner_username TEXT,
            members_count INTEGER,
            bot_role TEXT,
            is_admin INTEGER,
            last_sync TEXT
        )
    """)

    # 2. Sistem ve Bot Durumu Tablosu (Heartbeat)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_status (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def update_system_status(key: str, value: str):
    """Sistem ve heartbeat durumunu günceller."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO system_status (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (key, str(value), now_str))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"system_status güncelleme uyarısı: {e}")


def save_group_to_db(group_info: dict):
    """Tek bir grubun bilgilerini veritabanına kaydeder."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO groups (
                chat_id, title, chat_type, username,
                owner_id, owner_name, owner_username,
                members_count, bot_role, is_admin, last_sync
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title=excluded.title,
                chat_type=excluded.chat_type,
                username=excluded.username,
                owner_id=excluded.owner_id,
                owner_name=excluded.owner_name,
                owner_username=excluded.owner_username,
                members_count=excluded.members_count,
                bot_role=excluded.bot_role,
                is_admin=excluded.is_admin,
                last_sync=excluded.last_sync
        """, (
            group_info["chat_id"],
            group_info["title"],
            group_info["chat_type"],
            group_info.get("username", ""),
            group_info.get("owner_id", 0),
            group_info.get("owner_name", "Bilinmiyor"),
            group_info.get("owner_username", ""),
            group_info.get("members_count", 0),
            group_info.get("bot_role", "member"),
            group_info.get("is_admin", 0),
            now_str,
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Grup veritabanına kaydedilemedi ({group_info.get('chat_id')}): {e}")


# ── Senkronizasyon Motoru ─────────────────────────────────────
async def sync_all_groups(client: Client) -> Tuple[int, int, int]:
    """
    Sohbetleri tarar ve veritabanını günceller.
    Telegram kısıtlaması nedeniyle get_dialogs() metodunu Userbot (user_client) üzerinden çağırır.
    Döndürür: (taranan_grup_sayısı, toplam_üye, admin_olunan_grup_sayısı)
    """
    init_panel_db()
    total_groups = 0
    total_members = 0
    admin_groups = 0

    logger.info("🔄 Harici Admin Paneli için sohbet senkronizasyonu başlatılıyor...")
    update_system_status("bot_heartbeat", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    update_system_status("bot_version", BOT_VERSION)
    update_system_status("bot_status", "online")

    # 1. Dialog tarama için Userbot hesabını (user_client) kullan
    scanner_client = user_client if (user_client and getattr(user_client, "is_connected", False)) else None

    if scanner_client:
        try:
            async for dialog in scanner_client.get_dialogs():
                chat = dialog.chat
                if not chat or chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                    continue

                chat_id = chat.id
                title = chat.title or f"Sohbet_{chat_id}"
                chat_type = chat.type.value if hasattr(chat.type, "value") else str(chat.type)
                username = chat.username or ""

                # Üye sayısı
                members_count = getattr(chat, "members_count", 0)
                if not members_count or members_count <= 0:
                    try:
                        members_count = await client.get_chat_members_count(chat_id)
                    except Exception:
                        members_count = 0

                # Botun yetkisi (bot_client üzerinden kontrol)
                bot_role = "member"
                is_admin = 0
                try:
                    me_member = await client.get_chat_member(chat_id, "me")
                    if me_member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
                        is_admin = 1
                        bot_role = "admin" if me_member.status == ChatMemberStatus.ADMINISTRATOR else "owner"
                except Exception:
                    pass

                # Grubun Kurucusu (Owner)
                owner_id = 0
                owner_name = "Bilinmiyor"
                owner_username = ""

                try:
                    async for member in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
                        if member.status == ChatMemberStatus.OWNER and member.user:
                            owner_id = member.user.id
                            owner_name = member.user.first_name or member.user.username or f"Kullanıcı_{owner_id}"
                            owner_username = member.user.username or ""
                            break
                except Exception as admin_err:
                    logger.debug(f"Grup kurucusu çekilemedi ({chat_id}): {admin_err}")

                group_data = {
                    "chat_id": chat_id,
                    "title": title,
                    "chat_type": chat_type,
                    "username": username,
                    "owner_id": owner_id,
                    "owner_name": owner_name,
                    "owner_username": owner_username,
                    "members_count": members_count,
                    "bot_role": bot_role,
                    "is_admin": is_admin,
                }

                save_group_to_db(group_data)
                total_groups += 1
                total_members += members_count
                if is_admin:
                    admin_groups += 1

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Userbot üzerinden grup senkronizasyonu hatası: {e}", exc_info=True)
    else:
        logger.info("ℹ️ Userbot bağlı değil, gruplar gelen mesaj trafiğiyle anlık veritabanına işlenecektir.")

    update_system_status("total_groups", str(total_groups))
    update_system_status("total_members", str(total_members))
    update_system_status("admin_groups", str(admin_groups))
    update_system_status("last_sync_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    logger.info(f"✅ Senkronizasyon bitti: {total_groups} grup, {total_members} üye, {admin_groups} adminlik.")
    return total_groups, total_members, admin_groups


# ── Otomatik Anlık Grup Kaydedici ──────────────────────────────
@Client.on_message(filters.group, group=20)
async def auto_record_group_handler(client: Client, message: Message):
    """
    Botun bulunduğu gruplardan mesaj geldikçe grubu otomatik olarak
    panel_data.db veritabanına kaydeder.
    """
    try:
        if message.chat and message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
            chat = message.chat
            group_data = {
                "chat_id": chat.id,
                "title": chat.title or f"Grup_{chat.id}",
                "chat_type": chat.type.value if hasattr(chat.type, "value") else str(chat.type),
                "username": chat.username or "",
                "members_count": getattr(chat, "members_count", 0),
                "bot_role": "member",
                "is_admin": 0,
            }
            save_group_to_db(group_data)
    except Exception:
        pass
    message.continue_propagation()


# ── Periyodik Arka Plan Görevi ─────────────────────────────────
_sync_task_started = False

async def _periodic_sync_worker(client: Client):
    """Her 6 saatte bir tüm grupları otomatik tarar, 30 saniyede bir heartbeat atar."""
    await asyncio.sleep(10)
    last_full_sync = 0
    while True:
        try:
            update_system_status("bot_heartbeat", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            update_system_status("bot_status", "online")

            now = asyncio.get_event_loop().time()
            if now - last_full_sync > 21600 or last_full_sync == 0:
                await sync_all_groups(client)
                last_full_sync = now

        except Exception as loop_err:
            logger.debug(f"Periyodik senkronizasyon döngü uyarısı: {loop_err}")

        await asyncio.sleep(30)


@Client.on_message(group=50)
async def auto_start_sync_task(client: Client, message: Message):
    """İlk mesaj geldiğinde arka plan senkronizasyon görevini başlatır."""
    global _sync_task_started
    if not _sync_task_started:
        _sync_task_started = True
        asyncio.create_task(_periodic_sync_worker(client))
    message.continue_propagation()


# ══════════════════════════════════════════════════════════════
# 1. MANUEL SENKRONİZASYON KOMUTU (/sync_groups, /panelsenkr)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["panelsenkr", "grupsenkronize", "sync_groups"]))
async def manual_sync_command(client: Client, message: Message):
    """
    /sync_groups veya /panelsenkr:
    Tüm grupları tarayarak Web Admin Paneli veritabanını günceller.
    """
    status_msg = await message.reply_text("🔄 **Grup bilgileri taranıyor ve Web Paneli güncelleniyor...**\n*Lütfen bekleyin...*")
    try:
        total_g, total_m, total_a = await sync_all_groups(client)
        await status_msg.edit_text(
            "✅ **WEB ADMİN PANELİ SENKRONİZASYONU TAMAMLANDI!** 🐲\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 **Taranan Sohbet Sayısı:** `{total_g}` grup/kanal\n"
            f"👥 **Toplam Üye Erişimi:** `{total_m:,}` kişi\n"
            f"🛡️ **Admin Yetkisi Olan:** `{total_a}` grup\n"
            f"🕒 **Son Güncelleme:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 *Web Paneli üzerinden anlık olarak inceleyebilirsiniz.*"
        )
    except Exception as e:
        logger.error(f"Manuel senkronizasyon hatası: {e}")
        await status_msg.edit_text(f"❌ Senkronizasyon sırasında hata oluştu: `{e}`")
