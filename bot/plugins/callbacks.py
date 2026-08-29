# ============================================
# 🐲 Ejderha Müzik Botu - Callback Plugin'i
# ============================================
# Inline buton tıklamalarını yakalar ve menü mesajını günceller.
# Her buton tıklamasında ilgili alt menü gösterilir.

import logging

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from pyrogram.enums import ParseMode

from bot.theme import (
    WELCOME_TEXT, COMMANDS_TEXT, DOWNLOAD_HELP_TEXT,
    SETTINGS_TEXT, DEVELOPER_TEXT,
    get_main_menu_keyboard, get_back_button,
)

logger = logging.getLogger(__name__)


async def _safe_edit_text(callback: CallbackQuery, text: str, reply_markup):
    """Markdown destekli güvenli mesaj güncelleme (hata durumunda düz metne düşer)."""
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning(f"Markdown ile edit başarısız, düz metin deneniyor: {e}")
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.DISABLED,
            )
        except Exception as e2:
            logger.error(f"Callback edit_text hatası: {e2}")


@Client.on_callback_query(filters.regex(r"^menu_"))
async def menu_callback(client: Client, callback: CallbackQuery):
    """
    Menü butonlarına tıklandığında çağrılır.
    callback_data değerine göre mesajı günceller.
    """
    data = callback.data
    logger.info(f"🔘 Callback tıklandı: {data} - Kullanıcı: {callback.from_user.id if callback.from_user else '?'}")

    try:
        if data == "menu_main":
            # Ana menüye dön
            await _safe_edit_text(
                callback,
                text=WELCOME_TEXT,
                reply_markup=get_main_menu_keyboard(),
            )

        elif data == "menu_commands":
            # Komutlar alt menüsü
            await _safe_edit_text(
                callback,
                text=COMMANDS_TEXT,
                reply_markup=get_back_button(),
            )

        elif data == "menu_download":
            # İndirme rehberi alt menüsü
            await _safe_edit_text(
                callback,
                text=DOWNLOAD_HELP_TEXT,
                reply_markup=get_back_button(),
            )

        elif data == "menu_settings":
            # Ayarlar alt menüsü
            await _safe_edit_text(
                callback,
                text=SETTINGS_TEXT,
                reply_markup=get_back_button(),
            )

        elif data == "menu_developer":
            # Geliştirici alt menüsü
            await _safe_edit_text(
                callback,
                text=DEVELOPER_TEXT,
                reply_markup=get_back_button(),
            )
    except Exception as e:
        logger.error(f"menu_callback işleme hatası: {e}", exc_info=True)
    finally:
        # Callback'i her zaman yanıtla (loading animasyonunu kaldırır)
        try:
            await callback.answer()
        except Exception:
            pass
