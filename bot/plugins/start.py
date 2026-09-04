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
    get_main_menu_keyboard, get_back_button, get_dev_keyboard,
)

from bot.config import ADMIN_IDS
from bot.theme import (
    WELCOME_TEXT, SETTINGS_TEXT, COMMANDS_TEXT, DEVELOPER_TEXT,
    get_main_menu_keyboard, get_back_button, get_dev_keyboard, get_help_keyboard,
)
from utils.decorators import clean_command, get_user_display_name, get_user_id

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


# ── /başla, /start ve /menu Komutları ─────────────────────────
@Client.on_message(clean_command(["başla", "basla", "start", "menu"]))
async def start_command(client: Client, message: Message):
    """
    /başla veya /menu komutu:
    Ejderha temalı ana menüyü inline butonlarla birlikte gönderir.
    Hem DM hem de gruplarda çalışır (@mention destekler).
    """
    chat_type = "DM" if message.chat.type.value == "private" else "Grup"
    user_display = get_user_display_name(message)
    user_id = get_user_id(message)
    logger.info(f"📥 /başla komutu alındı [{chat_type}: {message.chat.id}, Kullanıcı: {user_display} ({user_id})]")

    await _safe_reply(
        message,
        text=WELCOME_TEXT,
        reply_markup=get_main_menu_keyboard(),
    )


basla_command = start_command


# ── /ayarlar, /ayar Komutları ─────────────────────────────────
@Client.on_message(clean_command(["ayarlar", "ayar"]))
async def settings_command(client: Client, message: Message):
    """
    /ayarlar komutu:
    Bot ve ses motoru ayarlarını gösterir.
    """
    chat_type = "DM" if message.chat.type.value == "private" else "Grup"
    user_display = get_user_display_name(message)
    user_id = get_user_id(message)
    logger.info(f"📥 /ayarlar komutu alındı [{chat_type}: {message.chat.id}, Kullanıcı: {user_display} ({user_id})]")

    await _safe_reply(
        message,
        text=SETTINGS_TEXT,
        reply_markup=get_back_button(),
    )


# ── /yardım, /komutlar (bot/plugins/help.py üzerinden yönetilir) ──
from bot.plugins.help import komutlar_command as help_command


# ── /gelistirici, /bilgi Komutları ────────────────────────────
@Client.on_message(clean_command(["gelistirici", "bilgi"]))
async def dev_command(client: Client, message: Message):
    """
    /gelistirici veya /bilgi komutu:
    Geliştirici bilgilerini gösterir.
    """
    await _safe_reply(
        message,
        text=DEVELOPER_TEXT,
        reply_markup=get_dev_keyboard(),
    )


# ── Teşhis & Güvenli Loglama ─────────────────────────────────
@Client.on_message(group=99)
async def debug_all_messages(client: Client, message: Message):
    """
    Boş mesajları (servis mesajları, silinmişler, boş caption) filtreler,
    yalnızca dolu mesajları loglar. Kullanıcı '?' sorununu çözer.
    """
    # 1. & 2. text ve caption boş mu kontrol et
    raw_text = message.text or message.caption
    # 3. İkisi de boşsa loglamadan ve işlemeden çık
    if not raw_text or not raw_text.strip():
        message.continue_propagation()
        return

    chat_type = message.chat.type if message.chat else "?"
    clean_snippet = raw_text.strip()[:50]
    user_info = get_user_display_name(message)
    user_id = get_user_id(message)

    logger.debug(
        f"🔍 Mesaj: Chat: {message.chat.id} ({chat_type}), "
        f"Gönderen: {user_info} [{user_id}], "
        f"Metin: '{clean_snippet}'"
    )
    message.continue_propagation()
