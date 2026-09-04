# ============================================
# 🐲 Ejderha Müzik Botu - Otomatik Filtre Sistemi
# ============================================
# Gruplara özel otomatik cevap (filter) ekleme,
# listeleme, silme ve tetikleyici yanıt sistemini yönetir.

import os
import json
import logging
import re
from typing import Optional, Dict

from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus, ChatType

from utils.decorators import clean_command

logger = logging.getLogger(__name__)

from utils.db import (
    get_chat_filters,
    save_chat_filter,
    delete_chat_filter,
    clear_all_chat_filters,
)



async def _is_admin(client: Client, message: Message) -> bool:
    """Komutu kullanan kişinin grupta yönetici olup olmadığını doğrular."""
    if message.chat.type == ChatType.PRIVATE:
        return True
    try:
        if not message.from_user:
            return False
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except Exception as e:
        logger.debug(f"Admin kontrolü uyarısı: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# 1. FİLTRE EKLEME KOMUTU (/filtre)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["filtre", "filtreekle"]) & filters.group)
async def add_filter_command(client: Client, message: Message):
    """
    /filtre <tetikleyici> <yanıt> veya bir mesaja yanıtlayarak /filtre <tetikleyici>
    Grup içinde tetikleyici kelime yazıldığında botun otomatik vereceği cevabı kaydeder.
    """
    if not await _is_admin(client, message):
        await message.reply_text("❌ Filtre ekleme yetkisi yalnızca grup yöneticilerine aittir!")
        return

    args = message.command[1:]

    # Listeleme isteği geldiyse (/filtre liste)
    if args and args[0].lower() in ["liste", "list"]:
        await list_filters_command(client, message)
        return

    keyword = None
    reply_text = None

    # Durum 1: Bir mesaja yanıtlayarak filtre ekleme
    if message.reply_to_message:
        if len(args) < 1:
            await message.reply_text(
                "ℹ️ **Kullanım:** Bir mesajı yanıtlayarak `/filtre <tetikleyici>` yazın."
            )
            return
        keyword = args[0].lower().strip()
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        if not reply_text:
            await message.reply_text("❌ Yanıtlanan mesaj metin veya başlık içermelidir!")
            return

    # Durum 2: Doğrudan komutla metin ekleme (/filtre <kelime> <yanıt>)
    else:
        if len(args) < 2:
            await message.reply_text(
                "⚙️ **FİLTRE EKLEME KULLANIMI**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 `/filtre <tetikleyici> <cevap>`\n\n"
                "**Örnekler:**\n"
                "• `/filtre sa Aleyküm Selam, hoş geldin! 🐲👋`\n"
                "• `/filtre kurallar Grup kurallarımız: Saygılı olun.`"
            )
            return
        keyword = args[0].lower().strip()
        reply_text = " ".join(args[1:]).strip()

    if not keyword or not reply_text:
        await message.reply_text("❌ Tetikleyici veya cevap boş olamaz!")
        return

    await save_chat_filter(message.chat.id, keyword, reply_text)
    await message.reply_text(
        f"✅ **Filtre Başarıyla Kaydedildi!**\n\n"
        f"🎯 **Tetikleyici:** `{keyword}`\n"
        f"💬 **Cevap:** {reply_text}"
    )


# ══════════════════════════════════════════════════════════════
# 2. FİLTRE SİLME KOMUTU (/filtresil)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["filtresil", "durdurfiltre"]) & filters.group)
async def stop_filter_command(client: Client, message: Message):
    """
    /filtresil <tetikleyici>
    Kayıtlı bir filtreyi gruptan kaldırır.
    """
    if not await _is_admin(client, message):
        await message.reply_text("❌ Filtre silme yetkisi yalnızca grup yöneticilerine aittir!")
        return

    if len(message.command) < 2:
        await message.reply_text("ℹ️ **Kullanım:** `/filtresil <silinecek_tetikleyici>`\nÖrnek: `/filtresil sa`")
        return

    keyword = message.command[1].lower().strip()
    success = await delete_chat_filter(message.chat.id, keyword)

    if success:
        await message.reply_text(f"🗑️ `{keyword}` filtresi başarıyla silindi.")
    else:
        await message.reply_text(f"❌ Bu grupta `{keyword}` adında aktif bir filtre bulunamadı.")


# ══════════════════════════════════════════════════════════════
# 3. TÜM FİLTRELERİ SİLME KOMUTU (/tümünüsil, /tumunusil)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["tümünüsil", "tumunusil", "tumfiltrelerisil"]) & filters.group)
async def stop_all_filters_command(client: Client, message: Message):
    """
    /tümünüsil komutu:
    Gruptaki tüm filtreleri tek seferde temizler.
    """
    if not await _is_admin(client, message):
        await message.reply_text("❌ Bu komutu yalnızca grup yöneticileri kullanabilir!")
        return

    success = await clear_all_chat_filters(message.chat.id)
    if success:
        await message.reply_text("🧹 Gruptaki tüm özel filtreler başarıyla temizlendi.")
    else:
        await message.reply_text("ℹ️ Grupta silinecek herhangi bir filtre bulunamadı.")


# ══════════════════════════════════════════════════════════════
# 4. FİLTRELERİ LİSTELEME KOMUTU (/filtreler)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["filtreler"]) & filters.group)
async def list_filters_command(client: Client, message: Message):
    """
    /filtreler komutu:
    Grupta kayıtlı olan tüm filtreleri listeler.
    """
    chat_filters = await get_chat_filters(message.chat.id)

    if not chat_filters:
        await message.reply_text(
            "⚙️ **GRUP ÖZEL FİLTRELERİ** ⚙️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Bu grupta henüz eklenmiş bir filtre bulunmuyor.\n\n"
            "➕ **Filtre Eklemek İçin:**\n"
            "`/filtre <tetikleyici> <cevap>`"
        )
        return

    filter_lines = []
    for idx, (kw, reply) in enumerate(chat_filters.items(), start=1):
        preview = reply[:35] + ("..." if len(reply) > 35 else "")
        filter_lines.append(f"`{idx}.` **{kw}** ➔ *{preview}*")

    text = (
        f"⚙️ **GRUP ÖZEL FİLTRELERİ ({len(chat_filters)})** ⚙️\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(filter_lines) +
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"➕ **Ekle:** `/filter <kelime> <yanıt>`\n"
        f"➖ **Sil:** `/stop <kelime>`"
    )

    await message.reply_text(text)


# ══════════════════════════════════════════════════════════════
# 5. OTOMATİK CEVAP DİNLEYİCİSİ (Filter Trigger Engine)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.group & ~filters.bot & ~filters.via_bot, group=15)
async def filter_trigger_handler(client: Client, message: Message):
    """
    Grupta yazılan her mesajı kontrol eder.
    Kayıtlı filtre tetikleyicisiyle eşleşirse otomatik yanıt verir.
    - group=15 ile çalışır, diğer eklentileri engellemez.
    """
    try:
        text = (message.text or message.caption or "").strip()
        if not text:
            message.continue_propagation()
            return

        # Komutları tetikleyici olarak işleme
        if text.startswith(("/", "!", ".")):
            message.continue_propagation()
            return

        chat_id = message.chat.id
        chat_filters = await get_chat_filters(chat_id)
        if not chat_filters:
            message.continue_propagation()
            return

        normalized_text = text.lower().strip()
        words = set(re.findall(r"\b\w+\b", normalized_text))

        # 1. Tam eşleşme veya kelime bazlı eşleşme
        matched_reply = None
        for keyword, reply_text in chat_filters.items():
            # Tam metin eşleşmesi veya cümlenin içinde tam kelime eşleşmesi
            if keyword == normalized_text or keyword in words or f" {keyword} " in f" {normalized_text} ":
                matched_reply = reply_text
                break

        if matched_reply:
            await message.reply_text(matched_reply)

    except Exception as e:
        logger.debug(f"Filtre tetikleme hatası: {e}")

    message.continue_propagation()
