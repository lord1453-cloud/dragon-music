# ============================================
# 🐲 Ejderha Müzik Botu - Kontrol Plugin'i
# ============================================
# /duraklat, /devam ve /gec komutlarını işler.
# Sesli sohbetteki müzik ve video akışını kontrol eder.

import logging
import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.clients import call_client
from bot.theme import (
    msg_paused, msg_resumed, msg_skipped,
    msg_stopped, msg_shuffled, msg_queue_cleared,
    msg_not_playing, msg_error,
    get_panel_text, get_panel_keyboard, get_player_keyboard,
    get_system_stats_text, get_stats_keyboard,
)
from utils.queue_manager import queue
from utils.ytdl import (
    get_audio_file_for_stream,
    get_video_file_for_stream,
    cleanup_old_streams,
)
from bot.plugins.play import make_stream

logger = logging.getLogger(__name__)


# ── İnteraktif Kontrol Paneli Komutları ────────────────────────
@Client.on_message(filters.command(["panel", "kontrol", "cpanel", "dashboard"]))
async def panel_command(client: Client, message: Message):
    """
    /panel veya /kontrol komutu:
    Şu anki yayın durumu, çalan parça ve interaktif butonlarla
    canlı Kontrol Panelini açar.
    """
    chat_id = message.chat.id
    chat_title = message.chat.title or "Özel Sohbet"

    current_track = await queue.get_current(chat_id)
    queue_tracks = await queue.get_queue(chat_id)

    panel_text = get_panel_text(
        chat_title=chat_title,
        current_track=current_track,
        queue_count=len(queue_tracks),
        is_paused=False,
    )

    await message.reply_text(
        text=panel_text,
        reply_markup=get_panel_keyboard(is_paused=False),
    )


# ── Canlı Sistem İstatistikleri Komutu ────────────────────────
@Client.on_message(filters.command(["stats", "istatistik", "durum"]))
async def stats_command(client: Client, message: Message):
    """
    /stats veya /durum komutu:
    RAM, CPU, Uptime ve motor istatistiklerini gösterir.
    """
    stats_text = get_system_stats_text()
    await message.reply_text(
        text=stats_text,
        reply_markup=get_stats_keyboard(),
    )


@Client.on_message(filters.command(["duraklat", "pause", "durdur"]) & filters.group)
async def pause_command(client: Client, message: Message):
    """
    /duraklat, /pause veya /durdur komutu.
    Sesli sohbetteki yayını duraklatır.
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
    Duraklatılmış yayını kaldığı yerden devam ettirir.
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
    Çalan şarkıyı/videoyu atlayıp kuyruktaki sıradakine geçer.
    """
    chat_id = message.chat.id

    if not await queue.has_current(chat_id):
        await message.reply_text(msg_not_playing())
        return

    next_track = await queue.next(chat_id)

    if next_track:
        is_video = next_track.get("stream_type") == "video"
        try:
            if is_video:
                file_path = await get_video_file_for_stream(next_track["url"])
            else:
                file_path = await get_audio_file_for_stream(next_track["url"], title=next_track.get("title"))

            if not file_path:
                await message.reply_text(msg_error("Sıradaki medya dosyası indirilemedi."))
                return

            await call_client.change_stream(
                chat_id,
                make_stream(file_path, is_video=is_video),
            )
            await message.reply_text(msg_skipped(next_track["title"], is_video=is_video))

            asyncio.create_task(cleanup_old_streams(keep_path=file_path))

            tracks = await queue.get_queue(chat_id)
            if tracks:
                preload_track = tracks[0]
                preload_video = preload_track.get("stream_type") == "video"
                if preload_video:
                    asyncio.create_task(get_video_file_for_stream(preload_track["url"]))
                else:
                    asyncio.create_task(get_audio_file_for_stream(preload_track["url"], title=preload_track.get("title")))

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
    Yayını tamamen durdurur, kuyruğu temizler ve sesli sohbetten ayrılır.
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
    Kuyruktaki sıradaki parçaları rastgele karıştırır.
    """
    chat_id = message.chat.id

    success = await queue.shuffle(chat_id)
    if success:
        await message.reply_text(msg_shuffled())
    else:
        tracks = await queue.get_queue(chat_id)
        if len(tracks) <= 1:
            await message.reply_text(msg_error("Karıştırmak için kuyrukta en az 2 parça olmalıdır."))
        else:
            await message.reply_text(msg_not_playing())


@Client.on_message(filters.command(["temizle", "clear", "sirasifirla"]) & filters.group)
async def clear_command(client: Client, message: Message):
    """
    /temizle, /clear veya /sirasifirla komutu.
    Şu an çalan parçayı bozmadan bekleyen kuyruğu temizler.
    """
    chat_id = message.chat.id

    success = await queue.clear_queue_only(chat_id)
    if success:
        await message.reply_text(msg_queue_cleared())
    else:
        await message.reply_text(msg_error("Temizlenecek bekleyen parça yok."))
