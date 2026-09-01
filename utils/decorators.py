# ============================================
# 🐲 Ejderha Müzik Botu - Dekoratörler Modülü
# ============================================
# Komutların çalıştırılmasından önce ses kanalı,
# yetki ve grup kontrollerini gerçekleştiren dekoratörler.

import functools
import logging
from typing import Callable, Any

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ChatType

from bot.clients import call_client

logger = logging.getLogger(__name__)


def check_voice_chat() -> Callable:
    """
    Ses kanalı aktiflik ve bağlantı kontrolü yapan asenkron dekoratör.
    
    Kontrol Mantığı:
    1. Mesajın bir grup veya kanaldan gelip gelmediğini doğrular.
    2. Botun PyTgCalls üzerinde aktif bir görüşmede (call_client.calls / active_calls) olup olmadığını veya
       Telegram grubunda aktif bir sesli sohbet başlatılıp başlatılmadığını kontrol eder.
    3. Sesli sohbet aktif değilse veya bot bağlı değilse işlemi iptal edip kullanıcıyı uyarır.
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

            # 2. PyTgCalls aktif çağrı kontrolü
            try:
                if call_client:
                    active_calls = getattr(call_client, "active_calls", None) or getattr(call_client, "calls", None)
                    if active_calls is not None:
                        if isinstance(active_calls, dict) and chat_id in active_calls:
                            is_active = True
                        elif isinstance(active_calls, (list, set, tuple)) and chat_id in active_calls:
                            is_active = True

                # 3. Telegram Grup Sesli Sohbeti (Group Call) aktiflik kontrolü
                if not is_active:
                    chat = await client.get_chat(chat_id)
                    if (
                        getattr(chat, "is_voice_chat_active", False)
                        or getattr(chat, "has_active_voice_chat", False)
                        or getattr(chat, "active_call", None) is not None
                    ):
                        is_active = True
            except Exception as e:
                logger.debug(f"check_voice_chat kontrol uyarısı ({chat_id}): {e}")
                # Telegram API geçici erişiminde hatayı tolere et
                is_active = False

            # 4. Sesli kanal aktif değilse komutu durdur ve uyar
            if not is_active:
                await message.reply_text("❌ Sesli kanal aktif değil. Önce /join ile bağlan.")
                return None

            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator
