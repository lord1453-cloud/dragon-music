# ============================================
# 🐲 Ejderha Müzik Botu - Video & Ses İndirme Plugin'i
# ============================================
# /video ve /indir komutlarını yönetir.
#
# Özellikler:
# - /video <link/arama>: 720p veya 480p MP4 formatında video indirip Telegram'a gönderir.
# - /indir <link/arama>: 192 kbps veya 128 kbps MP3 ses dosyası indirip gönderir.
# - 50 MB Telegram sınırını aşan dosyalarda bilgilendirici uyarı verir.
# - Gönderim tamamlandıktan sonra geçici dosyaları anında siler ve RAM'i temizler (gc.collect).

import os
import gc
import logging
from typing import Tuple

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.theme import (
    msg_searching,
    msg_downloading,
    msg_download_complete,
    msg_video_downloading,
    msg_video_complete,
    msg_file_too_large,
    msg_error,
    msg_usage,
)
from utils.downloader import (
    download_video,
    download_audio,
    cleanup_file,
)
from utils.decorators import clean_command

logger = logging.getLogger(__name__)


def _parse_video_args(command_parts: list) -> Tuple[str, str]:
    """
    Komut argümanlarından kalite ve arama metnini ayrıştırır.
    Örn: /video 480p Tarkan -> ('480p', 'Tarkan')
         /video Tarkan -> ('720p', 'Tarkan')
    """
    if len(command_parts) < 2:
        return "720p", ""

    first_arg = command_parts[1].lower().strip()
    if first_arg in ["720p", "720", "hd"]:
        quality = "720p"
        query = " ".join(command_parts[2:]).strip()
    elif first_arg in ["480p", "480", "sd"]:
        quality = "480p"
        query = " ".join(command_parts[2:]).strip()
    else:
        quality = "720p"
        query = " ".join(command_parts[1:]).strip()

    return quality, query


def _parse_audio_args(command_parts: list) -> Tuple[int, str]:
    """
    Komut argümanlarından bitrate ve arama metnini ayrıştırır.
    Örn: /indir 128k Tarkan -> (128, 'Tarkan')
         /indir Tarkan -> (192, 'Tarkan')
    """
    if len(command_parts) < 2:
        return 192, ""

    first_arg = command_parts[1].lower().strip()
    if first_arg in ["128k", "128", "low"]:
        bitrate = 128
        query = " ".join(command_parts[2:]).strip()
    elif first_arg in ["192k", "192", "high", "320k", "320"]:
        bitrate = 192
        query = " ".join(command_parts[2:]).strip()
    else:
        bitrate = 192
        query = " ".join(command_parts[1:]).strip()

    return bitrate, query


# ── 1. /video Komutu (MP4 Video İndirme) ───────────────────────

@Client.on_message(clean_command(["video", "v"]))
async def video_download_command(client: Client, message: Message):
    """
    /video <link veya isim>
    /video 480p <link veya isim>
    /video 720p <link veya isim>

    YouTube'dan videoyu MP4 formatında indirip kaliteli olarak sohbete gönderir.
    Maksimum 50 MB boyuta izin verir.
    """
    quality, query = _parse_video_args(message.command)
    if not query:
        await message.reply_text(
            msg_usage(
                "/video [720p|480p] <link veya arama>",
                "/video Tarkan Şımarık\n/video 480p https://youtube.com/watch?v=..."
            )
        )
        return

    # Durum bildirimi
    status_msg = await message.reply_text(msg_searching(query, is_video=True))
    downloaded_file = None

    try:
        # İndirme durumuna güncelle
        await status_msg.edit_text(msg_video_downloading(query, quality=quality))

        # Asenkron indirmeyi başlat (Semaphore(2) korumalı)
        result = await download_video(query, quality=quality)

        if not result.get("success"):
            err_type = result.get("error")
            if err_type == "oversized":
                size_mb = result.get("size_mb", 50.0)
                await status_msg.edit_text(msg_file_too_large(size_mb=size_mb))
            elif err_type == "not_found":
                await status_msg.edit_text(msg_error("Video bulunamadı! Lütfen farklı bir arama deneyin."))
            else:
                await status_msg.edit_text(msg_error(result.get("message", "Video indirilemedi.")))
            return

        downloaded_file = result.get("file_path")
        if not downloaded_file or not os.path.exists(downloaded_file):
            await status_msg.edit_text(msg_error("İndirilen video dosyasına ulaşılamadı."))
            return

        # Telegram'a video olarak gönder
        title = result.get("title", "Video")
        size_mb = result.get("size_mb", 0.0)
        duration = result.get("duration", 0)

        await message.reply_video(
            video=downloaded_file,
            caption=msg_video_complete(title=title, quality=quality, size_mb=size_mb),
            duration=duration,
            supports_streaming=True,
        )

        # Durum mesajını kaldır
        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"/video işlem hatası: {e}", exc_info=True)
        try:
            await status_msg.edit_text(msg_error(f"Video gönderilemedi: {e}"))
        except Exception:
            pass
    finally:
        # Geçici dosyayı kesinlikle sil ve belleği temizle
        if downloaded_file:
            cleanup_file(downloaded_file)
        gc.collect()


# ── 2. /indir Komutu (MP3 Ses İndirme) ─────────────────────────

@Client.on_message(clean_command(["indir", "dl", "download"]))
async def audio_download_command(client: Client, message: Message):
    """
    /indir <şarkı adı veya link>
    /indir 128k <şarkı adı veya link>

    YouTube'dan şarkıyı MP3 formatında indirip ses dosyası olarak Telegram'a gönderir.
    """
    bitrate, query = _parse_audio_args(message.command)
    if not query:
        await message.reply_text(
            msg_usage(
                "/indir [192k|128k] <şarkı veya link>",
                "/indir Tarkan Kuzu Kuzu\n/indir 128k https://youtube.com/watch?v=..."
            )
        )
        return

    # Durum bildirimi
    status_msg = await message.reply_text(msg_searching(query, is_video=False))
    downloaded_file = None

    try:
        await status_msg.edit_text(msg_downloading(query))

        # Asenkron indirmeyi başlat (Semaphore(2) korumalı)
        result = await download_audio(query, bitrate=bitrate)

        if not result.get("success"):
            err_type = result.get("error")
            if err_type == "oversized":
                size_mb = result.get("size_mb", 50.0)
                await status_msg.edit_text(msg_file_too_large(size_mb=size_mb))
            elif err_type == "not_found":
                await status_msg.edit_text(msg_error("Şarkı bulunamadı! Lütfen farklı bir arama terimi deneyin."))
            else:
                await status_msg.edit_text(msg_error(result.get("message", "Şarkı indirilemedi.")))
            return

        downloaded_file = result.get("file_path")
        if not downloaded_file or not os.path.exists(downloaded_file):
            await status_msg.edit_text(msg_error("İndirilen ses dosyasına ulaşılamadı."))
            return

        title = result.get("title", "Şarkı")
        performer = result.get("performer", "Ejderha Müzik")
        duration = result.get("duration", 0)

        # Telegram'a müzik dosyası olarak gönder
        await message.reply_audio(
            audio=downloaded_file,
            title=title,
            performer=performer,
            duration=duration,
            caption=msg_download_complete(title=title),
        )

        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"/indir işlem hatası: {e}", exc_info=True)
        try:
            await status_msg.edit_text(msg_error(f"Ses dosyası gönderilemedi: {e}"))
        except Exception:
            pass
    finally:
        if downloaded_file:
            cleanup_file(downloaded_file)
        gc.collect()
