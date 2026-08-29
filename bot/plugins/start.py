# ============================================
# 🐲 Ejderha Müzik Botu - Start & Menü Plugin'i
# ============================================
# /start ve /menu komutlarını işler.
# Ejderha temalı karşılama mesajı ve inline keyboard menüsü gösterir.

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.theme import WELCOME_TEXT, get_main_menu_keyboard


@Client.on_message(filters.command(["start", "menu"]) & filters.group)
async def start_command(client: Client, message: Message):
    """
    /start veya /menu komutu geldiğinde ejderha temalı
    karşılama mesajını inline butonlarla birlikte gönderir.
    Grup sohbetlerinde çalışır.
    """
    try:
        await message.reply_text(
            text=WELCOME_TEXT,
            reply_markup=get_main_menu_keyboard(),
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"start_command hatası: {e}", exc_info=True)


@Client.on_message(filters.command(["start", "menu"]) & filters.private)
async def start_private_command(client: Client, message: Message):
    """
    Özel mesajda /start veya /menu komutu geldiğinde
    karşılama mesajını gönderir.
    """
    try:
        await message.reply_text(
            text=WELCOME_TEXT,
            reply_markup=get_main_menu_keyboard(),
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"start_private_command hatası: {e}", exc_info=True)
