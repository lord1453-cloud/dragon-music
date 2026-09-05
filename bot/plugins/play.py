# ============================================
# 🐲 Ejderha Müzik & Video Botu - Oynat Plugin'i
# ============================================
# /oynat, /play (Ses) ve /voynat, /vplay, /video (Görüntülü Yayın)
# komutlarıyla şarkı/video çalma ve kuyruğa ekleme işlemlerini yönetir.
#
# YENİ ÖZELLİKLER:
# - Görüntülü Yayın (Video Stream): 720p HD MP4 akış desteği
# - Spotify Desteği: Şarkı, albüm ve çalma listesi linklerini otomatik algılama
# - YouTube 403 / Bot koruması (Cookies entegrasyonu)
# - Audio ve Video istekleri için temiz ve modüler if/else mimarisi

import os
import logging
import asyncio
import time
from typing import Optional, Any, Dict

from pyrogram import Client, filters
from pyrogram.types import Message
try:
    from pytgcalls import PyTgCalls  # type: ignore
    from pytgcalls.types import MediaStream, AudioQuality, VideoQuality, Update  # type: ignore
except Exception:
    PyTgCalls = None  # type: ignore
    MediaStream = None  # type: ignore
    AudioQuality = None  # type: ignore
    VideoQuality = None  # type: ignore
    Update = None  # type: ignore

from bot.clients import bot_client, call_client
from bot.theme import (
    msg_searching, msg_playing, msg_queued,
    msg_error, msg_usage, msg_no_voice_chat,
    msg_spotify_importing, get_player_keyboard,
    msg_rate_limited, msg_bot_detected,
    msg_auto_left_empty, msg_auto_left_idle, msg_auto_left_closed,
)
from utils.queue_manager import queue
from utils.db import get_chat_setting
from utils.ytdl import (
    search_youtube,
    get_audio_file_for_stream,
    get_video_file_for_stream,
    cleanup_old_streams,
    YTDLError,
    YouTubeRateLimitError,
    YouTubeBotChallengeError,
)
from utils.spotify import is_spotify_url, get_spotify_tracks
from utils.decorators import clean_command, get_user_display_name

logger = logging.getLogger(__name__)

# Kuyruk parça limiti (çalan şarkı hariç maksimum bekleyen parça sayısı)
MAX_QUEUE_SIZE = 20

# ── Pürüzsüz ve Kararlı Akış FFmpeg Parametreleri ─────────────
SMOOTH_STREAM_FFMPEG = (
    "-re "                             # Gerçek zamanlı akış hızı (1.0x playback rate)
    "-analyzeduration 1000000 "        # 1 saniyelik hızlı format tespiti
    "-probesize 1000000 "               # 1MB probe boyutu
)

# ── Eşzamanlılık, Zamanlayıcılar ve Gözlemciler ───────────────
_play_locks: Dict[int, asyncio.Lock] = {}
_last_stream_end: Dict[int, float] = {}
_active_watchdogs: Dict[int, asyncio.Task] = {}
_idle_leave_tasks: Dict[int, asyncio.Task] = {}
_empty_chat_tasks: Dict[int, asyncio.Task] = {}


def _cancel_all_timers(chat_id: int):
    """Chat için çalışan tüm zamanlayıcıları (watchdog, boşta kalma, boş sesli) iptal eder."""
    if chat_id in _active_watchdogs:
        _active_watchdogs[chat_id].cancel()
        _active_watchdogs.pop(chat_id, None)
    if chat_id in _idle_leave_tasks:
        _idle_leave_tasks[chat_id].cancel()
        _idle_leave_tasks.pop(chat_id, None)
    if chat_id in _empty_chat_tasks:
        _empty_chat_tasks[chat_id].cancel()
        _empty_chat_tasks.pop(chat_id, None)


async def _auto_delete_message(message: Message, delay: int = 7):
    """Mesajı belirtilen süre sonunda arka planda sessizce siler."""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception:
        pass


async def _is_voice_chat_empty(chat_id: int) -> bool:
    """Sesli sohbette dinleyici (kullanıcı) olup olmadığını denetler."""
    if not call_client:
        return False
    try:
        participants = await call_client.get_participants(chat_id)
        if participants is None:
            return False
        active_members = [p for p in participants if not getattr(p, "left", False)]
        user_info = getattr(call_client, "_cache_local_peer", None)
        my_id = getattr(user_info, "user_id", None) if user_info else None
        real_listeners = [p for p in active_members if getattr(p, "user_id", None) != my_id]
        return len(real_listeners) == 0
    except Exception as e:
        logger.debug(f"Katılımcı kontrol hatası ({chat_id}): {e}")
        return False


async def _empty_chat_worker(chat_id: int, timeout: int = 60):
    """Sesli sohbette dinleyici kalmadığında belirli süre sonra yayını kapatır ve ayrılır."""
    try:
        await asyncio.sleep(timeout)
        if not call_client:
            return
        is_still_empty = await _is_voice_chat_empty(chat_id)
        if is_still_empty:
            logger.info(f"👥 Sesli sohbette dinleyici kalmadı ({chat_id}), yayın otomatik kapatılıyor...")
            _cancel_all_timers(chat_id)
            try:
                await call_client.leave_group_call(chat_id)
            except Exception:
                pass
            await queue.clear(chat_id)
            try:
                await bot_client.send_message(chat_id, msg_auto_left_empty())
            except Exception:
                pass
            asyncio.create_task(cleanup_old_streams())
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"empty_chat_worker hatası ({chat_id}): {e}")
    finally:
        _empty_chat_tasks.pop(chat_id, None)


async def _idle_leave_worker(chat_id: int, timeout: int = 60):
    """Kuyruk bittiğinde ve ses çalmazken belirli süre sonra sesli sohbetten otomatik ayrılır."""
    try:
        await asyncio.sleep(timeout)
        if not await queue.has_current(chat_id) and await queue.is_empty(chat_id):
            logger.info(f"⏳ Sesli sohbet boşta kaldı ({chat_id}), otomatik ayrılınıyor...")
            _cancel_all_timers(chat_id)
            if call_client:
                try:
                    await call_client.leave_group_call(chat_id)
                except Exception:
                    pass
            await queue.clear(chat_id)
            try:
                await bot_client.send_message(chat_id, msg_auto_left_idle())
            except Exception:
                pass
            asyncio.create_task(cleanup_old_streams())
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"idle_leave_worker hatası ({chat_id}): {e}")
    finally:
        _idle_leave_tasks.pop(chat_id, None)


async def _check_chat_participants(chat_id: int):
    """Katılımcı değişimini kontrol eder, gerekirse otomatik kapanma sayacını yönetir."""
    if not await queue.has_current(chat_id):
        return
    is_empty = await _is_voice_chat_empty(chat_id)
    if is_empty:
        if chat_id not in _empty_chat_tasks or _empty_chat_tasks[chat_id].done():
            logger.info(f"⚠️ Sesli sohbette dinleyici kalmadı ({chat_id}), 60sn otomatik kapanma sayacı başlatıldı.")
            _empty_chat_tasks[chat_id] = asyncio.create_task(_empty_chat_worker(chat_id, timeout=60))
    else:
        if chat_id in _empty_chat_tasks:
            logger.info(f"👥 Sesli sohbete dinleyici katıldı ({chat_id}), otomatik kapanma sayacı iptal edildi.")
            _empty_chat_tasks[chat_id].cancel()
            _empty_chat_tasks.pop(chat_id, None)


async def _track_watchdog(chat_id: int, duration_sec: int):
    """
    Şarkı süresini arka planda takip eder.
    PyTgCalls stream_end olayının kaçırılması durumunda
    otomatik olarak sıradaki parçaya geçişi tetikler.
    """
    if duration_sec <= 0:
        duration_sec = 240
    try:
        await asyncio.sleep(duration_sec + 5)
        if await queue.has_current(chat_id):
            logger.info(f"⏰ Watchdog tetiklendi ({chat_id}): Şarkı süresi doldu, sıradakine geçiliyor...")
            await _play_next(bot_client, chat_id)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Watchdog hatası ({chat_id}): {e}")
    finally:
        _active_watchdogs.pop(chat_id, None)


def _make_audio_stream(file_path: str) -> MediaStream:
    """Takılmasız ses akışı nesnesi oluşturur."""
    return MediaStream(
        file_path,
        audio_parameters=AudioQuality.HIGH,
        video_flags=MediaStream.IGNORE,
        ffmpeg_parameters=SMOOTH_STREAM_FFMPEG,
    )


def _make_video_stream(file_path: str) -> MediaStream:
    """720p HD görüntülü yayın (Video Stream) nesnesi oluşturur."""
    return MediaStream(
        file_path,
        audio_parameters=AudioQuality.HIGH,
        video_parameters=VideoQuality.HD_720p,
        video_flags=MediaStream.REQUIRED,
        ffmpeg_parameters=SMOOTH_STREAM_FFMPEG,
    )


def make_stream(file_path: str, is_video: bool = False) -> MediaStream:
    """
    Ses veya Video akışı nesnesi oluşturan modüler fabrika fonksiyonu.
    if/else yapısıyla ses ve video isteklerini temizce ayırır.
    """
    if is_video:
        return _make_video_stream(file_path)
    else:
        return _make_audio_stream(file_path)


async def join_voice_chat(chat_id: int, stream_obj: MediaStream) -> bool:
    """
    Sesli sohbete otomatik olarak bağlanır veya mevcut akışı günceller.
    Bağlantı kopması veya AlreadyJoined durumlarında akıllıca kendini toparlar.
    """
    if not call_client:
        logger.error("PyTgCalls istemcisi aktif değil!")
        return False

    # 1. Zaten bağlıysa akışı güncellemeyi dene
    try:
        await call_client.change_stream(chat_id, stream_obj)
        logger.info(f"✅ Akış güncellendi (chat_id: {chat_id})")
        return True
    except Exception as e:
        logger.warning(f"change_stream başarısız ({chat_id}): {e}")

    # 2. Bağlı değilse doğrudan sesli sohbete katıl
    try:
        await call_client.join_group_call(chat_id, stream_obj)
        logger.info(f"✅ Sesli sohbete otomatik bağlanıldı (chat_id: {chat_id})")
        return True
    except Exception as e:
        err_str = str(e)
        logger.warning(f"Sesli sohbete 1. bağlanma denemesi başarısız ({chat_id}): {err_str}")
        if "already" in err_str.lower():
            try:
                await call_client.leave_group_call(chat_id)
                await asyncio.sleep(0.5)
            except Exception:
                pass
        else:
            await asyncio.sleep(0.8)

        try:
            await call_client.join_group_call(chat_id, stream_obj)
            logger.info(f"✅ Sesli sohbete 2. denemede bağlanıldı (chat_id: {chat_id})")
            return True
        except Exception as e2:
            logger.error(f"❌ Sesli sohbete bağlanılamadı ({chat_id}): {e2}")
            return False


async def _prefetch_next(chat_id: int):
    """
    Kuyruktaki sıradaki parçayı arka planda indirir.
    Geçişlerdeki bekleme süresini minimuma indirir.
    """
    try:
        tracks = await queue.get_queue(chat_id)
        if tracks:
            next_track = tracks[0]
            next_url = next_track.get("url")
            is_video = next_track.get("stream_type") == "video"
            if next_url:
                if is_video:
                    asyncio.create_task(get_video_file_for_stream(next_url))
                else:
                    asyncio.create_task(get_audio_file_for_stream(next_url))
                logger.info(f"🔥 Sıradaki parça arka planda indiriliyor: {next_track.get('title', '?')}")
    except Exception:
        pass


async def _play_next(client: Client, chat_id: int, message: Message = None):
    """
    Kuyruktaki sıradaki parçayı çalar.
    Yarış durumlarına (race condition) karşı chat_id kilitli çalışır.
    """
    if chat_id not in _play_locks:
        _play_locks[chat_id] = asyncio.Lock()

    async with _play_locks[chat_id]:
        # Mevcut watchdog varsa iptal et
        if chat_id in _active_watchdogs:
            _active_watchdogs[chat_id].cancel()
            _active_watchdogs.pop(chat_id, None)

        track = await queue.next(chat_id)
        if not track:
            logger.info(f"✨ Kuyruk tamamlandı ({chat_id}), 60sn boşta kalma sayacı başlatılıyor...")
            await queue.set_current(chat_id, None)
            asyncio.create_task(cleanup_old_streams())

            if chat_id in _idle_leave_tasks:
                _idle_leave_tasks[chat_id].cancel()
            _idle_leave_tasks[chat_id] = asyncio.create_task(_idle_leave_worker(chat_id, timeout=60))

            try:
                await bot_client.send_message(
                    chat_id,
                    "✨ **Kuyruk tamamlandı.**\n*60 saniye içinde yeni şarkı eklenmezse sesli sohbetten otomatik ayrılacağım.*"
                )
            except Exception:
                pass
            return

        # Sıradaki parça var, boşta kalma sayacını iptal et
        if chat_id in _idle_leave_tasks:
            _idle_leave_tasks[chat_id].cancel()
            _idle_leave_tasks.pop(chat_id, None)

        is_video = track.get("stream_type") == "video"

        try:
            # ── Ses ve Video Ayrımı (Download) ────────────────────
            if is_video:
                file_path = await get_video_file_for_stream(track["url"])
            else:
                file_path = await get_audio_file_for_stream(track["url"], title=track.get("title"))

            if not file_path:
                if message:
                    await message.reply_text(msg_error("Medya dosyası indirilemedi."))
                else:
                    try:
                        await bot_client.send_message(
                            chat_id,
                            msg_error(f"'{track.get('title')}' indirilemedi, sıradakine geçiliyor...")
                        )
                    except Exception:
                        pass
                asyncio.create_task(_play_next(client, chat_id, message))
                return

            if os.path.getsize(file_path) < 10000:
                logger.warning(f"Dosya boyutu çok küçük: {file_path}")
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                if is_video:
                    file_path = await get_video_file_for_stream(track["url"])
                else:
                    file_path = await get_audio_file_for_stream(track["url"])
                if not file_path:
                    asyncio.create_task(_play_next(client, chat_id, message))
                    return

            # ── Akışı Başlat veya Değiştir ────────────────────────
            stream_obj = make_stream(file_path, is_video=is_video)
            joined = await join_voice_chat(chat_id, stream_obj)
            if not joined:
                logger.error(f"Sıradaki parça için sesli sohbete bağlanılamadı ({chat_id})")
                return

            msg_text = msg_playing(track["title"], track.get("duration_str", ""), is_video=is_video)
            if message:
                await message.reply_text(msg_text, reply_markup=get_player_keyboard(is_paused=False))
            else:
                try:
                    await bot_client.send_message(chat_id, msg_text, reply_markup=get_player_keyboard(is_paused=False))
                except Exception:
                    pass

            await _prefetch_next(chat_id)
            asyncio.create_task(cleanup_old_streams(keep_path=file_path))

            # Şarkı süresini izleyen watchdog başlat
            duration = track.get("duration", 0)
            if duration and duration > 0:
                _active_watchdogs[chat_id] = asyncio.create_task(_track_watchdog(chat_id, duration))

            # Katılımcı sayısını kontrol et
            asyncio.create_task(_check_chat_participants(chat_id))

        except Exception as e:
            logger.error(f"Şarkı/Video çalma hatası: {e}")
            if message:
                await message.reply_text(msg_error(str(e)))
            else:
                try:
                    await bot_client.send_message(chat_id, msg_error(f"Oynatma hatası: {e}"))
                except Exception:
                    pass
            asyncio.create_task(_play_next(client, chat_id, message))


# ── PyTgCalls Olay Dinleyicileri (Event Handlers) ─────────────

if call_client:
    @call_client.on_stream_end()
    async def stream_end_handler(client: PyTgCalls, update: Any):
        """
        Yayın bittiğinde tetiklenir, kuyruktaki sıradakine otomatik geçer.
        Mükerrer ve hızlı tetiklenmeleri önleyen debouncer içerir.
        """
        chat_id = getattr(update, "chat_id", update)
        if not isinstance(chat_id, int):
            try:
                chat_id = int(chat_id)
            except Exception:
                return

        now = time.time()
        if now - _last_stream_end.get(chat_id, 0) < 1.5:
            return
        _last_stream_end[chat_id] = now

        logger.info(f"🎵 Stream bitti (chat_id: {chat_id}), sıradakine otomatik geçiliyor...")
        asyncio.create_task(_play_next(bot_client, chat_id))


    @call_client.on_closed_voice_chat()
    @call_client.on_kicked()
    @call_client.on_left()
    async def stream_closed_handler(client: PyTgCalls, chat_id: Any):
        """
        Sesli sohbet kapandığında veya bot ayrıldığında kuyruğu temizler ve yayın durdurulur.
        """
        cid = getattr(chat_id, "chat_id", chat_id)
        if not isinstance(cid, int):
            try:
                cid = int(cid)
            except Exception:
                return

        logger.info(f"🛑 Sesli sohbet sonlandı veya bot ayrıldı (chat_id: {cid})")
        _cancel_all_timers(cid)
        await queue.clear(cid)
        try:
            await call_client.leave_group_call(cid)
        except Exception:
            pass
        try:
            await bot_client.send_message(cid, msg_auto_left_closed())
        except Exception:
            pass
        asyncio.create_task(cleanup_old_streams())


    @call_client.on_participants_change()
    async def participants_handler(client: PyTgCalls, update: Any):
        """
        Sesli sohbette katılımcı değiştiğinde kontrol eder.
        Dinleyici kalmadığında 60 saniyelik otomatik kapanma sayacını tetikler.
        """
        chat_id = getattr(update, "chat_id", None)
        if chat_id:
            await _check_chat_participants(chat_id)


# ══════════════════════════════════════════════════════════════
# ANA OYNATMA MOTORU (Spotify & YouTube Akışı + Otomatik Bağlanma)
# ══════════════════════════════════════════════════════════════

async def _process_play(client: Client, message: Message, is_video: bool = False):
    """
    /oynat ve /voynat komutlarının ortak motoru.
    Kullanıcı komutu verdiğinde doğrudan sesli sohbete otomatik bağlanır ve yayını başlatır.
    Kuyruk için 20 şarkı sınırı uygular (çalan şarkı hariç).
    """
    cmd_name = "/videoçal" if is_video else "/çal"
    if len(message.command) < 2:
        example = f"{cmd_name} https://open.spotify.com/track/..." if not is_video else f"{cmd_name} Tarkan Şımarık Klip"
        await message.reply_text(msg_usage(f"{cmd_name} <şarkı adı / link>", example))
        return

    raw_query = " ".join(message.command[1:]).strip()
    chat_id = message.chat.id
    requester = get_user_display_name(message)

    # Kuyruk limit kontrolü: Çalan şarkı varsa ve kuyruk 20 limitine ulaştıysa doğrudan uyar
    is_playing = await queue.has_current(chat_id)
    current_queue = await queue.get_queue(chat_id)
    if is_playing and len(current_queue) >= MAX_QUEUE_SIZE:
        await message.reply_text("❌ Kuyruk dolu! (20 şarkı limiti)")
        return

    status_msg = await message.reply_text(msg_searching(raw_query, is_video=is_video))

    # Temiz mod ayarı (Arama ve sıraya ekleme mesajlarını otomatik silme)
    is_clean = await get_chat_setting(chat_id, "clean_mode", default=False)

    # ══════════════════════════════════════════════════════════
    # IF/ELSE KONTROL BLOĞU: Spotify mı, değil mi?
    # ══════════════════════════════════════════════════════════

    if is_spotify_url(raw_query):
        logger.info(f"🟢 Spotify linki algılandı: {raw_query}")
        spotify_search_list = await get_spotify_tracks(raw_query)
        if not spotify_search_list:
            await status_msg.edit_text(msg_error("Spotify linki çözümlenemedi veya şarkı bulunamadı!"))
            return

        # ── Çoklu şarkı (Album / Playlist) ────────────────────
        if len(spotify_search_list) > 1:
            import_list = spotify_search_list[:50]
            await status_msg.edit_text(msg_spotify_importing(len(import_list)))
            first_track = None

            for i, artist_song in enumerate(import_list):
                # Kuyruk 20 limitine ulaştıysa daha fazla şarkı ekleme
                curr_q = await queue.get_queue(chat_id)
                currently_playing = await queue.has_current(chat_id)
                if currently_playing and len(curr_q) >= MAX_QUEUE_SIZE:
                    logger.info(f"Kuyruk 20 şarkı limitine ulaştı ({chat_id}). Spotify aktarımı durduruldu.")
                    break

                if i > 0:
                    await asyncio.sleep(0.3)

                logger.info(f"🟢 Spotify → YouTube araması: ytsearch1:{artist_song}")
                yt_res = await search_youtube(artist_song)
                if not yt_res:
                    continue

                track_info = {
                    "title": yt_res["title"],
                    "url": yt_res["url"],
                    "duration": yt_res["duration"],
                    "duration_str": yt_res["duration_str"],
                    "stream_type": "video" if is_video else "audio",
                    "requester": requester,
                }

                is_playing_now = await queue.has_current(chat_id)
                if not is_playing_now and first_track is None:
                    first_track = track_info
                    await queue.set_current(chat_id, track_info)
                else:
                    await queue.add(chat_id, track_info)

            # İlk parçayı başlat
            if first_track:
                # Boşta kalma sayacını iptal et
                if chat_id in _idle_leave_tasks:
                    _idle_leave_tasks[chat_id].cancel()
                    _idle_leave_tasks.pop(chat_id, None)

                try:
                    if is_video:
                        file_path = await get_video_file_for_stream(first_track["url"])
                    else:
                        file_path = await get_audio_file_for_stream(first_track["url"])

                    if not file_path:
                        await status_msg.edit_text(msg_error("İlk parçanın dosyası indirilemedi."))
                        await queue.clear(chat_id)
                        return

                    stream_obj = make_stream(file_path, is_video=is_video)
                    joined = await join_voice_chat(chat_id, stream_obj)
                    if not joined:
                        await status_msg.edit_text("❌ Sesli kanala bağlanılamadı. Lütfen grupta sesli sohbetin açık olduğundan emin olun.")
                        await queue.clear(chat_id)
                        return

                    await status_msg.edit_text(
                        msg_playing(first_track["title"], first_track.get("duration_str", ""), is_video=is_video),
                        reply_markup=get_player_keyboard(is_paused=False),
                    )
                    await _prefetch_next(chat_id)

                    # Şarkı süresi izleyen watchdog başlat
                    dur = first_track.get("duration", 0)
                    if dur and dur > 0:
                        _active_watchdogs[chat_id] = asyncio.create_task(_track_watchdog(chat_id, dur))

                    asyncio.create_task(_check_chat_participants(chat_id))

                    if is_clean:
                        asyncio.create_task(_auto_delete_message(message, delay=7))

                except Exception as e:
                    logger.error(f"Spotify çoklu oynatma hatası: {e}")
                    await status_msg.edit_text(msg_error(str(e)))
                    await queue.clear(chat_id)
            return

        search_query = spotify_search_list[0]
    else:
        search_query = raw_query

    # ══════════════════════════════════════════════════════════
    # YOUTUBE ARAMA VE OYNATMA
    # ══════════════════════════════════════════════════════════
    result = await search_youtube(search_query)
    if not result:
        await status_msg.edit_text(msg_error("İstenen parça/video YouTube üzerinde bulunamadı!"))
        if is_clean:
            asyncio.create_task(_auto_delete_message(status_msg, delay=7))
            asyncio.create_task(_auto_delete_message(message, delay=7))
        return

    track = {
        "title": result["title"],
        "url": result["url"],
        "duration": result["duration"],
        "duration_str": result["duration_str"],
        "stream_type": "video" if is_video else "audio",
        "requester": requester,
    }

    is_playing = await queue.has_current(chat_id)

    if is_playing:
        # Kuyruk 20 şarkı limiti kontrolü
        current_queue = await queue.get_queue(chat_id)
        if len(current_queue) >= MAX_QUEUE_SIZE:
            await status_msg.edit_text("❌ Kuyruk dolu! (20 şarkı limiti)")
            if is_clean:
                asyncio.create_task(_auto_delete_message(status_msg, delay=7))
                asyncio.create_task(_auto_delete_message(message, delay=7))
            return

        position = await queue.add(chat_id, track)
        await status_msg.edit_text(msg_queued(track["title"], position, is_video=is_video))

        # Temiz mod aktifse sıraya eklendi mesajını ve komutu otomatik sil
        if is_clean:
            asyncio.create_task(_auto_delete_message(status_msg, delay=7))
            asyncio.create_task(_auto_delete_message(message, delay=7))

        if position == 1:
            if is_video:
                asyncio.create_task(get_video_file_for_stream(track["url"]))
            else:
                asyncio.create_task(get_audio_file_for_stream(track["url"]))
    else:
        # Varsa boşta kalma sayacını iptal et
        if chat_id in _idle_leave_tasks:
            _idle_leave_tasks[chat_id].cancel()
            _idle_leave_tasks.pop(chat_id, None)

        await queue.set_current(chat_id, track)

        try:
            if is_video:
                file_path = await get_video_file_for_stream(result["url"])
            else:
                file_path = await get_audio_file_for_stream(result["url"], title=result.get("title"))

            if not file_path:
                await status_msg.edit_text(msg_error("Medya dosyası indirilemedi."))
                await queue.clear(chat_id)
                return

            if os.path.getsize(file_path) < 10000:
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                if is_video:
                    file_path = await get_video_file_for_stream(result["url"])
                else:
                    file_path = await get_audio_file_for_stream(result["url"])
                if not file_path:
                    await status_msg.edit_text(msg_error("Medya dosyası bozuk."))
                    await queue.clear(chat_id)
                    return

            stream_obj = make_stream(file_path, is_video=is_video)
            joined = await join_voice_chat(chat_id, stream_obj)
            if not joined:
                await status_msg.edit_text("❌ Sesli kanala bağlanılamadı. Lütfen grupta sesli sohbetin açık olduğundan emin olun.")
                await queue.clear(chat_id)
                return

            await status_msg.edit_text(
                msg_playing(track["title"], track.get("duration_str", ""), is_video=is_video),
                reply_markup=get_player_keyboard(is_paused=False),
            )
            await _prefetch_next(chat_id)

            # Şarkı süresi izleyen watchdog başlat
            dur = track.get("duration", 0)
            if dur and dur > 0:
                _active_watchdogs[chat_id] = asyncio.create_task(_track_watchdog(chat_id, dur))

            # Katılımcı kontrolü başlat
            asyncio.create_task(_check_chat_participants(chat_id))

            # Temiz mod aktifse komut mesajını sil
            if is_clean:
                asyncio.create_task(_auto_delete_message(message, delay=7))

        except Exception as e:
            logger.error(f"Yayın başlatma hatası: {e}")
            await status_msg.edit_text(msg_error(str(e)))
            await queue.clear(chat_id)


# ── Komut Kayıtları (Doğrudan Otomatik Bağlanma) ───────────────
# clean_command sayesinde hem /çal hem de /oynat (@mention dahil) sorunsuz çalışır

@Client.on_message(clean_command(["çal", "cal", "oynat"]))
async def play_command(client: Client, message: Message):
    """/çal veya /oynat: Sesli sohbette müzik çalar (otomatik bağlanır, Türkçe arama öncelikli)."""
    if message.chat.type.value == "private":
        await message.reply_text(
            "🐲 **Sesli Sohbet Uyarısı!**\n\n"
            "Müzik çalabilmem için beni bir **gruba** eklemeli ve o grupta sesli sohbeti başlatmalısınız!\n"
            "Grupta `/çal <şarkı>` veya `/oynat <şarkı>` yazarak müziği ateşleyebilirsiniz! 🔥"
        )
        return
    await _process_play(client, message, is_video=False)


# /çal ve /oynat komutu için açık alias tanımlaması
cal_command = play_command
oynat_command = play_command


@Client.on_message(clean_command(["videoçal", "videocal", "voynat"]))
async def vplay_command(client: Client, message: Message):
    """/videoçal veya /voynat: Sesli sohbette 720p görüntülü yayın başlatır (otomatik bağlanır)."""
    if message.chat.type.value == "private":
        await message.reply_text(
            "🐲 **Sesli Sohbet Uyarısı!**\n\n"
            "Görüntülü yayın başlatabilmem için beni bir **gruba** eklemeli ve sesli sohbeti başlatmalısınız!\n"
            "Grupta `/videoçal <video/şarkı>` yazarak yayını başlatabilirsiniz! 🎬"
        )
        return
    await _process_play(client, message, is_video=True)


videocal_command = vplay_command
voynat_command = vplay_command




