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
)
from utils.queue_manager import queue
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
    "-thread_queue_size 8192 "          # 8192 thread buffer kuyruğu (lag/jitter önler)
)


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
    /join komutuna gerek kalmadan botun doğrudan yayına geçmesini sağlar.
    """
    if not call_client:
        logger.error("PyTgCalls istemcisi aktif değil!")
        return False

    # 1. Zaten bağlıysa akışı güncellemeyi dene
    try:
        await call_client.change_stream(chat_id, stream_obj)
        logger.info(f"✅ Akış güncellendi (chat_id: {chat_id})")
        return True
    except Exception:
        pass

    # 2. Bağlı değilse doğrudan sesli sohbete katıl
    try:
        await call_client.join_group_call(chat_id, stream_obj)
        logger.info(f"✅ Sesli sohbete otomatik bağlanıldı (chat_id: {chat_id})")
        return True
    except Exception as e:
        logger.warning(f"Sesli sohbete 1. bağlanma denemesi başarısız ({chat_id}): {e}")
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
    Parça türüne (Audio / Video) göre uygun indirme ve akış nesnesini seçer.
    """
    track = await queue.next(chat_id)
    if not track:
        try:
            await call_client.leave_group_call(chat_id)
        except Exception:
            pass
        await queue.clear(chat_id)
        return

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
            await _play_next(client, chat_id, message)
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
                await _play_next(client, chat_id, message)
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

    except Exception as e:
        logger.error(f"Şarkı/Video çalma hatası: {e}")
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
    Yayın bittiğinde tetiklenir, kuyruktaki sıradakine geçer.
    """
    chat_id = update.chat_id
    logger.info(f"🎵 Stream bitti (chat_id: {chat_id}), sıradakine geçiliyor...")
    await _play_next(bot_client, chat_id)


@call_client.on_closed_voice_chat()
@call_client.on_kicked()
@call_client.on_left()
async def stream_closed_handler(client: PyTgCalls, chat_id: int):
    """
    Sesli sohbet kapandığında veya bot ayrıldığında kuyruğu temizler.
    """
    logger.info(f"🛑 Sesli sohbet sonlandı veya bot ayrıldı (chat_id: {chat_id})")
    await queue.clear(chat_id)


# ══════════════════════════════════════════════════════════════
# ANA OYNATMA MOTORU (Spotify & YouTube Akışı + Otomatik Bağlanma)
# ══════════════════════════════════════════════════════════════

async def _process_play(client: Client, message: Message, is_video: bool = False):
    """
    /oynat ve /voynat komutlarının ortak motoru.
    Kullanıcı komutu verdiğinde doğrudan sesli sohbete otomatik bağlanır ve yayını başlatır.
    Kuyruk için 20 şarkı sınırı uygular (çalan şarkı hariç).
    """
    cmd_name = "/voynat" if is_video else "/oynat"
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
            return

        position = await queue.add(chat_id, track)
        await status_msg.edit_text(msg_queued(track["title"], position, is_video=is_video))

        if position == 1:
            if is_video:
                asyncio.create_task(get_video_file_for_stream(track["url"]))
            else:
                asyncio.create_task(get_audio_file_for_stream(track["url"]))
    else:
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

        except Exception as e:
            logger.error(f"Yayın başlatma hatası: {e}")
            await status_msg.edit_text(msg_error(str(e)))
            await queue.clear(chat_id)


# ── Komut Kayıtları (Doğrudan Otomatik Bağlanma) ───────────────
# clean_command sayesinde hem /oynat hem de /oynat@PixelMuzikBot sorunsuz çalışır

@Client.on_message(clean_command(["oynat", "play"]) & filters.group)
async def play_command(client: Client, message: Message):
    """/oynat veya /play: Sesli sohbette müzik çalar (otomatik bağlanır)."""
    await _process_play(client, message, is_video=False)


@Client.on_message(clean_command(["voynat", "vplay"]) & filters.group)
async def vplay_command(client: Client, message: Message):
    """/voynat veya /vplay: Sesli sohbette 720p görüntülü yayın başlatır (otomatik bağlanır)."""
    await _process_play(client, message, is_video=True)


