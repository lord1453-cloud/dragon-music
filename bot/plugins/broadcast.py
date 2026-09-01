# ============================================
# 🐲 Ejderha Müzik Botu - Toplu Duyuru (Broadcast)
# ============================================
# Botun üye olduğu tüm gruplara tek seferde mesaj,
# medya, fotoğraf, video veya butonlu duyuru gönderir.
# FloodWait koruması ve detaylı raporlama içerir.

import os
import time
import asyncio
import logging
import sqlite3
from typing import List

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait,
    ChatWriteForbidden,
    UserBannedInChannel,
    ChatAdminRequired,
    ChannelPrivate,
    PeerIdInvalid,
    RPCError,
)
from pyrogram.enums import ChatType

from bot.config import OWNER_ID, BOT_TOKEN
from bot.plugins.group_sync import DB_PATH, init_panel_db

logger = logging.getLogger(__name__)


def _get_target_chat_ids() -> List[int]:
    """Veritabanındaki kayıtlı tüm grup ve kanal ID'lerini çeker."""
    init_panel_db()
    chat_ids = []
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute("SELECT chat_id FROM groups").fetchall()
            conn.close()
            chat_ids = [r[0] for r in rows]
    except Exception as e:
        logger.error(f"Grup ID'leri veritabanından alınamadı: {e}")
    return chat_ids


async def _is_authorized(client: Client, message: Message) -> bool:
    """Yalnızca bot sahibinin veya yetkilendirilmiş yöneticinin duyuru yapmasını sağlar."""
    user = message.from_user
    if not user:
        return False

    # 1. OWNER_ID tanımlıysa kontrol et
    if OWNER_ID and user.id == OWNER_ID:
        return True

    # 2. Varsayılan olarak özel mesajda veya bot sahibiyse izin ver
    # Eğer OWNER_ID henüz girilmediyse komutu kullanan ilk kişiye uyararak izin verebiliriz
    if not OWNER_ID:
        return True

    return False


# ══════════════════════════════════════════════════════════════
# TOPLU DUYURU KOMUTU (/broadcast, /duyuru, /gcast)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["broadcast", "duyuru", "gcast", "toplumesaj"]))
async def broadcast_command(client: Client, message: Message):
    """
    /broadcast <mesaj> veya bir mesaja yanıtlayarak /broadcast:
    Botun bulunduğu tüm gruplara duyuruyu güvenli şekilde iletir.
    """
    if not await _is_authorized(client, message):
        await message.reply_text("❌ Bu komutu yalnızca bot kurucusu kullanabilir!")
        return

    # Gönderilecek içeriği belirle
    has_reply = message.reply_to_message is not None
    broadcast_text = " ".join(message.command[1:]).strip() if len(message.command) > 1 else None

    if not has_reply and not broadcast_text:
        await message.reply_text(
            "📢 **TOPLU DUYURU KULLANIMI**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 **Yöntem 1 (Metin):**\n"
            "`/broadcast Sayın üyeler, yeni özellikler eklendi! 🐲🔥`\n\n"
            "👉 **Yöntem 2 (Fotoğraf/Medya/Butonlu Mesaj):**\n"
            "İletmek istediğiniz mesaja/fotoğrafa yanıt olarak `/broadcast` yazın."
        )
        return

    # Hedef grupları çek
    target_chats = _get_target_chat_ids()

    # Eğer veritabanı henüz boşsa dialoglardan çek
    if not target_chats:
        status_init = await message.reply_text("🔍 Kayıtlı grup aranıyor...")
        try:
            async for dialog in client.get_dialogs():
                if dialog.chat and dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                    if dialog.chat.id not in target_chats:
                        target_chats.append(dialog.chat.id)
            await status_init.delete()
        except Exception:
            pass

    if not target_chats:
        await message.reply_text("❌ Botun üye olduğu herhangi bir grup bulunamadı! Önce `/sync_groups` ile tarama yapın.")
        return

    start_time = time.time()
    total_targets = len(target_chats)
    success_count = 0
    failed_count = 0

    progress_msg = await message.reply_text(
        f"📢 **TOPLU DUYURU BAŞLATILDI...**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 **Hedef Grup Sayısı:** `{total_targets}`\n"
        f"⏳ Gönderiliyor: `[ 0 / {total_targets} ]`"
    )

    for idx, chat_id in enumerate(target_chats, start=1):
        try:
            # 1. Yanıtlanan bir mesaj varsa (Fotoğraf, Medya, Buton, vb. kopyala)
            if has_reply:
                await message.reply_to_message.copy(chat_id)
            # 2. Düz metin varsa
            else:
                formatted_announcement = (
                    f"🐲 **EJDERHA RESMİ DUYURU** 🐲\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{broadcast_text}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                await client.send_message(chat_id, formatted_announcement)

            success_count += 1

        except FloodWait as e:
            logger.warning(f"FloodWait: {e.value} saniye bekleniyor...")
            await asyncio.sleep(e.value + 1)
            try:
                if has_reply:
                    await message.reply_to_message.copy(chat_id)
                else:
                    await client.send_message(chat_id, formatted_announcement)
                success_count += 1
            except Exception:
                failed_count += 1

        except (ChatWriteForbidden, UserBannedInChannel, ChatAdminRequired, ChannelPrivate, PeerIdInvalid):
            # Botun gruptan atıldığı veya yazma izninin olmadığı durumlar
            failed_count += 1

        except RPCError as rpc_err:
            logger.debug(f"Duyuru gönderilemedi ({chat_id}): {rpc_err}")
            failed_count += 1

        except Exception as e:
            logger.debug(f"Beklenmeyen hata ({chat_id}): {e}")
            failed_count += 1

        # Her 5 grupta bir ilerleme çubuğunu güncelle
        if idx % 5 == 0 or idx == total_targets:
            try:
                await progress_msg.edit_text(
                    f"📢 **TOPLU DUYURU GÖNDERİLİYOR...**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📍 **Toplam Hedef:** `{total_targets}`\n"
                    f"✅ **Başarılı:** `{success_count}`\n"
                    f"❌ **Başarısız:** `{failed_count}`\n"
                    f"⏳ **İlerleme:** `[ {idx} / {total_targets} ]`"
                )
            except Exception:
                pass

        # Telegram hız sınırlarına takılmamak için aralık
        await asyncio.sleep(0.15)

    elapsed_time = round(time.time() - start_time, 1)

    final_report = (
        f"🎉 **TOPLU DUYURU TAMAMLANDI!** 🐲\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 **Toplam Hedef Grup:** `{total_targets}`\n"
        f"✅ **Başarıyla İletilen:** `{success_count}` grup\n"
        f"❌ **İletilemeyen / Engelli:** `{failed_count}` grup\n"
        f"⏱️ **Toplam Süre:** `{elapsed_time}` saniye\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ *Duyurunuz tüm gruplara ejderhanın nefesiyle ulaştırıldı!*"
    )

    await progress_msg.edit_text(final_report)
