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
    msg_not_playing, msg_error,
)
from utils.queue_manager import queue
from utils.ytdl import get_audio_file_for_stream

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


async def _cleanup_old_streams(keep_path: str = None):
    """
    Eski stream dosyalarını arka planda temizler.
    Bellek ve disk kullanımını düşük tutar.
    """
    def _clean():
        try:
            for f in glob.glob(os.path.join(DOWNLOADS_DIR, "stream_*")):
                if keep_path and os.path.abspath(f) == os.path.abspath(keep_path):
                    continue
                try:
                    os.remove(f)
                except Exception:
                    pass
        except Exception:
            pass

    await asyncio.to_thread(_clean)


@Client.on_message(filters.command("duraklat") & filters.group)
async def pause_command(client: Client, message: Message):
    """
    /duraklat komutu.
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


@Client.on_message(filters.command("devam") & filters.group)
async def resume_command(client: Client, message: Message):
    """
    /devam komutu.
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


@Client.on_message(filters.command("gec") & filters.group)
async def skip_command(client: Client, message: Message):
    """
    /gec komutu.
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

            asyncio.create_task(_cleanup_old_streams(keep_path=file_path))

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

        asyncio.create_task(_cleanup_old_streams())
