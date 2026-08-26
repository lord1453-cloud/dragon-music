# ============================================
# 🐲 Ejderha Müzik Botu - Kontrol Plugin'i
# ============================================
# /duraklat, /devam ve /gec komutlarını işler.
# Sesli sohbetteki müzik akışını kontrol eder.
#
# PÜRÜZSÜZ AKIŞ VE BUFFER OPTİMİZASYONU (PyTgCalls v1.2.9):
# - MediaStream ve AudioPiped desteği
# - FFmpeg '-re' parametresi ile gerçek zamanlı (1.0x) sabit hızda ses akışı
# - thread_queue_size 8192 ile genişletilmiş tampon (buffer)

import os
import logging
import asyncio
import glob

from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls.types import MediaStream, AudioQuality

from bot.clients import call_client
from bot.config import DOWNLOADS_DIR
from bot.theme import (
    msg_paused, msg_resumed, msg_skipped,
    msg_stopped, msg_shuffled, msg_queue_cleared,
    msg_not_playing, msg_error,
)
from utils.queue_manager import queue
from utils.ytdl import get_audio_file_for_stream, cleanup_old_streams

logger = logging.getLogger(__name__)

# ── play.py ile aynı pürüzsüz akış parametreleri ─────────────
SMOOTH_STREAM_FFMPEG = (
    "-re "                             # Gerçek zamanlı akış hızı (1.0x playback rate)
    "-analyzeduration 1000000 "        # 1 saniyelik hızlı format tespiti
    "-probesize 1000000 "               # 1MB probe boyutu
    "-thread_queue_size 8192 "          # 8192 thread buffer kuyruğu (pipe underrun önler)
)


def _make_audio_stream(file_path: str) -> MediaStream:
    """Takılmasız ve kararlı ses akışı nesnesi oluşturur. (PyTgCalls v1.2.9 uyumlu)"""
    return MediaStream(
        file_path,
        audio_parameters=AudioQuality.HIGH,
        video_flags=MediaStream.IGNORE,
        ffmpeg_parameters=SMOOTH_STREAM_FFMPEG,
    )


@Client.on_message(filters.command(["duraklat", "pause", "durdur"]) & filters.group)
async def pause_command(client: Client, message: Message):
    """
    /duraklat, /pause veya /durdur komutu.
    Sesli sohbetteki müziği duraklatır.
    """
    chat_id = message.chat.id

    if not await queue.has_current(chat_id):
        await message.reply_text(msg_not_playing())
        return

    try:
        await call_client.pause_stream(chat_id)
        await message.reply_text(msg_paused())
    except Exception as e:
        logger.error(f"Duraklatma hatası: {e}")
        await message.reply_text(msg_error(str(e)))


@Client.on_message(filters.command(["devam", "resume", "baslat"]) & filters.group)
async def resume_command(client: Client, message: Message):
    """
    /devam, /resume veya /baslat komutu.
    Duraklatılmış müziği kaldığı yerden devam ettirir.
    """
    chat_id = message.chat.id

    if not await queue.has_current(chat_id):
        await message.reply_text(msg_not_playing())
        return

    try:
        await call_client.resume_stream(chat_id)
        await message.reply_text(msg_resumed())
    except Exception as e:
        logger.error(f"Devam ettirme hatası: {e}")
        await message.reply_text(msg_error(str(e)))


@Client.on_message(filters.command(["gec", "atla", "skip", "next"]) & filters.group)
async def skip_command(client: Client, message: Message):
    """
    /gec, /atla, /skip veya /next komutu.
    Çalan şarkıyı atlayıp kuyruktaki sıradakine geçer.
    """
    chat_id = message.chat.id

    if not await queue.has_current(chat_id):
        await message.reply_text(msg_not_playing())
        return

    next_track = await queue.next(chat_id)

    if next_track:
        try:
            file_path = await get_audio_file_for_stream(next_track["url"])
            if not file_path:
                await message.reply_text(msg_error("Sıradaki şarkı indirilemedi."))
                return

            await call_client.change_stream(
                chat_id,
                _make_audio_stream(file_path),
            )
            await message.reply_text(msg_skipped(next_track["title"]))

            asyncio.create_task(cleanup_old_streams(keep_path=file_path))

            tracks = await queue.get_queue(chat_id)
            if tracks:
                asyncio.create_task(get_audio_file_for_stream(tracks[0]["url"]))

        except Exception as e:
            logger.error(f"Atlama hatası: {e}")
            await message.reply_text(msg_error(str(e)))
    else:
        try:
            await call_client.leave_group_call(chat_id)
        except Exception:
            pass
        await queue.clear(chat_id)
        await message.reply_text(msg_skipped())

        asyncio.create_task(cleanup_old_streams())


@Client.on_message(filters.command(["bitir", "dur", "son", "stop", "kapat", "leave", "ayril"]) & filters.group)
async def stop_command(client: Client, message: Message):
    """
    /bitir, /dur, /son, /stop, /kapat komutu.
    Müziği tamamen durdurur, kuyruğu temizler ve sesli sohbetten ayrılır.
    """
    chat_id = message.chat.id

    try:
        await call_client.leave_group_call(chat_id)
    except Exception:
        pass

    await queue.clear(chat_id)
    await message.reply_text(msg_stopped())
    asyncio.create_task(cleanup_old_streams())


@Client.on_message(filters.command(["karistir", "shuffle"]) & filters.group)
async def shuffle_command(client: Client, message: Message):
    """
    /karistir veya /shuffle komutu.
    Kuyruktaki sıradaki şarkıları rastgele karıştırır.
    """
    chat_id = message.chat.id

    success = await queue.shuffle(chat_id)
    if success:
        await message.reply_text(msg_shuffled())
    else:
        tracks = await queue.get_queue(chat_id)
        if len(tracks) <= 1:
            await message.reply_text(msg_error("Karıştırmak için kuyrukta en az 2 şarkı olmalıdır."))
        else:
            await message.reply_text(msg_not_playing())


@Client.on_message(filters.command(["temizle", "clear", "sirasifirla"]) & filters.group)
async def clear_command(client: Client, message: Message):
    """
    /temizle, /clear veya /sirasifirla komutu.
    Şu an çalan şarkıyı bozmadan bekleyen kuyruğu temizler.
    """
    chat_id = message.chat.id

    success = await queue.clear_queue_only(chat_id)
    if success:
        await message.reply_text(msg_queue_cleared())
    else:
        await message.reply_text(msg_error("Temizlenecek bekleyen şarkı yok."))


