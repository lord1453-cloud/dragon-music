# ============================================
# 🐲 Ejderha Müzik Botu - Eğlence Plugin'i
# ============================================
# /tokat, /slap (Tokat Atma)
# /slapboard, /tokatboard (Tokat Liderlik Tablosu)
# /ship (Aşk & Uyum Ölçer)
# komutlarını yönetir.

import os
import json
import random
import hashlib
import logging
from datetime import datetime
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message, User
from pyrogram.enums import ChatType

from bot.theme import msg_error

logger = logging.getLogger(__name__)

# ── İstatistik Dosyası Yolu ───────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
STATS_FILE = os.path.join(DATA_DIR, "slap_stats.json")

# ── Çalışan 15 Adet Sabit Tokat GIF Listesi ───────────────────
SLAP_GIFS = [
    "https://media.giphy.com/media/Gf3AUz3eBNbTW/giphy.gif",
    "https://media.giphy.com/media/jLeyZWgtwWP2U/giphy.gif",
    "https://media.giphy.com/media/alsfZ4y5i53g4qI0mK/giphy.gif",
    "https://media.giphy.com/media/Zau0yrl15oqdK2lT40/giphy.gif",
    "https://media.giphy.com/media/m6etwfPQ3U0vK/giphy.gif",
    "https://media.giphy.com/media/u8mAhlVOkaac8/giphy.gif",
    "https://media.giphy.com/media/tXMPB9cHxUE7NbadYQ/giphy.gif",
    "https://media.giphy.com/media/k1uEYPE77QuEA/giphy.gif",
    "https://media1.tenor.com/m/Ws6Dm1ZW_vMAAAAC/girl-slap.gif",
    "https://media1.tenor.com/m/CvBTA0GyrogAAAAC/anime-slap.gif",
    "https://media1.tenor.com/m/iDdSBScLKGMAAAAC/slap-handa-seishuu.gif",
    "https://media1.tenor.com/m/FJsjkKNrfg8AAAAC/peanuts-slap.gif",
    "https://media1.tenor.com/m/XnbfxP0bV_0AAAAC/slap-batman.gif",
    "https://media1.tenor.com/m/o6V_K_D_bU0AAAAC/tom-and-jerry-slap.gif",
    "https://media1.tenor.com/m/rVXByOZcwqsAAAAC/anime-slap.gif",
]

# ── Tokat Mesaj Şablonları ─────────────────────────────────────
SLAP_TEMPLATES = [
    "👋 **{target}**, {sender}'dan sert bir Osmanlı tokadı yedin! 💥",
    "👋 {sender}, **{target}** adlı kullanıcıya havada 360° dönerek tokat attı! 💫",
    "👋 **ÇAAATT!** 💥 {sender}, **{target}**'a unutamayacağı bir tokat yapıştırdı! 🌪️",
    "👋 **{target}**, {sender} öyle bir tokat attı ki ses yan gruptan duyuldu! ⚡",
    "👋 {sender} sinirlerine hakim olamadı ve **{target}**'a ejderha pençeli bir tokat patlattı! 🐲🖐️",
    "👋 **{target}**, {sender}'ın tokatından sonra yörüngeye fırladı! 🚀💥",
    "👋 **ŞIRRAAK!** 🖐️ {sender}, **{target}**'ın yanağına beşparmak imzasını attı! 🔥",
    "👋 {sender}, **{target}**'a ışık hızında bir tokat indirdi! ⚡😵",
]


# ── JSON İstatistik Yardımcı Fonksiyonları ────────────────────
def _load_slap_stats() -> dict:
    """slap_stats.json dosyasından istatistikleri güvenli şekilde okur."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Tokat istatistikleri okuma hatası: {e}")
        return {}


def _save_slap_stats(stats: dict):
    """İstatistikleri slap_stats.json dosyasına kaydeder."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Tokat istatistikleri yazma hatası: {e}")


def _update_slap_stat(sender_id: int, sender_name: str, target_id: int, target_name: str):
    """Atılan ve yenilen tokat sayılarını günceller."""
    stats = _load_slap_stats()
    today_str = datetime.now().strftime("%Y-%m-%d")

    s_id = str(sender_id)
    t_id = str(target_id)

    # Tokat atanın istatistiğini güncelle
    if s_id not in stats:
        stats[s_id] = {"isim": sender_name, "attı": 0, "yedi": 0, "son_tokat": today_str}
    stats[s_id]["attı"] = stats[s_id].get("attı", 0) + 1
    stats[s_id]["isim"] = sender_name
    stats[s_id]["son_tokat"] = today_str

    # Tokat yiyenin istatistiğini güncelle
    if t_id not in stats:
        stats[t_id] = {"isim": target_name, "attı": 0, "yedi": 0, "son_tokat": today_str}
    stats[t_id]["yedi"] = stats[t_id].get("yedi", 0) + 1
    stats[t_id]["isim"] = target_name
    stats[t_id]["son_tokat"] = today_str

    _save_slap_stats(stats)


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
# 1. TOKAT ATMA KOMUTU (/slap, /tokat, /samar)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["slap", "tokat", "samar"]))
async def tokat_command(client: Client, message: Message):
    """
    /slap [@kullanici] veya yanıtlama ile:
    Hedef kullanıcıyı tokatlar, 15 çalışan GIF'ten birini gönderir
    ve JSON veritabanında tokat istatistiklerini günceller.
    """
    try:
        sender = message.from_user
        sender_name = sender.first_name if sender else "Gizemli Ejderha"
        sender_mention = sender.mention if sender else "Gizemli Ejderha"
        sender_id = sender.id if sender else 0

        target_user: Optional[User] = None
        target_name: Optional[str] = None
        target_id: int = 0

        # 1. Yanıtlanan mesajdan hedef belirle
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user
            target_name = target_user.first_name
            target_id = target_user.id

        # 2. Komut parametresi ile hedef belirle (/slap @kullanici)
        elif len(message.command) > 1:
            raw_target = message.command[1]
            target_user = await _resolve_user(client, message, raw_target)
            if target_user:
                target_name = target_user.first_name
                target_id = target_user.id
            else:
                target_name = raw_target
                target_id = abs(hash(raw_target)) & 0xFFFFFF

        # 3. Parametre yoksa gruptan rastgele birini seç
        elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            target_user = await _get_random_chat_member(client, message.chat.id, exclude_ids={sender_id})
            if target_user:
                target_name = target_user.first_name
                target_id = target_user.id

        # 4. Hedef metnini oluştur
        if target_user:
            target_mention = target_user.mention
        elif target_name:
            target_mention = f"@{target_name.lstrip('@')}"
        else:
            # DM veya kimse bulunamadıysa kendine tokat
            target_mention = sender_mention
            target_name = sender_name
            target_id = sender_id

        # İstatistikleri güncelle
        if sender_id and target_id:
            _update_slap_stat(sender_id, sender_name, target_id, target_name)

        # Rastgele tokat mesajı ve GIF seç
        template = random.choice(SLAP_TEMPLATES)
        caption = template.format(sender=sender_mention, target=target_mention)
        gif_url = random.choice(SLAP_GIFS)

        # Animasyon olarak gönder (hata durumunda düz metin)
        try:
            await message.reply_animation(
                animation=gif_url,
                caption=caption,
            )
        except Exception as gif_err:
            logger.warning(f"GIF gönderilemedi ({gif_err}), metin ile yanıt veriliyor...")
            await message.reply_text(caption)

    except Exception as e:
        logger.error(f"/slap komutu hatası: {e}", exc_info=True)
        await message.reply_text(msg_error("Tokat atılırken beklenmeyen bir hata oluştu."))


# ══════════════════════════════════════════════════════════════
# 2. TOKAT LİDERLİK TABLOSU (/slapboard, /tokatboard, /tokattablosu)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["slapboard", "tokatboard", "tokattablosu", "tokatsiralama"]))
async def slapboard_command(client: Client, message: Message):
    """
    /slapboard veya /tokatboard komutu:
    Grupta en çok tokat atanları ve en çok tokat yiyenleri
    data/slap_stats.json dosyasından okuyarak liderlik tablosu olarak sunar.
    """
    stats = _load_slap_stats()
    if not stats:
        await message.reply_text(
            "🥊 **TOKAT LİDERLİK TABLOSU** 🥊\n\n"
            "Henüz kimse tokat atmadı! İlk tokadı sen patlat:\n"
            "👉 `/slap` veya `/slap @kullanıcı`"
        )
        return

    # En çok tokat atanlar (Top 5)
    top_givers = sorted(
        stats.items(),
        key=lambda item: item[1].get("attı", 0),
        reverse=True
    )[:5]

    # En çok tokat yiyenler (Top 5)
    top_receivers = sorted(
        stats.items(),
        key=lambda item: item[1].get("yedi", 0),
        reverse=True
    )[:5]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    # Atanlar metni
    givers_text = ""
    for idx, (uid, data) in enumerate(top_givers):
        count = data.get("attı", 0)
        if count > 0:
            name = data.get("isim", f"Kullanıcı_{uid}")
            givers_text += f"{medals[idx]} **{name}** — `{count}` tokat\n"
    if not givers_text:
        givers_text = "Henüz tokat atan yok.\n"

    # Yiyenler metni
    receivers_text = ""
    for idx, (uid, data) in enumerate(top_receivers):
        count = data.get("yedi", 0)
        if count > 0:
            name = data.get("isim", f"Kullanıcı_{uid}")
            receivers_text += f"{medals[idx]} **{name}** — `{count}` tokat\n"
    if not receivers_text:
        receivers_text = "Henüz tokat yiyen yok.\n"

    total_slaps = sum(d.get("attı", 0) for d in stats.values())

    board_text = (
        "🏆 **EJDERHA TOKAT LİDERLİK TABLOSU** 🏆\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🥊 **EN ÇOK TOKAT ATANLAR (Top Tokatçılar):**\n"
        f"{givers_text}\n"
        "🤕 **EN ÇOK TOKAT YİYENLER (Grup Mağdurları):**\n"
        f"{receivers_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💥 **Toplam Atılan Tokat:** `{total_slaps}`\n"
        "✨ *Sıralamaya girmek için sen de birini tokatla: `/slap`*"
    )

    await message.reply_text(board_text)


# ══════════════════════════════════════════════════════════════
# 3. SHIP / AŞK ÖLÇER KOMUTU (/ship, /cift, /ask, /love)
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
