# ============================================
# 🐲 Ejderha Müzik Botu - Günlük Aktiflik & Liderlik
# ============================================
# Gruptaki mesajları sayar, SQLite veritabanında tamponlu olarak depolar.
# Günlük liderlik tablosunu ve grup analiz raporunu (/gruprapor) listeler.
# 1. olan kullanıcıya "👑 GERÇEK EJDERHA 🐲" ünvanını verir.

import os
import logging
from datetime import datetime
from typing import Optional, Dict

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType

from utils.db import (
    record_user_message,
    get_daily_leaderboard,
    get_group_stats,
)
from utils.decorators import clean_command

logger = logging.getLogger(__name__)


# ── Geriye Dönük Uyumluluk Fonksiyonları ──────────────────────
def _load_daily_stats() -> dict:
    return {}

def _load_user_names() -> Dict[str, str]:
    return {}

def _get_group_stats(chat_id: int, date_str: Optional[str] = None) -> dict:
    return {}


# ══════════════════════════════════════════════════════════════
# 1. MESAJ DİNLEYİCİ (Grup Mesaj Sayacı - Tamponlu SQLite)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.group, group=10)
async def message_counter_handler(client: Client, message: Message):
    """
    Grupta paylaşılan normal mesajları dinler ve sayaç ekler.
    - Komutlar (örneğin '/', '!', '.' ile başlayanlar) sayılmaz.
    - Botların mesajları sayılmaz.
    - Bellek içi tamponda biriktirilir, 5 dakikada bir SQLite'a yazılır (CPU/Disk dostu).
    - group=10 ile çalışır, diğer komut ve eklentilerin çalışmasını engellemez.
    """
    try:
        if not message.from_user or message.from_user.is_bot:
            message.continue_propagation()
            return

        text = (message.text or message.caption or "").strip()
        if not text:
            message.continue_propagation()
            return

        # Komutları hariç tut
        if text.startswith(("/", "!", ".")):
            message.continue_propagation()
            return

        user_id = message.from_user.id
        user_name = message.from_user.first_name or message.from_user.username or f"Kullanıcı_{user_id}"
        username = message.from_user.username
        chat_id = message.chat.id

        await record_user_message(user_id, user_name, chat_id=chat_id, username=username)

    except Exception as e:
        logger.debug(f"Mesaj sayma işleminde uyarı: {e}")

    message.continue_propagation()


# ══════════════════════════════════════════════════════════════
# 2. GÜNLÜK AKTİFLİK LİDERLİK TABLOSU (/mesajlar, /topmesaj, /aktiflik)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["mesajlar", "topmesaj", "aktiflik", "gunluk"]))
async def daily_stats_command(client: Client, message: Message):
    """
    /mesajlar veya /topmesaj komutu:
    Bugün grupta en çok mesaj atan kullanıcıları sıralar.
    Günün 1.'sine '👑 GERÇEK EJDERHA 🐲' ünvanını verir!
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    chat_id = message.chat.id

    leaders = await get_daily_leaderboard(chat_id=chat_id, limit=10)
    gstats = await get_group_stats(chat_id)

    if not leaders:
        await message.reply_text(
            "📊 **GÜNLÜK MESAJ LİDERLİK TABLOSU** 📊\n"
            f"📅 Tarih: `{today_str}`\n\n"
            "💬 Bugün henüz kayıtlı bir mesaj bulunmuyor!\n"
            "Grupta sohbet ederek ilk mesajı siz atın ve **GERÇEK EJDERHA** tahtına oturun! 🐲🔥"
        )
        return

    total_messages = gstats.get("total_messages", 0)
    active_users_count = gstats.get("active_users", len(leaders))

    leaderboard_lines = []
    medals = ["👑", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    champion_name = None
    champion_count = 0

    for idx, item in enumerate(leaders):
        medal = medals[idx] if idx < len(medals) else f"`{idx+1}.`"
        name = item.get("name", "Savaşçı")
        count = item.get("message_count", 0)

        if idx == 0:
            champion_name = name
            champion_count = count
            title_badge = " 🔥 **[GERÇEK EJDERHA]**"
            line = f"{medal} **{name}**{title_badge} — `{count}` mesaj"
        elif idx == 1:
            line = f"{medal} **{name}** *(Gümüş Ejderha)* — `{count}` mesaj"
        elif idx == 2:
            line = f"{medal} **{name}** *(Bronz Ejderha)* — `{count}` mesaj"
        else:
            line = f"{medal} **{name}** — `{count}` mesaj"

        leaderboard_lines.append(line)

    lines_text = "\n".join(leaderboard_lines)

    champion_callout = ""
    if champion_name and champion_count > 0:
        champion_callout = (
            f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👑 **GÜNÜN GERÇEK EJDERHASI:** **{champion_name}** 🐲\n"
            f"🔥 *Bugün tam `{champion_count}` mesajla ejderhanın kalbini alevlendirdi ve tahtın tek sahibi oldu!*"
        )

    response_text = (
        f"🏆 **EJDERHA GÜNLÜK MESAJ LİDERLİK TABLOSU** 🏆\n"
        f"📅 **Tarih:** `{today_str}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{lines_text}"
        f"{champion_callout}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 **Toplam Mesaj:** `{total_messages}` | 👥 **Aktif Üye:** `{active_users_count}`\n"
        f"✨ *Tahtı ele geçirmek için sohbete katılın!*"
    )

    await message.reply_text(response_text)


# ══════════════════════════════════════════════════════════════
# 3. GERÇEK EJDERHA ÖZEL ÜNVAN KOMUTU (/ejderha, /gercekejderha)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["ejderha", "gercekejderha", "kral", "lider"]))
async def real_dragon_command(client: Client, message: Message):
    """
    /ejderha veya /gercekejderha komutu:
    Günün birincisini ilan eden, ona özel fantastik ünvan kartını gönderir.
    """
    chat_id = message.chat.id
    leaders = await get_daily_leaderboard(chat_id=chat_id, limit=1)

    if not leaders:
        await message.reply_text(
            "🐲 **GERÇEK EJDERHA TAHTI BOŞ!** 🐲\n\n"
            "Bugün henüz kimse taht için mücadele etmedi.\n"
            "Grupta mesaj atarak tahtı ilk sen kap: `/mesajlar`"
        )
        return

    top_entry = leaders[0]
    top_name = top_entry.get("name", "Savaşçı")
    top_count = top_entry.get("message_count", 0)

    coronation_text = (
        f"👑━━━━━━━━━━━━━━━━━━━━━━👑\n"
        f"   🐲 **GÜNÜN GERÇEK EJDERHASI** 🐲\n"
        f"👑━━━━━━━━━━━━━━━━━━━━━━👑\n\n"
        f"🔥 **Hükümdar:** **{top_name}**\n"
        f"📜 **Ünvan:** `GERÇEK EJDERHA (THE TRUE DRAGON)`\n"
        f"⚔️ **Bugünkü Mesaj Gücü:** `{top_count}` Mesaj\n\n"
        f"🌋 *'Ateşin efendisi, kelimelerin hükümdarı! Bugün grubun en gürleyen sesi sen oldun. "
        f"Tüm ejderhalar senin önünde saygıyla eğiliyor!'* 🐲✨\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Tüm sıralama için: `/mesajlar`"
    )

    await message.reply_text(coronation_text)


# ══════════════════════════════════════════════════════════════
# 4. GRUP BAZLI DETAYLI ANALİZ RAPORU (/gruprapor, /rapor, /analiz)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["gruprapor", "rapor", "analiz"]))
async def group_report_command(client: Client, message: Message):
    """
    /gruprapor veya /rapor komutu:
    Mevcut grubun günlük mesaj analizi, aktif üye sayısı,
    günün birincisi (Gerçek Ejderha) ve ilk 3 aktif üyeyi listeler.
    Herkese açıktır.
    """
    chat_id = message.chat.id
    chat_title = message.chat.title or "Bu Grup"
    today_str = datetime.now().strftime("%Y-%m-%d")

    leaders = await get_daily_leaderboard(chat_id=chat_id, limit=3)
    gstats = await get_group_stats(chat_id)

    if not leaders:
        await message.reply_text(
            f"📊 **{chat_title.upper()} - GÜNLÜK AKTİFLİK RAPORU** 📊\n"
            f"📅 **Tarih:** `{today_str}`\n\n"
            "💬 Bu grupta bugün henüz kayıtlı mesaj bulunmuyor.\n"
            "Sohbete başlayarak raporu ilk siz hareketlendirin! 🐲🔥"
        )
        return

    total_messages = gstats.get("total_messages", 0)
    active_members_count = gstats.get("active_users", len(leaders))

    # Günün 1.'si
    top_entry = leaders[0]
    champion_name = top_entry.get("name", "Savaşçı")
    top_count = top_entry.get("message_count", 0)

    # İlk 3 aktif üye
    medals = ["🥇", "🥈", "🥉"]
    top3_lines = []
    for idx, item in enumerate(leaders[:3]):
        name = item.get("name", "Savaşçı")
        count = item.get("message_count", 0)
        top3_lines.append(f"{medals[idx]} **{name}** — `{count}` mesaj")

    top3_text = "\n".join(top3_lines)

    # Aktiflik seviyesi değerlendirmesi
    if total_messages > 500:
        level_text = "🔥 **Alev Alev!** Grup ejderhanın nefesi gibi yanıyor!"
    elif total_messages > 100:
        level_text = "⚡ **Çok Canlı!** Grup oldukça aktif ve neşeli."
    else:
        level_text = "🌱 **Isınma Turunda!** Sohbet yavaş yavaş ısınıyor."

    report_text = (
        f"📊 **{chat_title.upper()} — GÜNLÜK GRUP RAPORU** 📊\n"
        f"📅 **Tarih:** `{today_str}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 **Toplam Mesaj:** `{total_messages}`\n"
        f"👥 **Aktif Üye Sayısı:** `{active_members_count}`\n"
        f"👑 **Günün Gerçek Ejderhası:** **{champion_name}** (`{top_count}` mesaj)\n\n"
        f"🏆 **EN AKTİF İLK 3 ÜYE:**\n"
        f"{top3_text}\n\n"
        f"📈 **Grup Durumu:** {level_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ *Detaylı sıralama için: `/mesajlar` | Sosyal menü: `/sosyal`*"
    )

    await message.reply_text(report_text)
