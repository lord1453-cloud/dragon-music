# ============================================
# 🐲 Ejderha Müzik Botu - Otomatik Filtre Sistemi
# ============================================
# Gruplara özel otomatik cevap (filter) ekleme,
# listeleme, silme ve tetikleyici yanıt sistemini yönetir.

import os
import json
import logging
import re
from typing import Optional, Dict

from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus, ChatType

logger = logging.getLogger(__name__)

# ── Dosya Yolları ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FILTERS_FILE = os.path.join(DATA_DIR, "filters.json")


# ── JSON Yardımcı Fonksiyonları ───────────────────────────────
def _load_all_filters() -> dict:
    """Tüm grupların filtrelerini data/filters.json dosyasından okur."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(FILTERS_FILE):
        return {}
    try:
        with open(FILTERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"filters.json okuma hatası: {e}")
        return {}


def _save_all_filters(data: dict):
    """Filtre veritabanını data/filters.json dosyasına kaydeder."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(FILTERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"filters.json yazma hatası: {e}")


def _load_chat_filters(chat_id: int) -> Dict[str, str]:
    """Belirtilen gruba ait filtre sözlüğünü döndürür."""
    all_data = _load_all_filters()
    return all_data.get(str(chat_id), {})


def _save_chat_filter(chat_id: int, keyword: str, reply_text: str):
    """Gruba yeni bir filtre ekler veya mevcut olanı günceller."""
    all_data = _load_all_filters()
    cid = str(chat_id)
    if cid not in all_data:
        all_data[cid] = {}
    all_data[cid][keyword.lower().strip()] = reply_text
    _save_all_filters(all_data)


def _delete_chat_filter(chat_id: int, keyword: str) -> bool:
    """Gruptan belirtilen filtreyi siler."""
    all_data = _load_all_filters()
    cid = str(chat_id)
    kw = keyword.lower().strip()
    if cid in all_data and kw in all_data[cid]:
        del all_data[cid][kw]
        if not all_data[cid]:
            del all_data[cid]
        _save_all_filters(all_data)
        return True
    return False


def _clear_all_chat_filters(chat_id: int) -> bool:
    """Gruptaki tüm filtreleri temizler."""
    all_data = _load_all_filters()
    cid = str(chat_id)
    if cid in all_data:
        del all_data[cid]
        _save_all_filters(all_data)
        return True
    return False


async def _is_admin(client: Client, message: Message) -> bool:
    """Komutu kullanan kişinin grupta yönetici olup olmadığını doğrular."""
    if message.chat.type == ChatType.PRIVATE:
        return True
    try:
        if not message.from_user:
            return False
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except Exception as e:
        logger.debug(f"Admin kontrolü uyarısı: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# 1. FİLTRE EKLEME KOMUTU (/filter, /filtre)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["filter", "filtre"]) & filters.group)
async def add_filter_command(client: Client, message: Message):
    """
    /filter <tetikleyici> <yanıt> veya bir mesaja yanıtlayarak /filter <tetikleyici>
    Grup içinde tetikleyici kelime yazıldığında botun otomatik vereceği cevabı kaydeder.
    """
    if not await _is_admin(client, message):
        await message.reply_text("❌ Filtre ekleme yetkisi yalnızca grup yöneticilerine aittir!")
        return

    args = message.command[1:]

    # Listeleme isteği geldiyse (/filter list)
    if args and args[0].lower() == "list":
        await list_filters_command(client, message)
        return

    keyword = None
    reply_text = None

    # Durum 1: Bir mesaja yanıtlayarak filtre ekleme
    if message.reply_to_message:
        if len(args) < 1:
            await message.reply_text(
                "ℹ️ **Kullanım:** Bir mesajı yanıtlayarak `/filter <tetikleyici>` yazın."
            )
            return
        keyword = args[0].lower().strip()
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        if not reply_text:
            await message.reply_text("❌ Yanıtlanan mesaj metin veya başlık içermelidir!")
            return

    # Durum 2: Doğrudan komutla metin ekleme (/filter <kelime> <yanıt>)
    else:
        if len(args) < 2:
            await message.reply_text(
                "⚙️ **FİLTRE EKLEME KULLANIMI**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 `/filter <tetikleyici> <cevap>`\n\n"
                "**Örnekler:**\n"
                "• `/filter sa Aleyküm Selam, hoş geldin! 🐲👋`\n"
                "• `/filter kurallar Grup kurallarımız: Saygılı olun.`"
            )
            return
        keyword = args[0].lower().strip()
        reply_text = " ".join(args[1:]).strip()

    if not keyword or not reply_text:
        await message.reply_text("❌ Tetikleyici veya cevap boş olamaz!")
        return

    _save_chat_filter(message.chat.id, keyword, reply_text)
    await message.reply_text(
        f"✅ **Filtre Başarıyla Kaydedildi!**\n\n"
        f"🎯 **Tetikleyici:** `{keyword}`\n"
        f"💬 **Cevap:** {reply_text}"
    )


# ══════════════════════════════════════════════════════════════
# 2. FİLTRE SİLME KOMUTU (/stop, /stopfilter, /filtresil)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["stopfilter", "stop", "filtresil", "durdurfiltre"]) & filters.group)
async def stop_filter_command(client: Client, message: Message):
    """
    /stop <tetikleyici> veya /filtresil <tetikleyici>
    Kayıtlı bir filtreyi gruptan kaldırır.
    """
    if not await _is_admin(client, message):
        await message.reply_text("❌ Filtre silme yetkisi yalnızca grup yöneticilerine aittir!")
        return

    if len(message.command) < 2:
        await message.reply_text("ℹ️ **Kullanım:** `/stop <silinecek_tetikleyici>`\nÖrnek: `/stop sa`")
        return

    keyword = message.command[1].lower().strip()
    success = _delete_chat_filter(message.chat.id, keyword)

    if success:
        await message.reply_text(f"🗑️ `{keyword}` filtresi başarıyla silindi.")
    else:
        await message.reply_text(f"❌ Bu grupta `{keyword}` adında aktif bir filtre bulunamadı.")


# ══════════════════════════════════════════════════════════════
# 3. TÜM FİLTRELERİ SİLME KOMUTU (/stopall, /tumfiltrelerisil)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["stopall", "tumfiltrelerisil", "clearfilters"]) & filters.group)
async def stop_all_filters_command(client: Client, message: Message):
    """
    /stopall komutu:
    Gruptaki tüm filtreleri tek seferde temizler.
    """
    if not await _is_admin(client, message):
        await message.reply_text("❌ Bu komutu yalnızca grup yöneticileri kullanabilir!")
        return

    success = _clear_all_chat_filters(message.chat.id)
    if success:
        await message.reply_text("🧹 Gruptaki tüm özel filtreler başarıyla temizlendi.")
    else:
        await message.reply_text("ℹ️ Grupta silinecek herhangi bir filtre bulunamadı.")


# ══════════════════════════════════════════════════════════════
# 4. FİLTRELERİ LİSTELEME KOMUTU (/filters, /filtreler)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["filters", "filtreler"]) & filters.group)
async def list_filters_command(client: Client, message: Message):
    """
    /filters veya /filtreler komutu:
    Grupta kayıtlı olan tüm filtreleri listeler.
    """
    chat_filters = _load_chat_filters(message.chat.id)

    if not chat_filters:
        await message.reply_text(
            "⚙️ **GRUP ÖZEL FİLTRELERİ** ⚙️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Bu grupta henüz eklenmiş bir filtre bulunmuyor.\n\n"
            "➕ **Filtre Eklemek İçin:**\n"
            "`/filter <tetikleyici> <cevap>`"
        )
        return

    filter_lines = []
    for idx, (kw, reply) in enumerate(chat_filters.items(), start=1):
        preview = reply[:35] + ("..." if len(reply) > 35 else "")
        filter_lines.append(f"`{idx}.` **{kw}** ➔ *{preview}*")

    text = (
        f"⚙️ **GRUP ÖZEL FİLTRELERİ ({len(chat_filters)})** ⚙️\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(filter_lines) +
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"➕ **Ekle:** `/filter <kelime> <yanıt>`\n"
        f"➖ **Sil:** `/stop <kelime>`"
    )

    await message.reply_text(text)


# ══════════════════════════════════════════════════════════════
# 5. OTOMATİK CEVAP DİNLEYİCİSİ (Filter Trigger Engine)
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.group & ~filters.bot & ~filters.via_bot, group=15)
async def filter_trigger_handler(client: Client, message: Message):
    """
    Grupta yazılan her mesajı kontrol eder.
    Kayıtlı filtre tetikleyicisiyle eşleşirse otomatik yanıt verir.
    - group=15 ile çalışır, diğer eklentileri engellemez.
    """
    try:
        text = message.text or message.caption
        if not text:
            message.continue_propagation()
            return

        # Komutları tetikleyici olarak işleme
        if text.startswith(("/", "!", ".")):
            message.continue_propagation()
            return

        chat_id = message.chat.id
        chat_filters = _load_chat_filters(chat_id)
        if not chat_filters:
            message.continue_propagation()
            return

        normalized_text = text.lower().strip()
        words = set(re.findall(r"\b\w+\b", normalized_text))

        # 1. Tam eşleşme veya kelime bazlı eşleşme
        matched_reply = None
        for keyword, reply_text in chat_filters.items():
            # Tam metin eşleşmesi veya cümlenin içinde tam kelime eşleşmesi
            if keyword == normalized_text or keyword in words or f" {keyword} " in f" {normalized_text} ":
                matched_reply = reply_text
                break

        if matched_reply:
            await message.reply_text(matched_reply)

    except Exception as e:
        logger.debug(f"Filtre tetikleme hatası: {e}")

    message.continue_propagation()
