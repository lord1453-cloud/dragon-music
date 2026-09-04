# ============================================
# 🐲 Ejderha Müzik Botu - Dekoratörler Modülü
# ============================================
# Kontrol komutlarının (/duraklat, /devam, /gec, /bitir vb.)
# yayın sırasında güvenle çalışmasını denetleyen dekoratör.

import functools
import logging
from typing import Callable, Any, Union, List, Tuple, Optional
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus

from bot.clients import call_client
from bot.config import ADMIN_IDS
from utils.queue_manager import queue

logger = logging.getLogger(__name__)


# ── Kullanıcı Adı ve Kimliği Güvenli Çözücü ("?" Hatasını Önler) ──
def get_user_display_name(message: Message) -> str:
    """
    Mesajı gönderen kullanıcının görünen adını çözer.
    Anonim yöneticiler veya kanal olarak atılan mesajlarda '?' yerine kanal/yönetici unvanını döndürür.
    """
    if message.from_user:
        return message.from_user.first_name or message.from_user.username or f"Kullanıcı_{message.from_user.id}"
    elif message.sender_chat:
        return message.sender_chat.title or "Anonim Yönetici"
    return "Anonim Kullanıcı"


def get_user_id(message: Message) -> int:
    """Mesajı gönderenin ID'sini güvenli şekilde döndürür."""
    if message.from_user:
        return message.from_user.id
    elif message.sender_chat:
        return message.sender_chat.id
    return 0


def tr_lower(text: str) -> str:
    """Türkçe İ/ı ve diğer büyük harfleri güvenle küçük harfe çevirir."""
    if not text:
        return ""
    return text.replace("İ", "i").replace("I", "ı").lower()


# ── Mention (@) Temizleyici & Komut Ayrıştırıcı ───────────────
def parse_command(message: Message) -> Tuple[Optional[str], str]:
    """
    Mesajdaki '@BotKullaniciAdi' kısmını temizler.
    Örnek: '/voynat@PixelMuzikBot https://...' -> ('/voynat', 'https://...')
    Boş mesajlarda (None, '') döndürür.
    """
    raw_text = message.text or message.caption
    if not raw_text or not raw_text.strip():
        return None, ""

    parts = raw_text.strip().split(maxsplit=1)
    raw_cmd = parts[0]
    # @ kısmını kes (örn: /voynat@PixelMuzikBot -> /voynat)
    clean_cmd = tr_lower(raw_cmd.split("@")[0])
    args = parts[1].strip() if len(parts) > 1 else ""

    return clean_cmd, args


def clean_command(commands: Union[str, List[str]], prefixes: Union[str, List[str]] = ("/", "!", ".")):
    """
    Hem standart hem de @mention ile gelen komutları (/voynat@PixelMuzikBot)
    kesin ve hatasız algılayan, Türkçe karakter duyarlı akıllı Pyrogram filtresi.
    message.command listesini otomatik olarak temizlenmiş komut ve argümanlarla günceller.
    """
    if isinstance(commands, str):
        cmd_list = [tr_lower(commands.lstrip("/!."))]
    else:
        cmd_list = [tr_lower(c.lstrip("/!.")) for c in commands]

    prefix_tuple = tuple(prefixes) if isinstance(prefixes, (list, tuple)) else (prefixes,)

    async def func(flt, client: Client, message: Message) -> bool:
        raw_text = message.text or message.caption
        if not raw_text or not raw_text.strip():
            return False

        text = raw_text.strip()
        if not text.startswith(flt.prefixes):
            return False

        parts = text.split()
        if not parts:
            return False

        # İlk kelimedeki prefix ve @mention kısmını ayır
        first_token = parts[0]
        # Prefix'i kaldır
        cmd_body = first_token.lstrip("/!.")
        # @botusername kısmını ayır
        cmd_name = tr_lower(cmd_body.split("@")[0])

        if cmd_name in flt.cmd_list:
            # message.command özelliğini temizlenmiş haliyle oluştur/doldur
            message.command = [cmd_name] + parts[1:]
            return True

        return False

    return filters.create(func, cmd_list=cmd_list, prefixes=prefix_tuple)


# ── Admin Yetki Kontrolü ─────────────────────────────────────
async def is_admin_user(client: Client, message: Message) -> bool:
    """
    Kullanıcının grupta admin, kurucu veya global yetkili (ADMIN_IDS)
    olup olmadığını Telegram API (get_chat_member) ile sorgular.
    """
    # 1. Özel mesajlarda (DM) daima yetkili kabul edilir
    if message.chat.type == ChatType.PRIVATE:
        return True

    # 2. Anonim Yönetici (Grup adına mesaj atan) kontrolü
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return True

    # 3. Global bot adminleri (bot.config -> ADMIN_IDS)
    user_id = message.from_user.id if message.from_user else 0
    if ADMIN_IDS and user_id in ADMIN_IDS:
        return True

    if not message.from_user:
        return False

    # 4. Telegram grup yetkisi sorgusu (get_chat_member)
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except Exception as e:
        logger.debug(f"is_admin_user sorgu hatası ({message.chat.id}, {user_id}): {e}")
        return False


def admin_only(alert_text: str = "⛔ Bu komut için yetkiniz yok!") -> Callable:
    """
    Komutu yalnızca grup yöneticilerinin veya global adminlerin kullanabilmesini sağlar.
    Yetkisi yoksa kullanıcıya uyarı gönderir.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(client: Client, message: Message, *args: Any, **kwargs: Any) -> Any:
            if not await is_admin_user(client, message):
                display_name = get_user_display_name(message)
                await message.reply_text(f"{alert_text}")
                return None
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator


def check_voice_chat() -> Callable:
    """
    Yayın ve ses kanalı aktifliğini denetleyen esnek dekoratör.
    Kuyrukta aktif parça veya PyTgCalls çağrısı varsa işlemi yürütür.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(client: Client, message: Message, *args: Any, **kwargs: Any) -> Any:
            # 1. Özel mesaj (DM) kontrolü
            if message.chat.type == ChatType.PRIVATE:
                await message.reply_text("❌ Bu komut yalnızca sesli sohbeti olan gruplarda kullanılabilir!")
                return None

            chat_id = message.chat.id
            is_active = False

            # 2. Kuyrukta çalan parça var mı?
            try:
                if await queue.has_current(chat_id):
                    is_active = True
            except Exception:
                pass

            # 3. PyTgCalls üzerinde aktif çağrı var mı?
            if not is_active and call_client:
                try:
                    active_calls = getattr(call_client, "active_calls", None) or getattr(call_client, "calls", None)
                    if active_calls is not None:
                        if isinstance(active_calls, dict) and chat_id in active_calls:
                            is_active = True
                        elif isinstance(active_calls, (list, set, tuple)) and chat_id in active_calls:
                            is_active = True
                except Exception:
                    pass

            # 4. Telegram grup sesli sohbet kontrolü
            if not is_active:
                try:
                    chat = await client.get_chat(chat_id)
                    if (
                        getattr(chat, "is_voice_chat_active", False)
                        or getattr(chat, "has_active_voice_chat", False)
                        or getattr(chat, "active_call", None) is not None
                    ):
                        is_active = True
                except Exception as e:
                    logger.debug(f"check_voice_chat get_chat esnetildi ({chat_id}): {e}")
                    is_active = True

            # 5. Aktif yayın yoksa uyar
            if not is_active:
                await message.reply_text("❌ Şu an sesli sohbette çalan bir yayın bulunmuyor!\n`/play <şarkı adı>` yazarak müzik başlatabilirsiniz. 🐲🔥")
                return None

            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator
