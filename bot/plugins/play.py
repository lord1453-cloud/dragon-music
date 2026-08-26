# ============================================
# 🐲 Ejderha Müzik Botu - Oynat Plugin'i
# ============================================
# /oynat komutuyla şarkı çalma ve kuyruğa ekleme işlemlerini yönetir.
# YouTube'dan arama yapar, sesli sohbete katılır ve müzik çalar.
#
# PÜRÜZSÜZ AKIŞ VE BUFFER OPTİMİZASYONU (PyTgCalls v1.2.9):
# - MediaStream ve AudioPiped desteği
# - FFmpeg '-re' parametresi ile gerçek zamanlı (1.0x) sabit hızda ses akışı
# - thread_queue_size 8192 ile genişletilmiş tampon (buffer)
# - Ev internetindeki dalgalanmalara karşı maksimum kararlılık

import os
import logging
import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, Update

from bot.clients import bot_client, call_client
from bot.theme import (
    msg_searching, msg_playing, msg_queued,
    msg_error, msg_usage, msg_no_voice_chat,
)
from utils.queue_manager import queue
from utils.ytdl import search_youtube, get_audio_file_for_stream, cleanup_old_streams

logger = logging.getLogger(__name__)


# ── Pürüzsüz ve Kararlı Akış FFmpeg Parametreleri ─────────────
# '-re': Yerel dosyayı gerçek zamanlı (1.0x hızıyla) okuyarak WebRTC
#        paketlerinin düzenli iletilmesini sağlar, takılmayı ve lag'ı bitirir.
# '-thread_queue_size 8192': Yüksek tampon genişliği ile paket düşmesini önler.
SMOOTH_STREAM_FFMPEG = (
    "-re "                             # Gerçek zamanlı akış hızı (1.0x playback rate)
    "-analyzeduration 1000000 "        # 1 saniyelik hızlı format tespiti
    "-probesize 1000000 "               # 1MB probe boyutu
    "-thread_queue_size 8192 "          # 8192 thread buffer kuyruğu (pipe underrun önler)
)


def _make_audio_stream(file_path: str) -> MediaStream:
    """
    Takılmasız, pürüzsüz ve kararlı ses akışı nesnesi oluşturur.
    PyTgCalls v1.2.9 MediaStream standart kullanımı.
    """
    return MediaStream(
        file_path,
        audio_parameters=AudioQuality.HIGH,
        video_flags=MediaStream.IGNORE,
        ffmpeg_parameters=SMOOTH_STREAM_FFMPEG,
    )


async def _prefetch_next(chat_id: int):
    """
    Kuyruktaki sıradaki şarkıyı arka planda indirir.
    Bu sayede şarkı geçişlerinde bekleme süresi azalır.
    """
    try:
        tracks = await queue.get_queue(chat_id)
        if tracks:
            next_url = tracks[0].get("url")
            if next_url:
                asyncio.create_task(get_audio_file_for_stream(next_url))
                logger.info(f"🔥 Sıradaki şarkı arka planda indiriliyor: {tracks[0].get('title', '?')}")
    except Exception:
        pass


async def _play_next(client: Client, chat_id: int, message: Message = None):
    """
    Kuyruktaki sıradaki şarkıyı çalar.
    Kuyruk boşsa sesli sohbetten ayrılır.
    """
    track = await queue.next(chat_id)
    if not track:
        try:
            await call_client.leave_group_call(chat_id)
        except Exception:
            pass
        await queue.clear(chat_id)
        return

    try:
        file_path = await get_audio_file_for_stream(track["url"])
        if not file_path:
            if message:
                await message.reply_text(msg_error("Ses dosyası indirilemedi."))
            else:
                try:
                    await bot_client.send_message(
                        chat_id,
                        msg_error(f"'{track.get('title')}' indirilemedi, sıradaki şarkıya geçiliyor...")
                    )
                except Exception:
                    pass
            await _play_next(client, chat_id, message)
            return

        if os.path.getsize(file_path) < 10000:
            logger.warning(f"Dosya çok küçük: {file_path}")
            try:
                os.remove(file_path)
            except Exception:
                pass
            file_path = await get_audio_file_for_stream(track["url"])
            if not file_path:
                await _play_next(client, chat_id, message)
                return

        await call_client.change_stream(
            chat_id,
            _make_audio_stream(file_path),
        )

        if message:
            await message.reply_text(
                msg_playing(track["title"], track.get("duration_str", ""))
            )
        else:
            try:
                await bot_client.send_message(
                    chat_id,
                    msg_playing(track["title"], track.get("duration_str", ""))
                )
            except Exception:
                pass

        await _prefetch_next(chat_id)
        asyncio.create_task(cleanup_old_streams(keep_path=file_path))

    except Exception as e:
        logger.error(f"Şarkı çalma hatası: {e}")
        if message:
            await message.reply_text(msg_error(str(e)))
        else:
            try:
                await bot_client.send_message(chat_id, msg_error(f"Oynatma hatası: {e}"))
            except Exception:
                pass
        await queue.clear(chat_id)


# ── PyTgCalls Olay Dinleyicileri (Event Handlers) ─────────────

@call_client.on_stream_end()
async def stream_end_handler(client: PyTgCalls, update: Update):
    """
    Şarkı bittiğinde PyTgCalls tarafından tetiklenir.
    Kuyruktaki sıradaki şarkıyı otomatik olarak çalar.
    """
    chat_id = update.chat_id
    logger.info(f"🎵 Stream bitti (chat_id: {chat_id}), sıradaki şarkıya geçiliyor...")
    await _play_next(bot_client, chat_id)


@call_client.on_closed_voice_chat()
@call_client.on_kicked()
@call_client.on_left()
async def stream_closed_handler(client: PyTgCalls, chat_id: int):
    """
    Sesli sohbet kapandığında, bot atıldığında veya ayrıldığında çağrılır.
    O sohbetin kuyruğunu temizler.
    """
    logger.info(f"🛑 Sesli sohbet sonlandı veya bot ayrıldı (chat_id: {chat_id})")
    await queue.clear(chat_id)


@Client.on_message(filters.command(["oynat", "play"]) & filters.group)
async def play_command(client: Client, message: Message):
    """
    /oynat veya /play <şarkı adı veya link> komutu.
    """
    if len(message.command) < 2:
        await message.reply_text(
            msg_usage("/oynat <şarkı adı veya link>", "/oynat Tarkan Şımarık")
        )

        return

    query = " ".join(message.command[1:])
    chat_id = message.chat.id

    status_msg = await message.reply_text(msg_searching(query))

    result = await search_youtube(query)
    if not result:
        await status_msg.edit_text(msg_error("Şarkı bulunamadı!"))
        return

    track = {
        "title": result["title"],
        "url": result["url"],
        "duration": result["duration"],
        "duration_str": result["duration_str"],
        "requester": message.from_user.first_name if message.from_user else "Bilinmeyen",
    }

    is_playing = await queue.has_current(chat_id)

    if is_playing:
        position = await queue.add(chat_id, track)
        await status_msg.edit_text(msg_queued(track["title"], position))

        if position == 1:
            asyncio.create_task(get_audio_file_for_stream(track["url"]))
    else:
        await queue.set_current(chat_id, track)

        try:
            file_path = await get_audio_file_for_stream(result["url"])
            if not file_path:
                await status_msg.edit_text(msg_error("Ses dosyası indirilemedi."))
                await queue.clear(chat_id)
                return

            if os.path.getsize(file_path) < 10000:
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                file_path = await get_audio_file_for_stream(result["url"])
                if not file_path:
                    await status_msg.edit_text(msg_error("Ses dosyası bozuk!"))
                    await queue.clear(chat_id)
                    return

            audio_stream = _make_audio_stream(file_path)

            try:
                await call_client.join_group_call(
                    chat_id,
                    audio_stream,
                )
            except Exception:
                try:
                    await call_client.change_stream(
                        chat_id,
                        _make_audio_stream(file_path),
                    )
                except Exception as e:
                    await status_msg.edit_text(msg_no_voice_chat())
                    await queue.clear(chat_id)
                    return

            await status_msg.edit_text(
                msg_playing(track["title"], track.get("duration_str", ""))
            )
            await _prefetch_next(chat_id)
        except Exception as e:
            logger.error(f"Çalma hatası: {e}")
            await status_msg.edit_text(msg_error(str(e)))
            await queue.clear(chat_id)

