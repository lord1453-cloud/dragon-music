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
    msg_not_playing, msg_no_voice_chat, msg_error,
    get_panel_text, get_panel_keyboard, get_player_keyboard,
    get_system_stats_text, get_stats_keyboard,
    msg_clean_mode_status, get_settings_keyboard,
)
from utils.queue_manager import queue
from utils.db import get_chat_setting, set_chat_setting
from utils.ytdl import (
    get_audio_file_for_stream,
    get_video_file_for_stream,
    cleanup_old_streams,
)
from utils.decorators import check_voice_chat, clean_command, admin_only
from bot.plugins.play import make_stream, _play_next, _cancel_all_timers

logger = logging.getLogger(__name__)


async def voice_chat_active(client: Client, chat_id: int) -> bool:
    """
    Grubun sesli sohbetinin (Group Call) aktif olup olmadığını kontrol eder.
    PyTgCalls veya Pyrogram üzerinden aktif çağrıyı doğrular.
    """
    try:
        if call_client:
            active_calls = getattr(call_client, "active_calls", None) or getattr(call_client, "calls", None)
            if active_calls is not None:
                if isinstance(active_calls, dict) and chat_id in active_calls:
                    return True
                elif isinstance(active_calls, (list, set, tuple)) and chat_id in active_calls:
                    return True

        chat = await client.get_chat(chat_id)
        if getattr(chat, "is_voice_chat_active", False) or getattr(chat, "has_active_voice_chat", False) or getattr(chat, "active_call", None) is not None:
            return True
    except Exception as e:
        logger.debug(f"voice_chat_active kontrol uyarısı ({chat_id}): {e}")
        return True
    return False




# ── İnteraktif Kontrol Paneli Komutları ────────────────────────
@Client.on_message(clean_command(["panel", "kontrol", "cpanel", "dashboard"]))
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
    clean_mode = await get_chat_setting(chat_id, "clean_mode", default=False)

    panel_text = get_panel_text(
        chat_title=chat_title,
        current_track=current_track,
        queue_count=len(queue_tracks),
        is_paused=False,
    )

    await message.reply_text(
        text=panel_text,
        reply_markup=get_panel_keyboard(is_paused=False, clean_mode=clean_mode),
    )


# ── Grup Temiz Mod & Mesaj Silme Ayarı Komutu ──────────────────
@Client.on_message(clean_command(["temizmod", "mesajsil", "mesajsilme", "temiz_mod"]) & filters.group)
@admin_only("⛔ Temiz mod ayarını yalnızca grup yöneticileri değiştirebilir!")
async def clean_mode_command(client: Client, message: Message):
    """
    /temizmod veya /mesajsil komutu:
    Şarkı arama ve kuyruğa ekleme mesajlarının 7 saniye sonra
    otomatik silinip silinmeyeceğini ayarlar.
    """
    chat_id = message.chat.id
    current_setting = await get_chat_setting(chat_id, "clean_mode", default=False)

    args = message.command[1:] if len(message.command) > 1 else []
    if args:
        sub = args[0].lower()
        if sub in ["ac", "aç", "on", "aktif", "true", "1", "evet"]:
            new_val = True
        elif sub in ["kapat", "off", "pasif", "false", "0", "hayır"]:
            new_val = False
        else:
            new_val = not current_setting
    else:
        new_val = not current_setting

    await set_chat_setting(chat_id, "clean_mode", new_val)
    await message.reply_text(msg_clean_mode_status(new_val))


# ── Grup Ayarları Menüsü Komutu ───────────────────────────────
@Client.on_message(clean_command(["ayarlar", "ayar", "settings"]) & filters.group)
@admin_only("⛔ Grup ayarlarını yalnızca grup yöneticileri görüntüleyebilir!")
async def settings_command(client: Client, message: Message):
    """
    /ayarlar komutu:
    Grup bazlı ayarları ve mesaj silme butonunu gösterir.
    """
    chat_id = message.chat.id
    clean_mode = await get_chat_setting(chat_id, "clean_mode", default=False)
    status_text = (
        f"⚙️ **GRUP AYARLARI**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🗑️ **Şarkı Mesajlarını Silme:** {'Açık ✅ (7sn sonra silinir)' if clean_mode else 'Kapalı ❌ (Mesajlar kalır)'}\n\n"
        f"💡 *Aşağıdaki butona tıklayarak ayarı anında değiştirebilirsiniz.*"
    )
    await message.reply_text(
        text=status_text,
        reply_markup=get_settings_keyboard(clean_mode=clean_mode),
    )


# ── Canlı Sistem İstatistikleri Komutu ────────────────────────
@Client.on_message(clean_command(["stats", "istatistik", "durum"]))
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


@Client.on_message(clean_command(["dur", "duraklat"]) & filters.group)
@check_voice_chat()
async def pause_command(client: Client, message: Message):
    """
    /dur veya /duraklat komutu.
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


@Client.on_message(clean_command(["devam", "devamet"]) & filters.group)
@check_voice_chat()
async def resume_command(client: Client, message: Message):
    """
    /devam veya /devamet komutu.
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


@Client.on_message(clean_command(["geç", "gec", "atla"]) & filters.group)
@check_voice_chat()
async def skip_command(client: Client, message: Message):
    """
    /geç, /gec veya /atla komutu.
    Çalan şarkıyı/videoyu atlayıp kuyruktaki sıradakine geçer.
    """
    chat_id = message.chat.id

    if not await queue.has_current(chat_id):
        await message.reply_text(msg_not_playing())
        return

    await message.reply_text("⏭️ **Şarkı atlandı, sıradakine geçiliyor...**")
    await _play_next(client, chat_id)


@Client.on_message(clean_command(["durdur", "bitir", "son", "kapat"]) & filters.group)
@check_voice_chat()
async def stop_command(client: Client, message: Message):
    """
    /durdur, /bitir, /son veya /kapat komutu.
    Yayını tamamen durdurur, kuyruğu temizler ve sesli sohbetten ayrılır.
    """
    chat_id = message.chat.id
    _cancel_all_timers(chat_id)

    try:
        await call_client.leave_group_call(chat_id)
    except Exception:
        pass

    await queue.clear(chat_id)
    await message.reply_text(msg_stopped())
    asyncio.create_task(cleanup_old_streams())


@Client.on_message(clean_command(["karıştır", "karistir"]) & filters.group)
@check_voice_chat()
async def shuffle_command(client: Client, message: Message):
    """
    /karıştır veya /karistir komutu.
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


@Client.on_message(clean_command(["temizle", "sirasifirla"]) & filters.group)
@check_voice_chat()
async def clear_command(client: Client, message: Message):
    """
    /temizle veya /sirasifirla komutu.
    Şu an çalan parçayı bozmadan bekleyen kuyruğu temizler.
    """
    chat_id = message.chat.id

    success = await queue.clear_queue_only(chat_id)
    if success:
        await message.reply_text(msg_queue_cleared())
    else:
        await message.reply_text(msg_error("Temizlenecek bekleyen parça yok."))
