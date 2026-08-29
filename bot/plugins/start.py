# ============================================
# 🐲 Ejderha Müzik Botu - Start, Menü & Ayarlar Plugin'i
# ============================================
# /start, /menu, /ayarlar, /settings, /yardim, /help
# komutlarını hem özel mesajda (DM) hem de gruplarda işler.

import logging

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

from bot.theme import (
    WELCOME_TEXT, SETTINGS_TEXT, COMMANDS_TEXT, DEVELOPER_TEXT,
    get_main_menu_keyboard, get_back_button,
)

logger = logging.getLogger(__name__)


async def _safe_reply(message: Message, text: str, reply_markup=None):
    """Markdown destekli güvenli mesaj gönderme (hata durumunda düz metne düşer)."""
    try:
        await message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning(f"Markdown ile gönderim başarısız ({e}), düz metin deneniyor...")
        try:
            await message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.DISABLED,
            )
        except Exception as e2:
            logger.error(f"Mesaj gönderme hatası: {e2}", exc_info=True)


# ── /start ve /menu Komutları ─────────────────────────────────
@Client.on_message(filters.command(["start", "menu"]))
async def start_command(client: Client, message: Message):
    """
    /start veya /menu komutu:
    Ejderha temalı ana menüyü inline butonlarla birlikte gönderir.
    Hem DM hem de gruplarda çalışır.
    """
    chat_type = "DM" if message.chat.type.value == "private" else "Grup"
    user_id = message.from_user.id if message.from_user else "?"
    logger.info(f"📥 /start komutu alındı [{chat_type}: {message.chat.id}, Kullanıcı: {user_id}]")

    await _safe_reply(
        message,
        text=WELCOME_TEXT,
        reply_markup=get_main_menu_keyboard(),
    )


# ── /ayarlar, /ayar, /settings Komutları ──────────────────────
@Client.on_message(filters.command(["ayarlar", "ayar", "settings"]))
async def settings_command(client: Client, message: Message):
    """
    /ayarlar veya /settings komutu:
    Bot ve ses motoru ayarlarını gösterir.
    Hem DM hem de gruplarda çalışır.
    """
    chat_type = "DM" if message.chat.type.value == "private" else "Grup"
    user_id = message.from_user.id if message.from_user else "?"
    logger.info(f"📥 /ayarlar komutu alındı [{chat_type}: {message.chat.id}, Kullanıcı: {user_id}]")

    await _safe_reply(
        message,
        text=SETTINGS_TEXT,
        reply_markup=get_back_button(),
    )


# ── /yardim, /help, /komutlar Komutları ───────────────────────
@Client.on_message(filters.command(["yardim", "help", "komutlar", "commands"]))
async def help_command(client: Client, message: Message):
    """
    /yardim veya /help komutu:
    Kullanılabilir tüm bot komutlarını listeler.
    Hem DM hem de gruplarda çalışır.
    """
    chat_type = "DM" if message.chat.type.value == "private" else "Grup"
    user_id = message.from_user.id if message.from_user else "?"
    logger.info(f"📥 /yardim komutu alındı [{chat_type}: {message.chat.id}, Kullanıcı: {user_id}]")

    await _safe_reply(
        message,
        text=COMMANDS_TEXT,
        reply_markup=get_back_button(),
    )


# ── /gelistirici, /developer Komutları ────────────────────────
@Client.on_message(filters.command(["gelistirici", "developer", "dev"]))
async def dev_command(client: Client, message: Message):
    """
    /gelistirici veya /developer komutu:
    Geliştirici bilgilerini gösterir.
    """
    await _safe_reply(
        message,
        text=DEVELOPER_TEXT,
        reply_markup=get_back_button(),
    )


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
