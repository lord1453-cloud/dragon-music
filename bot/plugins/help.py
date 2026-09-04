# ============================================
# 🐲 Ejderha Müzik Botu - Yardım & Komutlar Plugin'i
# ============================================
# /komutlar, /yardim, /help, /gif, /kedi, /kopek komutlarını yönetir.
# BotFather komut listesiyle tam uyumlu çalışır.

import random
import logging
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

from bot.theme import (
    COMMANDS_TEXT,
    get_help_keyboard,
    msg_usage,
)
from bot.config import ADMIN_IDS
from utils.decorators import clean_command, get_user_id

logger = logging.getLogger(__name__)

# ── Sevimli Hayvan & Eğlence GIF Havuzları ─────────────────────
CAT_GIFS = [
    "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif",
    "https://media.giphy.com/media/mlvseq9yvZhba/giphy.gif",
    "https://media.giphy.com/media/BzyTuYCmvSORqs1ABM/giphy.gif",
    "https://media.giphy.com/media/13CoXDiaCcCoyk/giphy.gif",
    "https://media.giphy.com/media/yFQ0ywscgobJK/giphy.gif",
]

DOG_GIFS = [
    "https://media.giphy.com/media/4Zo41lhzKt6iZ8xff9/giphy.gif",
    "https://media.giphy.com/media/bbshzgyFQDqPHXBo4c/giphy.gif",
    "https://media.giphy.com/media/mCRJDo24UvJMA/giphy.gif",
    "https://media.giphy.com/media/3o7abAHdYvZdBNnGZq/giphy.gif",
    "https://media.giphy.com/media/5ndfNkziqIZM1FlQsc/giphy.gif",
]

GENERAL_GIFS = [
    "https://media.giphy.com/media/blSTtZehjAZ8I/giphy.gif",
    "https://media.giphy.com/media/artj92V8o75VPL7AeQ/giphy.gif",
    "https://media.giphy.com/media/l41JGlwa1xY7Btxfs/giphy.gif",
    "https://media.giphy.com/media/10JhviFuU2gWD6/giphy.gif",
    "https://media.giphy.com/media/3oriO04qxVReM5rJEA/giphy.gif",
]


# ── 1. /yardım, /komutlar Komutu ──────────────────────────────

@Client.on_message(clean_command(["yardım", "yardim", "komutlar"]))
async def komutlar_command(client: Client, message: Message):
    """
    /yardım veya /komutlar:
    Tüm bot komutlarını ve açıklamalarını kategorili olarak listeler.
    """
    user_id = get_user_id(message)
    is_admin = bool(ADMIN_IDS and user_id in ADMIN_IDS)

    try:
        await message.reply_text(
            text=COMMANDS_TEXT,
            reply_markup=get_help_keyboard(is_admin=is_admin),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning(f"Markdown ile komut listesi gönderilemedi ({e}), düz metin deneniyor...")
        await message.reply_text(
            text=COMMANDS_TEXT,
            reply_markup=get_help_keyboard(is_admin=is_admin),
            parse_mode=ParseMode.DISABLED,
        )


yardim_command = komutlar_command


# ── 2. /kedi Komutu (Rastgele Kedi GIF'i) ──────────────────────

@Client.on_message(clean_command(["kedi"]))
async def kedi_command(client: Client, message: Message):
    """/kedi komutu: Rastgele sevimli bir kedi animasyonu gönderir."""
    gif_url = random.choice(CAT_GIFS)
    caption = "🐱 **Mırmır Kedi:** *Pisi pisi! Gününü neşeyle doldurmaya geldim!* 🐾✨"
    try:
        await message.reply_animation(animation=gif_url, caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── 3. /köpek Komutu (Rastgele Köpek GIF'i) ────────────────────

@Client.on_message(clean_command(["köpek", "kopek"]))
async def kopek_command(client: Client, message: Message):
    """/köpek veya /kopek komutu: Rastgele neşeli bir köpek animasyonu gönderir."""
    gif_url = random.choice(DOG_GIFS)
    caption = "🐶 **Neşeli Dost:** *Hav hav! Ejderhanın en sadık dostundan selamlar!* 🦴❤️"
    try:
        await message.reply_animation(animation=gif_url, caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── 4. /gif Komutu (GIF Gönderme) ──────────────────────────────

@Client.on_message(clean_command("gif"))
async def gif_command(client: Client, message: Message):
    """/gif [konu] komutu: Eğlenceli bir animasyon gönderir."""
    query = " ".join(message.command[1:]).strip() if len(message.command) > 1 else ""
    gif_url = random.choice(GENERAL_GIFS)

    if query:
        caption = f"🎬 **GIF:** `{query}` temalı ejderha animasyonu! ✨"
    else:
        caption = "🎬 **Ejderha GIF:** *Ateşli ve ritimli bir animasyon!* 🔥"

    try:
        await message.reply_animation(animation=gif_url, caption=caption)
    except Exception:
        await message.reply_text(caption)
