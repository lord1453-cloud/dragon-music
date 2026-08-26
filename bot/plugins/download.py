# ============================================
# 🐲 Ejderha Müzik Botu - İndirme Plugin'i
# ============================================
# /indir komutuyla şarkıyı MP3 olarak indirip
# Telegram'a ses dosyası olarak gönderir.

import os
import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.theme import (
    msg_searching, msg_downloading, msg_download_complete,
    msg_error, msg_usage,
)
from utils.ytdl import search_youtube, download_audio

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("indir"))
async def download_command(client: Client, message: Message):
    """
    /indir <şarkı adı veya link> komutu.

    - YouTube'dan şarkı arar
    - En yüksek kalitede MP3 olarak indirir
    - Telegram üzerinden ses dosyası olarak gönderir
    - Hem grup hem özel sohbette çalışır
    """
    # Komut argümanını al
    if len(message.command) < 2:
        await message.reply_text(
            msg_usage("/indir <şarkı adı veya link>", "/indir Tarkan Şımarık")
        )
        return

    query = " ".join(message.command[1:])

    # Arama mesajı gönder
    status_msg = await message.reply_text(msg_searching(query))

    # YouTube'da ara
    result = await search_youtube(query)
    if not result:
        await status_msg.edit_text(msg_error("Şarkı bulunamadı!"))
        return

    # İndirme durumunu güncelle
    await status_msg.edit_text(msg_downloading(result["title"]))

    # Şarkıyı indir
    download_result = await download_audio(query)
    if not download_result or not os.path.exists(download_result["file_path"]):
        await status_msg.edit_text(msg_error("Şarkı indirilemedi!"))
        return

    try:
        # Telegram'a ses dosyası olarak gönder
        await message.reply_audio(
            audio=download_result["file_path"],
            title=download_result["title"],
            caption=msg_download_complete(download_result["title"]),
            duration=download_result.get("duration", 0),
        )

        # Durum mesajını sil (dosya zaten gönderildi)
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Dosya gönderme hatası: {e}")
        await status_msg.edit_text(msg_error(f"Dosya gönderilemedi: {e}"))
    finally:
        # Geçici dosyayı temizle
        try:
            if download_result and os.path.exists(download_result["file_path"]):
                os.remove(download_result["file_path"])
        except Exception:
            pass
