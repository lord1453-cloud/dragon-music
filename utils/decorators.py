# ============================================
# 🐲 Ejderha Müzik Botu - Dekoratörler Modülü
# ============================================
# Kontrol komutlarının (/duraklat, /devam, /gec, /bitir vb.)
# yayın sırasında güvenle çalışmasını denetleyen dekoratör.

import functools
import logging
from typing import Callable, Any

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ChatType

from bot.clients import call_client
from utils.queue_manager import queue

logger = logging.getLogger(__name__)


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
