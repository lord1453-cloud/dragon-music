# ============================================
# 🐲 Ejderha Müzik Botu - Günlük Aktiflik & Liderlik
# ============================================
# Gruptaki mesajları sayar, data/daily_stats.json dosyasına kaydeder.
# Günlük liderlik tablosunu listeler ve 1. olan kullanıcıya
# "👑 GERÇEK EJDERHA 🐲" ünvanını verir.

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType

logger = logging.getLogger(__name__)

# ── Dosya Yolları ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DAILY_STATS_FILE = os.path.join(DATA_DIR, "daily_stats.json")
USER_NAMES_FILE = os.path.join(DATA_DIR, "user_names.json")


# ── JSON Okuma ve Yazma Yardımcıları ─────────────────────────
def _load_daily_stats() -> dict:
    """data/daily_stats.json dosyasını güvenli şekilde yükler."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DAILY_STATS_FILE):
        return {}
    try:
        with open(DAILY_STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"daily_stats.json okuma hatası: {e}")
        return {}


def _save_daily_stats(stats: dict):
    """Günlük mesaj istatistiklerini data/daily_stats.json dosyasına yazar."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(DAILY_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"daily_stats.json yazma hatası: {e}")


def _load_user_names() -> Dict[str, str]:
    """Kullanıcı ID -> İsim eşleme tablosunu okur."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USER_NAMES_FILE):
        return {}
    try:
        with open(USER_NAMES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"user_names.json okuma hatası: {e}")
        return {}


def _save_user_names(names: dict):
    """Kullanıcı ID -> İsim eşleme tablosunu kaydeder."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(USER_NAMES_FILE, "w", encoding="utf-8") as f:
            json.dump(names, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"user_names.json yazma hatası: {e}")


def _increment_user_message(user_id: int, user_name: str):
    """
    Belirtilen kullanıcının bugünkü mesaj sayısını 1 artırır
    ve JSON dosyasına kaydeder.
    """
    stats = _load_daily_stats()
    today_str = datetime.now().strftime("%Y-%m-%d")
    uid_str = str(user_id)

    # Günlük sözlüğü oluştur
    if today_str not in stats:
        stats[today_str] = {}

    # Mesaj sayısını artır
    stats[today_str][uid_str] = stats[today_str].get(uid_str, 0) + 1
    _save_daily_stats(stats)

    # Kullanıcı adını güncelle
    if user_name:
        names = _load_user_names()
        if names.get(uid_str) != user_name:
            names[uid_str] = user_name
            _save_user_names(names)


# ══════════════════════════════════════════════════════════════
# 1. MESAJ DİNLEYİCİ (Grup Mesaj Sayacı)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.group, group=10)
async def message_counter_handler(client: Client, message: Message):
    """
    Grupta paylaşılan normal mesajları dinler ve sayaç ekler.
    - Komutlar (örneğin '/', '!', '.' ile başlayanlar) sayılmaz.
    - Botların mesajları sayılmaz.
    - group=10 ile çalışır, diğer komut ve eklentilerin çalışmasını engellemez.
    """
    try:
        # Bot veya bilinmeyen kullanıcıları sayma
        if not message.from_user or message.from_user.is_bot:
            message.continue_propagation()
            return

        text = message.text or message.caption or ""

        # Komutları hariç tut (/, !, . ile başlayan mesajlar komuttur)
        if text.startswith(("/", "!", ".")):
            message.continue_propagation()
            return

        # Kullanıcı bilgilerini al
        user_id = message.from_user.id
        user_name = message.from_user.first_name or message.from_user.username or f"Kullanıcı_{user_id}"

        # Mesajı sayaca ekle
        _increment_user_message(user_id, user_name)

    except Exception as e:
        logger.debug(f"Mesaj sayma işleminde uyarı: {e}")

    # Mesajın diğer komutlara ve eklentilere akmaya devam etmesini sağla
    message.continue_propagation()


# ══════════════════════════════════════════════════════════════
# 2. GÜNLÜK AKTİFLİK LİDERLİK TABLOSU (/mesajlar, /topmesaj, /aktiflik)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["mesajlar", "topmesaj", "aktiflik", "gunluk", "top"]))
async def daily_stats_command(client: Client, message: Message):
    """
    /mesajlar veya /topmesaj komutu:
    Bugün grupta en çok mesaj atan kullanıcıları sıralar.
    Günün 1.'sine '👑 GERÇEK EJDERHA 🐲' ünvanını verir!
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    stats = _load_daily_stats()
    today_data: dict = stats.get(today_str, {})

    if not today_data:
        await message.reply_text(
            "📊 **GÜNLÜK MESAJ LİDERLİK TABLOSU** 📊\n"
            f"📅 Tarih: `{today_str}`\n\n"
            "💬 Bugün henüz kayıtlı bir mesaj bulunmuyor!\n"
            "Grupta sohbet ederek ilk mesajı siz atın ve **GERÇEK EJDERHA** tahtına oturun! 🐲🔥"
        )
        return

    # Kullanıcı adlarını çek
    names = _load_user_names()

    # Mesaj sayısına göre çoktan aza sırala
    sorted_users = sorted(
        today_data.items(),
        key=lambda item: item[1],
        reverse=True
    )

    total_messages = sum(today_data.values())
    active_users_count = len(today_data)

    # Sıralama metni oluştur
    leaderboard_lines = []
    medals = ["👑", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    champion_id = None
    champion_name = None
    champion_count = 0

    for idx, (uid, count) in enumerate(sorted_users[:10]):
        medal = medals[idx] if idx < len(medals) else f"`{idx+1}.`"
        name = names.get(uid, f"Kullanıcı_{uid}")

        if idx == 0:
            champion_id = uid
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

    # 1. Olan Gerçek Ejderha için özel taçlandırma mesajı
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
@Client.on_message(filters.command(["ejderha", "gercekejderha", "kral", "lider"]))
async def real_dragon_command(client: Client, message: Message):
    """
    /ejderha veya /gercekejderha komutu:
    Günün birincisini ilan eden, ona özel fantastik ünvan kartını gönderir.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    stats = _load_daily_stats()
    today_data: dict = stats.get(today_str, {})

    if not today_data:
        await message.reply_text(
            "🐲 **GERÇEK EJDERHA TAHTI BOŞ!** 🐲\n\n"
            "Bugün henüz kimse taht için mücadele etmedi.\n"
            "Grupta mesaj atarak tahtı ilk sen kap: `/mesajlar`"
        )
        return

    names = _load_user_names()
    sorted_users = sorted(today_data.items(), key=lambda item: item[1], reverse=True)
    top_uid, top_count = sorted_users[0]
    top_name = names.get(top_uid, f"Kullanıcı_{top_uid}")

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
