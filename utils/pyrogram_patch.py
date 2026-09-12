# ============================================
# 🐲 Ejderha Müzik Botu - Pyrogram Güvenlik Yaması
# ============================================
# Telegram'ın MTProto Layer güncellemeleri ve sunucu kaynaklı
# 500 RPC_CALL_FAIL (channels.GetMessages) hatalarında botun
# 10 kez art arda döngüye girip donmasını (freeze) ve
# Message._parse aşamasında çökmesini (crash) engeller.

import logging
from typing import Iterable, List, Union

from pyrogram import raw, utils
from pyrogram.errors import RPCError
from pyrogram.methods.messages.get_messages import GetMessages
from pyrogram.types.messages_and_media.message import Message

logger = logging.getLogger("EjderhaBot.PyrogramPatch")

# ── 1. Telegram 64-bit Yeni Kanal/Grup ID Yaması ────────────────
try:
    utils.MIN_CHANNEL_ID = -1009999999999
    utils.MAX_CHANNEL_ID = -1000000000000
except Exception:
    pass

# ── 2. GetMessages Otomatik Reply Çözümleme Yaması ──────────────
# Pyrogram normalde her 500 hatasında 10 kez retry yapar ve bu sırada
# bot 30-40 saniye boyunca tamamen donar. reply_to_message_ids sorgusunu
# retries=1 ile sınırlayıp 500 RPC_CALL_FAIL durumunda sessizce None dönüyoruz.
_orig_get_messages = GetMessages.get_messages

async def _safe_get_messages(
    self,
    chat_id: Union[int, str],
    message_ids: Union[int, Iterable[int]] = None,
    reply_to_message_ids: Union[int, Iterable[int]] = None,
    replies: int = 1
):
    if reply_to_message_ids is not None:
        try:
            ids = reply_to_message_ids
            peer = await self.resolve_peer(chat_id)
            is_iterable = not isinstance(ids, int)
            ids_list = list(ids) if is_iterable else [ids]
            input_ids = [raw.types.InputMessageReplyTo(id=i) for i in ids_list]

            replies_count = (1 << 31) - 1 if replies < 0 else replies

            if isinstance(peer, raw.types.InputPeerChannel):
                rpc = raw.functions.channels.GetMessages(channel=peer, id=input_ids)
            else:
                rpc = raw.functions.messages.GetMessages(id=input_ids)

            # retries=1: 10 defa döngüye girip botun donmasını engeller
            r = await self.invoke(rpc, retries=1, sleep_threshold=-1)
            parsed = await utils.parse_messages(self, r, replies=replies_count)
            return parsed if is_iterable else (parsed[0] if parsed else None)
        except RPCError as rpc_err:
            logger.debug(f"Telegram [500 RPC_CALL_FAIL] channels.GetMessages atlandı: {rpc_err}")
            return [] if not isinstance(reply_to_message_ids, int) else None
        except Exception as err:
            logger.debug(f"reply_to_message çözümleme hatası atlandı: {err}")
            return [] if not isinstance(reply_to_message_ids, int) else None

    return await _orig_get_messages(
        self,
        chat_id=chat_id,
        message_ids=message_ids,
        reply_to_message_ids=reply_to_message_ids,
        replies=replies
    )

GetMessages.get_messages = _safe_get_messages

# ── 3. Message._parse Çökme Önleyici Fallback Yaması ─────────────
# Pyrogram Message._parse içinde sadece MessageIdsEmpty bekler;
# RPCError fırlatılırsa dispatcher çöker. Bu yama ile RPCError yakalanır
# ve mesaj replies=0 ile güvenle ayrıştırılarak komutların çalışması sağlanır.
_orig_message_parse = Message._parse

async def _safe_message_parse(client, message, users, chats, is_scheduled: bool = False, replies: int = 1):
    try:
        return await _orig_message_parse(client, message, users, chats, is_scheduled=is_scheduled, replies=replies)
    except RPCError as rpc_err:
        logger.debug(f"Message._parse RPC hatası ({rpc_err}) yakalandı, replies=0 fallback uygulanıyor.")
        try:
            return await _orig_message_parse(client, message, users, chats, is_scheduled=is_scheduled, replies=0)
        except Exception:
            raise rpc_err
    except Exception as exc:
        if replies > 0:
            try:
                return await _orig_message_parse(client, message, users, chats, is_scheduled=is_scheduled, replies=0)
            except Exception:
                pass
        raise exc

Message._parse = _safe_message_parse
logger.info("🛡️ Pyrogram 500 RPC_CALL_FAIL & Donma önleyici yama aktif.")
