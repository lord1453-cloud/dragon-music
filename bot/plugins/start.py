# ============================================
# 🐲 Ejderha Müzik Botu - Start & Menü Plugin'i
# ============================================
# /start ve /menu komutlarını işler.
# Ejderha temalı karşılama mesajı ve inline keyboard menüsü gösterir.

import logging

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

from bot.theme import WELCOME_TEXT, get_main_menu_keyboard

logger = logging.getLogger(__name__)


@Client.on_message(filters.command(["start", "menu"]) & filters.group)
async def start_command(client: Client, message: Message):
    """
    /start veya /menu komutu geldiğinde ejderha temalı
    karşılama mesajını inline butonlarla birlikte gönderir.
    Grup sohbetlerinde çalışır.
    """
    logger.info(f"📥 /start komutu alındı - Grup: {message.chat.id}, Kullanıcı: {message.from_user.id if message.from_user else 'Bilinmiyor'}")
    try:
        await message.reply_text(
            text=WELCOME_TEXT,
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("✅ start_command yanıtı gönderildi (Grup)")
    except Exception as e:
        logger.error(f"❌ start_command hatası: {e}", exc_info=True)
        # Markdown parse hatası olursa düz metin olarak gönder
        try:
            await message.reply_text(
                text=WELCOME_TEXT,
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.DISABLED,
            )
            logger.info("✅ start_command düz metin olarak gönderildi (Grup)")
        except Exception as e2:
            logger.error(f"❌ start_command fallback hatası: {e2}", exc_info=True)


@Client.on_message(filters.command(["start", "menu"]) & filters.private)
async def start_private_command(client: Client, message: Message):
    """
    Özel mesajda /start veya /menu komutu geldiğinde
    karşılama mesajını gönderir.
    """
    logger.info(f"📥 /start komutu alındı - DM: {message.from_user.id if message.from_user else 'Bilinmiyor'}")
    try:
        await message.reply_text(
            text=WELCOME_TEXT,
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("✅ start_private_command yanıtı gönderildi (DM)")
    except Exception as e:
        logger.error(f"❌ start_private_command hatası: {e}", exc_info=True)
        # Markdown parse hatası olursa düz metin olarak gönder
        try:
            await message.reply_text(
                text=WELCOME_TEXT,
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.DISABLED,
            )
            logger.info("✅ start_private_command düz metin olarak gönderildi (DM)")
        except Exception as e2:
            logger.error(f"❌ start_private_command fallback hatası: {e2}", exc_info=True)


# ── Teşhis: Tüm mesajları logla (DEBUG) ──────────────────────
@Client.on_message(group=99)
async def debug_all_messages(client: Client, message: Message):
    """
    Botun gerçekten mesaj alıp almadığını doğrulamak için
    gelen tüm mesajları loglar. group=99 ile en son çalışır
    ve diğer handler'ları engellemez.
    """
    chat_type = message.chat.type if message.chat else "?"
    text = (message.text or message.caption or "")[:50]
    logger.info(
        f"🔍 [DEBUG] Mesaj alındı - "
        f"Chat: {message.chat.id} ({chat_type}), "
        f"From: {message.from_user.id if message.from_user else '?'}, "
        f"Text: '{text}'"
    )
    message.continue_propagation()
