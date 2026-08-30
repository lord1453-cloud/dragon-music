# ============================================
# 🐲 Ejderha Müzik Botu - Callback Plugin'i
# ============================================
# Inline buton tıklamalarını, interaktif Kontrol Panelini
# ve canlı müzik oynatıcı butonlarını yönetir.

import logging
import asyncio

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from pyrogram.enums import ParseMode

from bot.clients import call_client, bot_client
from bot.theme import (
    WELCOME_TEXT, COMMANDS_TEXT, DOWNLOAD_HELP_TEXT,
    SETTINGS_TEXT, DEVELOPER_TEXT,
    get_main_menu_keyboard, get_back_button, get_dev_keyboard,
    get_panel_keyboard, get_player_keyboard,
    get_panel_text, get_system_stats_text, get_stats_keyboard,
    msg_paused, msg_resumed, msg_skipped, msg_stopped,
    msg_shuffled, msg_queue_cleared, msg_queue_empty,
    msg_queue_list, msg_not_playing, msg_error,
)
from utils.queue_manager import queue
from utils.ytdl import (
    get_audio_file_for_stream,
    get_video_file_for_stream,
    cleanup_old_streams,
)

logger = logging.getLogger(__name__)


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    """Markdown destekli güvenli mesaj güncelleme."""
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.debug(f"Markdown edit başarısız ({e}), düz metin deneniyor...")
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.DISABLED,
            )
        except Exception:
            pass


# ── 1. Ana Menü ve Bilgi Callback'leri (menu_*) ───────────────
@Client.on_callback_query(filters.regex(r"^menu_"))
async def menu_callback(client: Client, callback: CallbackQuery):
    """Ana menü ve alt rehber butonları."""
    data = callback.data
    logger.info(f"🔘 Menü butonu: {data} - Kullanıcı: {callback.from_user.id if callback.from_user else '?'}")

    try:
        if data == "menu_main":
            await _safe_edit(callback, text=WELCOME_TEXT, reply_markup=get_main_menu_keyboard())
        elif data == "menu_commands":
            await _safe_edit(callback, text=COMMANDS_TEXT, reply_markup=get_back_button())
        elif data == "menu_download":
            await _safe_edit(callback, text=DOWNLOAD_HELP_TEXT, reply_markup=get_back_button())
        elif data == "menu_settings":
            await _safe_edit(callback, text=SETTINGS_TEXT, reply_markup=get_back_button())
        elif data == "menu_developer":
            await _safe_edit(callback, text=DEVELOPER_TEXT, reply_markup=get_dev_keyboard())
    except Exception as e:
        logger.error(f"menu_callback hatası: {e}", exc_info=True)
    finally:
        try:
            await callback.answer()
        except Exception:
            pass


# ── 2. İnteraktif Kontrol Paneli ve Oynatıcı (ctrl_*) ──────────
@Client.on_callback_query(filters.regex(r"^ctrl_"))
async def control_callback(client: Client, callback: CallbackQuery):
    """
    Kontrol Paneli ve Çalar butonlarını anlık olarak yönetir.
    """
    data = callback.data
    chat_id = callback.message.chat.id
    chat_title = callback.message.chat.title or "Özel Sohbet"
    user_name = callback.from_user.first_name if callback.from_user else "Bilinmeyen"

    logger.info(f"🎛️ Panel butonu tıklandı: {data} [{chat_title}: {chat_id}, Kullanıcı: {user_name}]")

    try:
        # ── KONTROL PANELİNİ AÇ / YENİLE ──
        if data in ["ctrl_panel", "ctrl_refresh"]:
            current_track = await queue.get_current(chat_id)
            queue_tracks = await queue.get_queue(chat_id)
            is_paused = False
            panel_text = get_panel_text(
                chat_title=chat_title,
                current_track=current_track,
                queue_count=len(queue_tracks),
                is_paused=is_paused,
            )
            await _safe_edit(callback, text=panel_text, reply_markup=get_panel_keyboard(is_paused=is_paused))
            await callback.answer("🔄 Kontrol Paneli güncellendi!")
            return

        # ── DURAKLAT ──
        elif data == "ctrl_pause":
            if not await queue.has_current(chat_id):
                await callback.answer("❌ Şu an çalan bir parça yok!", show_alert=True)
                return
            try:
                await call_client.pause_stream(chat_id)
                current_track = await queue.get_current(chat_id)
                queue_tracks = await queue.get_queue(chat_id)
                panel_text = get_panel_text(
                    chat_title=chat_title,
                    current_track=current_track,
                    queue_count=len(queue_tracks),
                    is_paused=True,
                )
                await _safe_edit(callback, text=panel_text, reply_markup=get_panel_keyboard(is_paused=True))
                await callback.answer("⏸️ Yayın duraklatıldı!")
            except Exception as e:
                logger.error(f"ctrl_pause hatası: {e}")
                await callback.answer(f"Hata: {e}", show_alert=True)
            return

        # ── DEVAM ET ──
        elif data == "ctrl_resume":
            if not await queue.has_current(chat_id):
                await callback.answer("❌ Şu an çalan bir parça yok!", show_alert=True)
                return
            try:
                await call_client.resume_stream(chat_id)
                current_track = await queue.get_current(chat_id)
                queue_tracks = await queue.get_queue(chat_id)
                panel_text = get_panel_text(
                    chat_title=chat_title,
                    current_track=current_track,
                    queue_count=len(queue_tracks),
                    is_paused=False,
                )
                await _safe_edit(callback, text=panel_text, reply_markup=get_panel_keyboard(is_paused=False))
                await callback.answer("▶️ Yayın devam ettiriliyor!")
            except Exception as e:
                logger.error(f"ctrl_resume hatası: {e}")
                await callback.answer(f"Hata: {e}", show_alert=True)
            return

        # ── ATLA / GEÇ ──
        elif data == "ctrl_skip":
            if not await queue.has_current(chat_id):
                await callback.answer("❌ Çalan veya sırada bekleyen parça yok!", show_alert=True)
                return

            from bot.plugins.play import make_stream
            next_track = await queue.next(chat_id)

            if next_track:
                is_video = next_track.get("stream_type") == "video"
                try:
                    if is_video:
                        file_path = await get_video_file_for_stream(next_track["url"])
                    else:
                        file_path = await get_audio_file_for_stream(next_track["url"], title=next_track.get("title"))

                    if not file_path:
                        await callback.answer("❌ Medya dosyası indirilemedi!", show_alert=True)
                        return

                    await call_client.change_stream(chat_id, make_stream(file_path, is_video=is_video))
                    await callback.answer(f"⏭️ Sıradakine geçildi: {next_track['title'][:30]}")

                    # Paneli güncelle
                    queue_tracks = await queue.get_queue(chat_id)
                    panel_text = get_panel_text(
                        chat_title=chat_title,
                        current_track=next_track,
                        queue_count=len(queue_tracks),
                        is_paused=False,
                    )
                    await _safe_edit(callback, text=panel_text, reply_markup=get_panel_keyboard(is_paused=False))
                    asyncio.create_task(cleanup_old_streams(keep_path=file_path))
                except Exception as e:
                    logger.error(f"ctrl_skip hatası: {e}")
                    await callback.answer(f"Atlama hatası: {e}", show_alert=True)
            else:
                try:
                    await call_client.leave_group_call(chat_id)
                except Exception:
                    pass
                await queue.clear(chat_id)
                await callback.answer("⏹️ Kuyruk bitti, sesli sohbetten ayrılındı.")
                panel_text = get_panel_text(chat_title=chat_title, current_track=None, queue_count=0)
                await _safe_edit(callback, text=panel_text, reply_markup=get_panel_keyboard(is_paused=False))
            return

        # ── YAYINI BİTİR / DURDUR ──
        elif data == "ctrl_stop":
            try:
                await call_client.leave_group_call(chat_id)
            except Exception:
                pass
            await queue.clear(chat_id)
            await callback.answer("🛑 Yayın sonlandırıldı ve kuyruk temizlendi.", show_alert=True)
            panel_text = get_panel_text(chat_title=chat_title, current_track=None, queue_count=0)
            await _safe_edit(callback, text=panel_text, reply_markup=get_panel_keyboard(is_paused=False))
            asyncio.create_task(cleanup_old_streams())
            return

        # ── KUYRUĞU KARIŞTIR ──
        elif data == "ctrl_shuffle":
            success = await queue.shuffle(chat_id)
            if success:
                await callback.answer("🔀 Kuyruktaki parçalar rastgele karıştırıldı!")
                current_track = await queue.get_current(chat_id)
                queue_tracks = await queue.get_queue(chat_id)
                panel_text = get_panel_text(
                    chat_title=chat_title,
                    current_track=current_track,
                    queue_count=len(queue_tracks),
                )
                await _safe_edit(callback, text=panel_text, reply_markup=get_panel_keyboard(is_paused=False))
            else:
                await callback.answer("❌ Karıştırmak için sırada en az 2 parça olmalı!", show_alert=True)
            return

        # ── KUYRUĞU TEMİZLE ──
        elif data == "ctrl_clear":
            success = await queue.clear_queue_only(chat_id)
            if success:
                await callback.answer("🧹 Bekleyen tüm parçalar temizlendi!")
                current_track = await queue.get_current(chat_id)
                panel_text = get_panel_text(chat_title=chat_title, current_track=current_track, queue_count=0)
                await _safe_edit(callback, text=panel_text, reply_markup=get_panel_keyboard(is_paused=False))
            else:
                await callback.answer("ℹ️ Sırada bekleyen parça yok.", show_alert=True)
            return

        # ── KUYRUK LİSTESİNİ GÖR ──
        elif data == "ctrl_queue":
            current_track = await queue.get_current(chat_id)
            queue_tracks = await queue.get_queue(chat_id)

            if not current_track and not queue_tracks:
                await callback.answer("ℹ️ Şu an kuyruk tamamen boş!", show_alert=True)
                return

            current_title = current_track.get("title") if current_track else None
            if queue_tracks:
                queue_text = msg_queue_list(queue_tracks, current_title=current_title)
            else:
                queue_text = (
                    f"📋 **EJDERHA YAYIN KUYRUĞU**\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🔥 **Şu An Çalan:** {current_title}\n\n"
                    f"✨ *Sırada bekleyen başka parça yok.*"
                )
            await _safe_edit(callback, text=queue_text, reply_markup=get_back_button())
            await callback.answer()
            return

        # ── SİSTEM İSTATİSTİKLERİ ──
        elif data == "ctrl_stats":
            stats_text = get_system_stats_text()
            await _safe_edit(callback, text=stats_text, reply_markup=get_stats_keyboard())
            await callback.answer()
            return

        # ── KAPAT ──
        elif data == "ctrl_close":
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.answer("Panel kapatıldı.")
            return

    except Exception as e:
        logger.error(f"control_callback genel hatası ({data}): {e}", exc_info=True)
        try:
            await callback.answer(f"İşlem hatası: {e}", show_alert=True)
        except Exception:
            pass
