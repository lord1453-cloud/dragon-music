# ============================================
# 🐲 Ejderha Müzik Botu - Callback Plugin'i
# ============================================
# Inline buton tıklamalarını yakalar ve menü mesajını günceller.
# Her buton tıklamasında ilgili alt menü gösterilir.

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from bot.theme import (
    WELCOME_TEXT, COMMANDS_TEXT, DOWNLOAD_HELP_TEXT,
    SETTINGS_TEXT, DEVELOPER_TEXT,
    get_main_menu_keyboard, get_back_button,
)


@Client.on_callback_query(filters.regex(r"^menu_"))
async def menu_callback(client: Client, callback: CallbackQuery):
    """
    Menü butonlarına tıklandığında çağrılır.
    callback_data değerine göre mesajı günceller.
    """
    data = callback.data

    if data == "menu_main":
        # Ana menüye dön
        await callback.message.edit_text(
            text=WELCOME_TEXT,
            reply_markup=get_main_menu_keyboard(),
        )

    elif data == "menu_commands":
        # Komutlar alt menüsü
        await callback.message.edit_text(
            text=COMMANDS_TEXT,
            reply_markup=get_back_button(),
        )

    elif data == "menu_download":
        # İndirme rehberi alt menüsü
        await callback.message.edit_text(
            text=DOWNLOAD_HELP_TEXT,
            reply_markup=get_back_button(),
        )

    elif data == "menu_settings":
        # Ayarlar alt menüsü
        await callback.message.edit_text(
            text=SETTINGS_TEXT,
            reply_markup=get_back_button(),
        )

    elif data == "menu_developer":
        # Geliştirici alt menüsü
        await callback.message.edit_text(
            text=DEVELOPER_TEXT,
            reply_markup=get_back_button(),
        )

    # Callback'i yanıtla (Telegram'da loading simgesini kaldırır)
    await callback.answer()
