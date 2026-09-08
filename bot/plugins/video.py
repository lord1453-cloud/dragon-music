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
import re
import logging
from typing import Tuple

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.errors import RPCError, Forbidden
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot.theme import (
    msg_searching,
    msg_downloading,
    msg_download_complete,
    msg_video_downloading,
    msg_video_complete,
    msg_file_too_large,
    msg_media_sent_to_pm,
    msg_media_permission_error,
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


# ── Medya Gönderim Yardımcısı (İzin Kısıtlamaları Korumalı) ──

async def _send_media_with_fallback(
    client: Client,
    message: Message,
    status_msg: Message,
    file_path: str,
    media_type: str,
    title: str,
    caption: str,
    duration: int = 0,
    performer: str = "Ejderha Müzik",
) -> None:
    """
    Videoyu veya sesi Telegram'a gönderir.
    Grupta video/ses izni kısıtlıysa (403 CHAT_SEND_VIDEOS_FORBIDDEN vb.):
    1. Belge (document/dosya) olarak göndermeyi dener.
    2. Grupta belge izni de yoksa, kullanıcıya DM (özel mesaj) üzerinden göndermeyi dener.
    3. Kullanıcıya özelden de atamazsa (DM başlatılmamışsa), bilgilendirici mesaj ve DM butonu sunar.
    """
    # 1. Aşama: Asıl medya formatında sohbete göndermeyi dene
    try:
        if media_type == "video":
            await message.reply_video(
                video=file_path,
                caption=caption,
                duration=duration,
                supports_streaming=True,
            )
        else:
            await message.reply_audio(
                audio=file_path,
                title=title,
                performer=performer,
                duration=duration,
                caption=caption,
            )
        try:
            await status_msg.delete()
        except Exception:
            pass
        return
    except Exception as first_err:
        err_str = str(first_err).upper()
        is_forbidden = (
            isinstance(first_err, Forbidden)
            or "FORBIDDEN" in err_str
            or "CHAT_SEND_VIDEOS_FORBIDDEN" in err_str
            or "CHAT_SEND_AUDIOS_FORBIDDEN" in err_str
            or "CHAT_SEND_MEDIA_FORBIDDEN" in err_str
        )
        if not is_forbidden:
            raise first_err

        logger.warning(
            f"Grupta {media_type} gönderme izni kısıtlı ({first_err}). Belge (document) olarak deneniyor..."
        )

    # 2. Aşama: Belge (document) olarak sohbete göndermeyi dene
    clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip() or media_type
    ext = ".mp4" if media_type == "video" else ".mp3"
    file_name = f"{clean_title[:50]}{ext}"

    try:
        await message.reply_document(
            document=file_path,
            caption=caption,
            file_name=file_name,
        )
        try:
            await status_msg.delete()
        except Exception:
            pass
        return
    except Exception as doc_err:
        logger.warning(f"Belge olarak gönderme de kısıtlı ({doc_err})")

    # 3. Aşama: Kullanıcıya özel mesajdan (DM) göndermeyi dene
    user_id = message.from_user.id if message.from_user else None
    is_group = message.chat.type != ChatType.PRIVATE

    bot_me = getattr(client, "me", None)
    if not bot_me and client.is_connected:
        try:
            bot_me = await client.get_me()
        except Exception:
            pass
    bot_username = getattr(bot_me, "username", None) or "DragonMusicBot"

    if user_id and is_group:
        logger.info(f"Grupta medya gönderimi kapalı. Kullanıcıya ({user_id}) özel mesajdan gönderiliyor...")
        try:
            if media_type == "video":
                await client.send_video(
                    chat_id=user_id,
                    video=file_path,
                    caption=caption,
                    duration=duration,
                    supports_streaming=True,
                )
            else:
                await client.send_audio(
                    chat_id=user_id,
                    audio=file_path,
                    title=title,
                    performer=performer,
                    duration=duration,
                    caption=caption,
                )

            # Gruba DM'e gönderildiğini bildir
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 Dosyayı Gör (Bota Git)", url=f"https://t.me/{bot_username}")]
            ])
            try:
                await status_msg.edit_text(msg_media_sent_to_pm(media_type), reply_markup=btn)
            except Exception:
                pass
            return
        except Exception as pm_err:
            logger.warning(f"Kullanıcıya DM ile gönderilemedi ({pm_err}). Kullanıcı botu DM'de başlatmamış olabilir.")

    # 4. Aşama: Hiçbiri olmadıysa, gruba kibar ve yönlendirici mesaj göster
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Bota Git (Özelden İndir)", url=f"https://t.me/{bot_username}?start=dl")]
    ])
    try:
        await status_msg.edit_text(msg_media_permission_error(media_type), reply_markup=btn)
    except Exception:
        pass


# ── 1. /video Komutu (MP4 Video İndirme) ───────────────────────

@Client.on_message(clean_command(["video", "videoindir"]))
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

        # Telegram'a video olarak gönder (izin kısıtlamalarına karşı yedekli)
        title = result.get("title", "Video")
        size_mb = result.get("size_mb", 0.0)
        duration = result.get("duration", 0)

        caption = msg_video_complete(title=title, quality=quality, size_mb=size_mb)
        await _send_media_with_fallback(
            client=client,
            message=message,
            status_msg=status_msg,
            file_path=downloaded_file,
            media_type="video",
            title=title,
            caption=caption,
            duration=duration,
        )

    except Exception as e:
        err_str = str(e).upper()
        if isinstance(e, Forbidden) or "FORBIDDEN" in err_str:
            logger.warning(f"/video izin kısıtlaması nedeniyle gönderilemedi: {e}")
            try:
                await status_msg.edit_text(msg_media_permission_error("video"))
            except Exception:
                pass
        else:
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

@Client.on_message(clean_command(["indir", "sesindir"]))
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

        caption = msg_download_complete(title=title)
        await _send_media_with_fallback(
            client=client,
            message=message,
            status_msg=status_msg,
            file_path=downloaded_file,
            media_type="audio",
            title=title,
            caption=caption,
            duration=duration,
            performer=performer,
        )

    except Exception as e:
        err_str = str(e).upper()
        if isinstance(e, Forbidden) or "FORBIDDEN" in err_str:
            logger.warning(f"/indir izin kısıtlaması nedeniyle gönderilemedi: {e}")
            try:
                await status_msg.edit_text(msg_media_permission_error("audio"))
            except Exception:
                pass
        else:
            logger.error(f"/indir işlem hatası: {e}", exc_info=True)
            try:
                await status_msg.edit_text(msg_error(f"Ses dosyası gönderilemedi: {e}"))
            except Exception:
                pass
    finally:
        if downloaded_file:
            cleanup_file(downloaded_file)
        gc.collect()
