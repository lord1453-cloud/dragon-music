# ============================================
# 🐲 Ejderha Müzik Botu - Kuyruk Plugin'i
# ============================================
# /sira komutuyla müzik kuyruğunu listeler.

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.theme import msg_queue_list, msg_queue_empty
from utils.queue_manager import queue


@Client.on_message(filters.command("sira") & filters.group)
async def queue_command(client: Client, message: Message):
    """
    /sira komutu.
    Kuyruktaki şarkıları numaralı liste halinde gösterir.
    Çalan parçayı vurgular.
    """
    chat_id = message.chat.id

    # Kuyrukta şarkı var mı kontrol et
    tracks = await queue.get_queue(chat_id)
    current = await queue.current(chat_id)

    if not tracks and not current:
        await message.reply_text(msg_queue_empty())
        return

    # Çalan şarkının başlığını al
    current_title = current["title"] if current else None

    if not tracks:
        # Sadece çalan şarkı var, kuyruk boş
        await message.reply_text(
            msg_queue_list([], current_title)
        )
    else:
        await message.reply_text(
            msg_queue_list(tracks, current_title)
        )
