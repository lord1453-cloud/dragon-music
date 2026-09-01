# ============================================
# 🐲 Ejderha Müzik Botu - Eğlence Plugin'i
# ============================================
# /tokat ve /ship komutlarını işler.
# Şaka amaçlı tokat atma ve aşk/uyum eşleştirmesi yapar.

import random
import hashlib
import logging
from datetime import datetime
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message, User
from pyrogram.enums import ChatType

from bot.theme import msg_error

logger = logging.getLogger(__name__)

# ── Tokat GIF Listesi ──────────────────────────────────────────
SLAP_GIFS = [
    "https://media.giphy.com/media/Gf3AUz3eBNbTW/giphy.gif",
    "https://media.giphy.com/media/jLeyZWgtwWP2U/giphy.gif",
    "https://media.giphy.com/media/alsfZ4y5i53g4qI0mK/giphy.gif",
    "https://media.giphy.com/media/Zau0yrl15oqdK2lT40/giphy.gif",
    "https://media.giphy.com/media/m6etwfPQ3U0vK/giphy.gif",
    "https://media.giphy.com/media/u8mAhlVOkaac8/giphy.gif",
    "https://media.giphy.com/media/tXMPB9cHxUE7NbadYQ/giphy.gif",
    "https://media.giphy.com/media/k1uEYPE77QuEA/giphy.gif",
]

# ── Tokat Mesaj Şablonları ─────────────────────────────────────
SLAP_TEMPLATES = [
    "👋 **{target}**, {sender}'dan sert bir Osmanlı tokadı yedin! 💥",
    "👋 {sender}, **{target}** adlı kullanıcıya havada 360° dönerek tokat attı! 💫",
    "👋 **ÇAAATT!** 💥 {sender}, **{target}**'a unutamayacağı bir tokat yapıştırdı! 🌪️",
    "👋 **{target}**, {sender} öyle bir tokat attı ki ses yan gruptan duyuldu! ⚡",
    "👋 {sender} sinirlerine hakim olamadı ve **{target}**'a ejderha pençeli bir tokat patlattı! 🐲🖐️",
    "👋 **{target}**, {sender}'ın tokatından sonra yörüngeye fırladı! 🚀💥",
]


async def _resolve_user(client: Client, message: Message, query: str) -> Optional[User]:
    """Kullanıcı adı, etiket veya ID'den Pyrogram User nesnesini bulur."""
    query = query.strip().lstrip("@")
    if not query:
        return None
    try:
        user_id_or_uname = int(query) if query.isdigit() else query
        return await client.get_users(user_id_or_uname)
    except Exception as e:
        logger.debug(f"Kullanıcı çözümlenemedi ({query}): {e}")
        return None


async def _get_random_chat_member(client: Client, chat_id: int, exclude_ids: set) -> Optional[User]:
    """Gruptan rastgele bir kullanıcı (bot olmayan) seçer."""
    try:
        members = []
        async for member in client.get_chat_members(chat_id, limit=50):
            user = member.user
            if user and not user.is_bot and user.id not in exclude_ids:
                members.append(user)
        if members:
            return random.choice(members)
    except Exception as e:
        logger.debug(f"Rastgele grup üyesi çekilemedi: {e}")
    return None


# ══════════════════════════════════════════════════════════════
# 1. TOKAT KOMUTU (/tokat, /slap, /samar)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["tokat", "slap", "samar"]))
async def tokat_command(client: Client, message: Message):
    """
    /tokat [@kullanici] veya yanıtlama ile:
    Hedef kullanıcıyı etiketleyerek rastgele bir tokat GIF'i ve mesajı gönderir.
    Hedef belirtilmemişse gruptan rastgele bir üyeyi tokatlar.
    """
    try:
        sender = message.from_user
        sender_mention = sender.mention if sender else "Gizemli Ejderha"
        sender_id = sender.id if sender else 0

        target_user: Optional[User] = None
        target_name: Optional[str] = None

        # 1. Yanıtlanan mesajdan hedef belirle
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user

        # 2. Komut parametresi ile hedef belirle (/tokat @kullanici)
        elif len(message.command) > 1:
            raw_target = message.command[1]
            target_user = await _resolve_user(client, message, raw_target)
            if not target_user:
                target_name = raw_target

        # 3. Parametre yoksa gruptan rastgele birini seç
        elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            target_user = await _get_random_chat_member(client, message.chat.id, exclude_ids={sender_id})

        # 4. Hedef metnini oluştur
        if target_user:
            target_mention = target_user.mention
        elif target_name:
            target_mention = f"@{target_name.lstrip('@')}"
        else:
            # DM veya kimse bulunamadıysa eğlenceli kendi kendine tokat
            target_mention = sender_mention

        # Rastgele tokat mesajı ve GIF seç
        template = random.choice(SLAP_TEMPLATES)
        caption = template.format(sender=sender_mention, target=target_mention)
        gif_url = random.choice(SLAP_GIFS)

        # Animasyon olarak gönder (hata durumunda düz metin fallback)
        try:
            await message.reply_animation(
                animation=gif_url,
                caption=caption,
            )
        except Exception as gif_err:
            logger.warning(f"GIF gönderilemedi ({gif_err}), metin ile yanıt veriliyor...")
            await message.reply_text(caption)

    except Exception as e:
        logger.error(f"/tokat komutu hatası: {e}", exc_info=True)
        await message.reply_text(msg_error("Tokat atılırken beklenmeyen bir hata oluştu."))


# ══════════════════════════════════════════════════════════════
# 2. SHIP / AŞK ÖLÇER KOMUTU (/ship, /cift, /ask, /love)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["ship", "cift", "ask", "love"]))
async def ship_command(client: Client, message: Message):
    """
    /ship [@kullanici1] [@kullanici2] veya yanıtlama ile:
    İki kullanıcı arasındaki aşk ve uyum yüzdesini hesaplar.
    Görsel aşk barı ve ejderha yorumu sunar.
    """
    try:
        sender = message.from_user
        sender_mention = sender.mention if sender else "Sen"
        sender_id = sender.id if sender else 0

        user1_mention: str = sender_mention
        user2_mention: Optional[str] = None

        u1_id = sender_id
        u2_id = 0

        cmd_args = message.command[1:]

        # Durum 1: İki kişi belirtilmiş (/ship @ali @veli)
        if len(cmd_args) >= 2:
            u1 = await _resolve_user(client, message, cmd_args[0])
            u2 = await _resolve_user(client, message, cmd_args[1])
            user1_mention = u1.mention if u1 else f"@{cmd_args[0].lstrip('@')}"
            user2_mention = u2.mention if u2 else f"@{cmd_args[1].lstrip('@')}"
            u1_id = u1.id if u1 else abs(hash(cmd_args[0])) & 0xFFFFFF
            u2_id = u2.id if u2 else abs(hash(cmd_args[1])) & 0xFFFFFF

        # Durum 2: Tek kişi belirtilmiş (/ship @ayse) -> Komutu yazan + Hedef
        elif len(cmd_args) == 1:
            u2 = await _resolve_user(client, message, cmd_args[0])
            user2_mention = u2.mention if u2 else f"@{cmd_args[0].lstrip('@')}"
            u2_id = u2.id if u2 else abs(hash(cmd_args[0])) & 0xFFFFFF

        # Durum 3: Yanıtlanan mesaja /ship yazılmış -> Komutu yazan + Yanıtlanan kişi
        elif message.reply_to_message and message.reply_to_message.from_user:
            u2 = message.reply_to_message.from_user
            user2_mention = u2.mention
            u2_id = u2.id

        # Durum 4: Hiçbir şey belirtilmemişse gruptan rastgele seç
        elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            rand_u1 = await _get_random_chat_member(client, message.chat.id, exclude_ids=set())
            rand_u2 = None
            if rand_u1:
                rand_u2 = await _get_random_chat_member(client, message.chat.id, exclude_ids={rand_u1.id})

            if rand_u1 and rand_u2:
                user1_mention = rand_u1.mention
                user2_mention = rand_u2.mention
                u1_id = rand_u1.id
                u2_id = rand_u2.id
            elif rand_u1:
                user2_mention = rand_u1.mention
                u2_id = rand_u1.id
            else:
                user2_mention = "Ejderha Bot 🐲"
                u2_id = 999999
        else:
            # DM'de parametresiz yazılmışsa bot ile ship'le
            user2_mention = "Ejderha Bot 🐲"
            u2_id = 999999

        if not user2_mention:
            user2_mention = "Ejderha Bot 🐲"
            u2_id = 999999

        # Günlük tutarlı yüzde hesaplama (günde 1 kez değişir)
        today_str = datetime.now().strftime("%Y-%m-%d")
        pair_key = f"{min(u1_id, u2_id)}_{max(u1_id, u2_id)}_{today_str}"
        percent = int(hashlib.md5(pair_key.encode()).hexdigest(), 16) % 101

        # Aşk Barı Görseli (10 segment)
        filled = round(percent / 10)
        empty = 10 - filled
        progress_bar = "█" * filled + "░" * empty

        # Ejderha Yorumu
        if percent <= 20:
            verdict = "💔 **İmkansız Aşk!** Birbirinizi gördüğünüz yerde arkanıza bakmadan kaçın! 🏃‍♂️💨"
        elif percent <= 45:
            verdict = "😐 **İdare Eder...** Arkadaş kalırsanız iki taraf için de daha hayırlı olur."
        elif percent <= 70:
            verdict = "💕 **Tatlı Bir Uyum!** Aranızda güzel bir çekim var, bir kahve için. ☕✨"
        elif percent <= 88:
            verdict = "🔥 **Ateşli Çift!** Tutku ve aşk ejderhanın alevi gibi yükseliyor! 🐉❤️"
        else:
            verdict = "💍 **Efsanevi Ruh İkizleri!** Nikah masası hazır, hemen evlenin! 💒👑"

        # Şık Yanıt Metni
        ship_text = (
            f"💘 **EJDERHA AŞK ÖLÇER (SHIP)** 💘\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **1. Kişi:** {user1_mention}\n"
            f"👤 **2. Kişi:** {user2_mention}\n\n"
            f"📊 **Aşk Uyumu:** `[{progress_bar}] %{percent}`\n"
            f"💬 **Ejderha Yorumu:**\n{verdict}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ *Günün aşk falı ejderha tarafından mühürlendi!*"
        )

        await message.reply_text(ship_text)

    except Exception as e:
        logger.error(f"/ship komutu hatası: {e}", exc_info=True)
        await message.reply_text(msg_error("Aşk uyumu hesaplanırken bir hata oluştu."))
