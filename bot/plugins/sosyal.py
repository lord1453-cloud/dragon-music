# ============================================
# 🐲 Ejderha Müzik Botu - Sosyal Menü Modülü
# ============================================
# /sosyal komutu ile interaktif eğlence, aktiflik,
# tokat, aşk ölçer, filtre ve grup raporu menüsünü sunar.

import logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.enums import ParseMode

from bot.plugins.activity import (
    _load_daily_stats,
    _load_user_names,
    _get_group_stats,
)
from bot.plugins.fun import _load_slap_stats

logger = logging.getLogger(__name__)

# ── Sosyal Menü Metni ─────────────────────────────────────────
SOSYAL_MENU_TEXT = """
🐲 **EJDERHA SOSYAL & EĞLENCE MERKEZİ** 🐲
━━━━━━━━━━━━━━━━━━━━━━━━
Aşağıdaki eğlence ve topluluk komutlarıyla grubunuzu canlandırın:

🥊 **TOKAT SİSTEMİ:**
• `/slap [@kullanıcı]` — Hedefe GIF'li Osmanlı tokadı patlatır!
• `/slapboard` — En çok tokat atan ve yiyenlerin liderlik tablosu.

📊 **AKTİFLİK & GRUP ANALİZİ:**
• `/mesajlar` — Günün mesaj kralları liderlik sıralaması.
• `/gruprapor` — Bu grubun detaylı mesaj ve aktiflik raporu.
• `/ejderha` — Günün birincisi **👑 GERÇEK EJDERHA** ünvan kartı.

💘 **AŞK & EĞLENCE:**
• `/ship [@kullanıcı1] [@kullanıcı2]` — Aşk ve uyum falı ölçer.

⚙️ **ÖZEL FİLTRELER:**
• `/filter <kelime> <yanıt>` — Otomatik cevap filtresi ekler.
• `/stop <kelime>` — Filtreyi siler.
• `/filters` — Gruptaki tüm filtreleri listeler.
━━━━━━━━━━━━━━━━━━━━━━━━
✨ *Butonlara tıklayarak doğrudan işlem yapabilirsiniz:*
"""


def get_sosyal_keyboard() -> InlineKeyboardMarkup:
    """Sosyal menü için zengin ve interaktif buton takımı."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🥊 Tokat At", switch_inline_query_current_chat="/slap "),
                InlineKeyboardButton("🏆 Tokat Lideri", callback_data="sosyal_slapboard"),
            ],
            [
                InlineKeyboardButton("📊 Mesaj Kralları", callback_data="sosyal_mesajlar"),
                InlineKeyboardButton("👑 Gerçek Ejderha", callback_data="sosyal_ejderha"),
            ],
            [
                InlineKeyboardButton("📈 Grup Raporu", callback_data="sosyal_gruprapor"),
                InlineKeyboardButton("⚙️ Filtreler", callback_data="sosyal_filters"),
            ],
            [
                InlineKeyboardButton("💘 Aşk Ölçer", switch_inline_query_current_chat="/ship "),
                InlineKeyboardButton("🔄 Menüyü Yenile", callback_data="sosyal_refresh"),
            ],
        ]
    )


# ── /sosyal Komutu ─────────────────────────────────────────────
@Client.on_message(filters.command(["sosyal", "social", "eglence"]))
async def sosyal_command(client: Client, message: Message):
    """
    /sosyal veya /eglence komutu:
    Grup veya özel sohbette zengin Sosyal Menüyü butonlarla birlikte açar.
    """
    try:
        await message.reply_text(
            text=SOSYAL_MENU_TEXT,
            reply_markup=get_sosyal_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"/sosyal komut hatası: {e}")
        await message.reply_text(SOSYAL_MENU_TEXT, reply_markup=get_sosyal_keyboard())


# ── Sosyal Callback Dinleyicisi ───────────────────────────────
@Client.on_callback_query(filters.regex(r"^sosyal_"))
async def sosyal_callback_handler(client: Client, callback: CallbackQuery):
    """Sosyal menü buton tıklamalarını yönetir."""
    data = callback.data
    chat_id = callback.message.chat.id

    try:
        if data == "sosyal_refresh":
            await callback.message.edit_text(
                text=SOSYAL_MENU_TEXT,
                reply_markup=get_sosyal_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
            await callback.answer("🔄 Menü güncellendi!")
            return

        elif data == "sosyal_gruprapor":
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            chat_title = callback.message.chat.title or "Bu Grup"
            group_data = _get_group_stats(chat_id, today_str)
            names = _load_user_names()

            if not group_data:
                await callback.answer("💬 Bu grupta bugün henüz kayıtlı mesaj yok!", show_alert=True)
                return

            sorted_users = sorted(group_data.items(), key=lambda item: item[1], reverse=True)
            total_messages = sum(group_data.values())
            active_members = len(group_data)

            top_uid, top_count = sorted_users[0]
            champion_name = names.get(top_uid, f"Kullanıcı_{top_uid}")

            medals = ["🥇", "🥈", "🥉"]
            top3_lines = []
            for idx in range(min(3, len(sorted_users))):
                uid, count = sorted_users[idx]
                name = names.get(uid, f"Kullanıcı_{uid}")
                top3_lines.append(f"{medals[idx]} **{name}** — `{count}` mesaj")

            out_text = (
                f"📊 **{chat_title.upper()} — GÜNLÜK GRUP RAPORU** 📊\n"
                f"📅 **Tarih:** `{today_str}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💬 **Toplam Mesaj:** `{total_messages}`\n"
                f"👥 **Aktif Üye:** `{active_members}`\n"
                f"👑 **Günün Gerçek Ejderhası:** **{champion_name}** (`{top_count}` mesaj)\n\n"
                f"🏆 **EN AKTİF İLK 3 ÜYE:**\n"
                + "\n".join(top3_lines) +
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ *Detaylı liste için: `/mesajlar`*"
            )

            back_kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")]]
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb, parse_mode=ParseMode.MARKDOWN)
            await callback.answer()

        elif data == "sosyal_mesajlar":
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            group_data = _get_group_stats(chat_id, today_str)
            names = _load_user_names()

            if not group_data:
                await callback.answer("💬 Bugün henüz kayıtlı mesaj yok!", show_alert=True)
                return

            sorted_users = sorted(group_data.items(), key=lambda item: item[1], reverse=True)
            medals = ["👑", "🥈", "🥉", "4️⃣", "5️⃣"]
            lines = []
            for idx, (uid, count) in enumerate(sorted_users[:5]):
                m = medals[idx] if idx < len(medals) else f"`{idx+1}.`"
                n = names.get(uid, f"Kullanıcı_{uid}")
                tag = " 🔥[GERÇEK EJDERHA]" if idx == 0 else ""
                lines.append(f"{m} **{n}**{tag} — `{count}` mesaj")

            out_text = (
                f"📊 **GÜNLÜK MESAJ KRALLARI** 📊\n"
                f"📅 Tarih: `{today_str}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                + "\n".join(lines) +
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 Günün Lideri: **{names.get(sorted_users[0][0], 'Ejderha')}**"
            )

            back_kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")]]
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb, parse_mode=ParseMode.MARKDOWN)
            await callback.answer()

        elif data == "sosyal_slapboard":
            slap_stats = _load_slap_stats()
            if not slap_stats:
                await callback.answer("🥊 Henüz kimse tokat atmadı!", show_alert=True)
                return

            top_givers = sorted(slap_stats.items(), key=lambda i: i[1].get("attı", 0), reverse=True)[:3]
            top_receivers = sorted(slap_stats.items(), key=lambda i: i[1].get("yedi", 0), reverse=True)[:3]

            givers_txt = "\n".join([f"🥇 **{d.get('isim')}** — `{d.get('attı')}` tokat" for _, d in top_givers if d.get("attı", 0) > 0]) or "Yok"
            receivers_txt = "\n".join([f"🤕 **{d.get('isim')}** — `{d.get('yedi')}` tokat" for _, d in top_receivers if d.get("yedi", 0) > 0]) or "Yok"

            out_text = (
                f"🏆 **TOKAT LİDERLİK TABLOSU** 🏆\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🥊 **Top Tokatçılar:**\n{givers_txt}\n\n"
                f"🤕 **Top Tokat Yiyenler:**\n{receivers_txt}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ `/slap` yazarak sıralamaya girebilirsiniz!"
            )

            back_kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")]]
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb, parse_mode=ParseMode.MARKDOWN)
            await callback.answer()

        elif data == "sosyal_ejderha":
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            group_data = _get_group_stats(chat_id, today_str)
            names = _load_user_names()

            if not group_data:
                await callback.answer("🐲 Bugün henüz taht sahibi yok!", show_alert=True)
                return

            sorted_users = sorted(group_data.items(), key=lambda item: item[1], reverse=True)
            top_uid, top_count = sorted_users[0]
            top_name = names.get(top_uid, f"Kullanıcı_{top_uid}")

            out_text = (
                f"👑━━━━━━━━━━━━━━━━━━━━━━👑\n"
                f"   🐲 **GÜNÜN GERÇEK EJDERHASI** 🐲\n"
                f"👑━━━━━━━━━━━━━━━━━━━━━━👑\n\n"
                f"🔥 **Hükümdar:** **{top_name}**\n"
                f"📜 **Ünvan:** `GERÇEK EJDERHA (THE TRUE DRAGON)`\n"
                f"⚔️ **Mesaj Sayısı:** `{top_count}` Mesaj\n\n"
                f"🌋 *'Bugün grubun alevini en güçlü şekilde yakan hükümdar!'* 🐲✨"
            )

            back_kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")]]
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb, parse_mode=ParseMode.MARKDOWN)
            await callback.answer()

        elif data == "sosyal_filters":
            from bot.plugins.filters import _load_chat_filters
            chat_filters = _load_chat_filters(chat_id)

            if not chat_filters:
                filter_list_text = "Bu grupta henüz eklenmiş özel filtre yok.\n\nEkleme formatı:\n`/filter <kelime> <yanıt>`"
            else:
                filter_list_text = "\n".join([f"• `{k}`" for k in chat_filters.keys()])

            out_text = (
                f"⚙️ **GRUP ÖZEL FİLTRELERİ** ⚙️\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{filter_list_text}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"➕ **Ekleme:** `/filter <tetikleyici> <cevap>`\n"
                f"➖ **Silme:** `/stop <tetikleyici>`"
            )

            back_kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")]]
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb, parse_mode=ParseMode.MARKDOWN)
            await callback.answer()

    except Exception as e:
        logger.error(f"sosyal_callback hatası: {e}")
        try:
            await callback.answer(f"Hata: {e}", show_alert=True)
        except Exception:
            pass
