# ============================================
# 🐲 Ejderha Müzik Botu - Zengin Sosyal & Eğlence Modülü
# ============================================
# /sosyal menüsü, zar atma, kahve falı, şans ölçer,
# fıkra, şiir, hayvan GIF'leri, yıldız falı ve iltifat komutları.
# Tüm komutlar hareketli ve çalışan GIF'lerle zenginleştirilmiştir.

import os
import random
import logging
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.enums import ParseMode

from utils.db import get_daily_leaderboard, get_group_stats

logger = logging.getLogger(__name__)


# ── ÇALIŞAN SABİT GIF VE ANİMASYON CDN LİNKLERİ ──────────────
GIFS = {
    "dice": "https://media.giphy.com/media/3oriO04qxVReM5rJEA/giphy.gif",
    "coffee": "https://media.giphy.com/media/3oriO13KTkzPwTykp2/giphy.gif",
    "luck": "https://media.giphy.com/media/l41JGlwa1xY7Btxfs/giphy.gif",
    "joke": "https://media.giphy.com/media/10JhviFuU2gWD6/giphy.gif",
    "poetry": "https://media.giphy.com/media/26FPy3QZLnLCy5Ip2/giphy.gif",
    "weather_sun": "https://media.giphy.com/media/u01ioCe6G8URG/giphy.gif",
    "weather_rain": "https://media.giphy.com/media/t7Qb8655Z1V9K/giphy.gif",
    "star": "https://media.giphy.com/media/xT9IgzoKnwFNmISR8I/giphy.gif",
    "compliment": "https://media.giphy.com/media/M90mJvfWfd5mbUuULX/giphy.gif",
    "hug": "https://media.giphy.com/media/u9BxQbM5bxvwY/giphy.gif",
    "kiss": "https://media.giphy.com/media/G3va31oEEnIkM/giphy.gif",
    "dance": "https://media.giphy.com/media/blSTtZehjAZ8I/giphy.gif",
    "cry": "https://media.giphy.com/media/L95W4wv8nnb9K/giphy.gif",
    "party": "https://media.giphy.com/media/artj92V8o75VPL7AeQ/giphy.gif",
    "animals": [
        ("🐈 **Mırmır Kedi**", "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif"),
        ("🐕 **Neşeli Köpecik**", "https://media.giphy.com/media/4Zo41lhzKt6iZ8xff9/giphy.gif"),
        ("🐼 **Tembel Panda**", "https://media.giphy.com/media/EatwJZRUIv41G/giphy.gif"),
        ("🦊 **Akıllı Tilki**", "https://media.giphy.com/media/cno2xVuF567FVoEZMQ/giphy.gif"),
        ("🦦 **Sevimli Su Samuru**", "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOHY5bTFrb2x5Y3BxeDZ2OXh2czA0MDFnNTI4NmVtc3J3M2syc3FiaSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7TKMt1VVNkHV2PaE/giphy.gif"),
        ("🐧 **Minik Penguen**", "https://media.giphy.com/media/OJac5MRF6xsp2/giphy.gif"),
        ("🦥 **Keyifli Tembel Hayvan**", "https://media.giphy.com/media/d90e0cOHb56xW604g5/giphy.gif"),
    ]
}



# ── EĞLENCELİ VERİ HAVUZLARI ─────────────────────────────────
KAHVE_FALLARI = [
    "☕ **Fincanında bir ejderha silüeti belirdi!** Yakın zamanda grubunda büyük bir liderlik veya başarı elde edeceksin.",
    "☕ **Yolun açık görünüyor!** Önünde 3 vakte kadar çok sevineceğin bir müzik veya sohbet haberi var.",
    "☕ **Kısmetin kapıda!** Fincanın dibinde bir kalp ve bol neşe var, sevdiğin birinden mesaj alabilirsin.",
    "☕ **Göz var üzerinde!** Grup arkadaşların senin enerjine ve neşene hayran kalmış durumda.",
    "☕ **Büyük bir sürpriz yolda!** Beklemediğin bir anda keyifli bir dost meclisi toplanacak.",
]

FIKRALAR = [
    "🎭 **Temel ile Dursun:**\nTemel bir gün gökyüzüne bakarken Dursun sormuş:\n— Ula Temel, Ay mı daha uzak yoksa Trabzon mu?\nTemel gülmüş:\n— Ula Dursun, Ay'ı buradan görebiliyorsun ama Trabzon'u göremiyorsun, tabii ki Trabzon daha uzak! 😂",
    "🎭 **Nasreddin Hoca ve Kazan:**\nHoca komşusundan kazan almış, geri verirken içine tencere koymuş: 'Kazan doğurdu!' demiş. Bir gün kazanı tekrar alıp geri getirmeyince komşu sormuş. Hoca: 'Senin kazan öldü!' demiş. Komşu: 'Hoca kazan ölür mü?' deyince Hoca:\n— Doğurduğuna inanıyordun da öldüğüne niye inanmıyorsun? 🤣",
    "🎭 **Papağan ve Kaptan:**\nSihirbaz gemide gösteri yaparken ne kaybetse papağan hemen bağırıyormuş:\n— 'Numara numara! Masanın altında!'\nBir gün gemi batmış, sihirbaz ile papağan kalasın üzerinde kalmış. Papağan 3 gün sessizce bakıp sonunda demiş:\n— 'Tamam pes, gemiyi nereye sakladın?' 😆",
]

SIIRLER = [
    "📜 *'Ağlasam sesimi duyar mısınız mısralarımda?*\n*Dokunabilir misiniz gözyaşlarıma ellerinizle?*\n*Bilmeyenler beni divane sanır...'* — **Orhan Veli**",
    "📜 *'Seni sevmek, gökyüzünde kanat çırpan bir ejderhanın ateşi gibi...*\n*Ne söner ne küllenir, daima aydınlatır geceyi.'* — **Ejderha Şiirleri**",
    "📜 *'Gözlerin bir çığlık, bir yaralı haykırış...*\n*Gözlerin bu gece çok uzaktan geçen bir gemi.'* — **Attilâ İlhan**",
    "📜 *'Ben sana mecburum bilemezsin, adını mıh gibi aklımda tutuyorum.'* — **Attilâ İlhan**",
]

HAVALAR = [
    "☀️ **Hava Durumu:** Pırıl pırıl güneşli, 29°C! Ejderha bile serinlemek için limonata arıyor. 🥤",
    "⛅ **Hava Durumu:** Parçalı bulutlu, 24°C. Şarkı açıp balkonda kahve içmek için mükemmel bir hava!",
    "🌧️ **Hava Durumu:** Tatlı bir yağmur eşliğinde 18°C. Kulaklığı takıp slow parça dinleme vakti! 🎧",
    "⚡ **Hava Durumu:** Fırtınalı ve elektrikli! Ejderhanın kükremesi havayı alevlendiriyor! 🔥",
    "❄️ **Hava Durumu:** Serin ve ferahlatıcı, 16°C. İnce bir hırka almayı unutmayın!",
]

YILDIZ_FALLARI = [
    "⭐ **Yıldız Falın:** Bugün şans yıldızın zirvede parlıyor! Kararsız kaldığın bir konuda adım atarsan kazançlı çıkacaksın.",
    "⭐ **Yıldız Falın:** Merkür seninle barışık! Grup içi iletişimde parlayacak, esprilerinle herkesi güldüreceksin.",
    "⭐ **Yıldız Falın:** Venüs sana göz kırpıyor! Kalbini kıpır kıpır yapacak tatlı bir gelişme kapıda.",
    "⭐ **Yıldız Falın:** Mars enerjisi seni sarıyor! Bugün enerjin yüksek, spora veya müziğe vakit ayır.",
]

ILTIFATLAR = [
    "💐 **Ejderha Fısıltısı:** Grubun enerjisini tek başına ikiye katlayan muhteşem bir auraya sahipsin! ✨",
    "💐 **Ejderha Fısıltısı:** Zarafetin ve neşenle bu grubun en değerli cevherlerinden birisin! 💎",
    "💐 **Ejderha Fısıltısı:** Senin gibi dostlar zor bulunur; ejderha bile senin yanında sakinleşiyor! 🐲❤️",
    "💐 **Ejderha Fısıltısı:** Gülüşün grubun en karanlık gününü bile aydınlatacak kadar sıcak! ☀️",
]


# ── SOSYAL MENÜ METNİ & BUTONLARI ─────────────────────────────
SOSYAL_MENU_TEXT = """
✨━━━━━━━━━━━━━━━━━━━━━━━━✨
   🐲 **EJDERHA SOSYAL & EĞLENCE MERKEZİ** 🐲
✨━━━━━━━━━━━━━━━━━━━━━━━━✨

Grubunuza neşe katacak interaktif eğlence ve oyun komutları:

🎲 **OYUNLAR & ŞANS:**
• `/zar` — 1-6 arası şans zarı atar.
• `/sans` — Günlük şans yüzdenizi ölçer.
• `/kahve` — Fincanınızdaki sırları döker.
• `/yildiz` — Yıldız & burç falınızı yorumlar.

🎭 **KAHKAHA & KÜLTÜR:**
• `/fikra` — En komik fıkralarla güldürür.
• `/siir` — Efsane şairlerden dizeler sunar.
• `/hayvan` — Rastgele tatlı bir hayvan GIF'i getirir.
• `/saksak` — Sana özel tatlı bir iltifat fısıldar.
• `/hava` — Eğlenceli günlük hava tahmini yapar.

🥊 **TOPLULUK & TOKAT:**
• `/slap [@kullanıcı]` — Hedefe GIF'li Osmanlı tokadı atar!
• `/slapboard` — Tokat liderlik tablosunu açar.
• `/ship [@üye1] [@üye2]` — Aşk & uyum falı ölçer.
• `/gruprapor` — Bu grubun aktiflik ve mesaj analizini çıkarır.
━━━━━━━━━━━━━━━━━━━━━━━━
✨ *Aşağıdaki renkli butonlara dokunarak anında deneyin:*
"""


def get_sosyal_keyboard() -> InlineKeyboardMarkup:
    """Zengin emojili ve animasyonlu buton takımı."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Zar At", callback_data="sosyal_zar"),
            InlineKeyboardButton("☕ Kahve Falı", callback_data="sosyal_kahve"),
        ],
        [
            InlineKeyboardButton("🍀 Şansımı Ölç", callback_data="sosyal_sans"),
            InlineKeyboardButton("🎭 Fıkra Anlat", callback_data="sosyal_fikra"),
        ],
        [
            InlineKeyboardButton("📜 Şiir Oku", callback_data="sosyal_siir"),
            InlineKeyboardButton("⭐ Yıldız Falı", callback_data="sosyal_yildiz"),
        ],
        [
            InlineKeyboardButton("🐶 Sevimli Hayvan", callback_data="sosyal_hayvan"),
            InlineKeyboardButton("💐 Şakşak (İltifat)", callback_data="sosyal_saksak"),
        ],
        [
            InlineKeyboardButton("🥊 Tokat At", switch_inline_query_current_chat="/slap "),
            InlineKeyboardButton("💘 Aşk Ölçer", switch_inline_query_current_chat="/ship "),
        ],
        [
            InlineKeyboardButton("📊 Mesaj Kralları", callback_data="sosyal_mesajlar"),
            InlineKeyboardButton("📈 Grup Raporu", callback_data="sosyal_gruprapor"),
        ],
        [
            InlineKeyboardButton("🔄 Menüyü Yenile", callback_data="sosyal_refresh"),
            InlineKeyboardButton("🔙 Ana Menü", callback_data="menu_main"),
        ],
    ])


# ══════════════════════════════════════════════════════════════
# 1. /sosyal KOMUTU
# ══════════════════════════════════════════════════════════════
@Client.on_message(filters.command(["sosyal", "social", "eglence"]))
async def sosyal_command(client: Client, message: Message):
    """/sosyal veya /eglence komutu."""
    try:
        await message.reply_text(
            text=SOSYAL_MENU_TEXT,
            reply_markup=get_sosyal_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"/sosyal komut hatası: {e}")


# ══════════════════════════════════════════════════════════════
# 2. YENİ EĞLENCE KOMUTLARI (GIF DESTEKLİ)
# ══════════════════════════════════════════════════════════════

# ── /zar ──
@Client.on_message(filters.command(["zar", "dice"]))
async def zar_command(client: Client, message: Message):
    """/zar komutu: 1-6 arası rastgele zar atar."""
    num = random.randint(1, 6)
    dice_emojis = ["⚀ 1", "⚁ 2", "⚂ 3", "⚃ 4", "⚄ 5", "⚅ 6"]
    user_name = message.from_user.first_name if message.from_user else "Ejderha"
    caption = f"🎲 **{user_name}** zar attı!\n━━━━━━━━━━━━━━━━━━━━━━━━\n✨ Sonuç: **{dice_emojis[num - 1]}** geldi! 🎯"
    try:
        await message.reply_animation(animation=GIFS["dice"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /sans & /şans ──
@Client.on_message(filters.command(["sans", "şans", "sansim", "şansım"]))
async def sans_command(client: Client, message: Message):
    """/şans komutu: Rastgele şans yüzdesi hesaplar."""
    pct = random.randint(10, 100)
    user_name = message.from_user.first_name if message.from_user else "Ejderha"
    if pct > 80:
        comment = "🔥 Ejderhanın şansı seninle! Bugün piyango bileti alabilirsin!"
    elif pct > 50:
        comment = "✨ Şansın gayet yerinde, güzel haberler kapıda!"
    else:
        comment = "🌱 Biraz dikkatli ol, ama enerjini asla düşürme!"

    caption = (
        f"🍀 **GÜNLÜK ŞANS ÖLÇER** 🍀\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Kullanıcı:** {user_name}\n"
        f"🎯 **Bugünkü Şansınız:** `%{pct}`\n\n"
        f"{comment}"
    )
    try:
        await message.reply_animation(animation=GIFS["luck"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /kahve ──
@Client.on_message(filters.command(["kahve", "kahvefali", "fal"]))
async def kahve_command(client: Client, message: Message):
    """/kahve komutu: Rastgele kahve falı yorumu yapar."""
    fal = random.choice(KAHVE_FALLARI)
    user_name = message.from_user.first_name if message.from_user else "Ejderha"
    caption = (
        f"☕ **{user_name} İÇİN KAHVE FALI** ☕\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{fal}\n\n"
        f"✨ *Neyse halin, çıksın falın!*"
    )
    try:
        await message.reply_animation(animation=GIFS["coffee"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /fikra & /fıkra ──
@Client.on_message(filters.command(["fikra", "fıkra", "komik", "espiri"]))
async def fikra_command(client: Client, message: Message):
    """/fıkra komutu: Rastgele komik bir fıkra anlatır."""
    fikra = random.choice(FIKRALAR)
    try:
        await message.reply_animation(animation=GIFS["joke"], caption=fikra)
    except Exception:
        await message.reply_text(fikra)


# ── /siir & /şiir ──
@Client.on_message(filters.command(["siir", "şiir", "dize"]))
async def siir_command(client: Client, message: Message):
    """/şiir komutu: Rastgele güzel bir şiir dizesi gönderir."""
    siir = random.choice(SIIRLER)
    try:
        await message.reply_animation(animation=GIFS["poetry"], caption=siir)
    except Exception:
        await message.reply_text(siir)


# ── /hava ──
@Client.on_message(filters.command(["hava", "havadurumu"]))
async def hava_command(client: Client, message: Message):
    """/hava komutu: Günlük eğlenceli hava durumu tahmini yapar."""
    hava = random.choice(HAVALAR)
    gif_choice = GIFS["weather_sun"] if "güneşli" in hava or "parçalı" in hava else GIFS["weather_rain"]
    try:
        await message.reply_animation(animation=gif_choice, caption=hava)
    except Exception:
        await message.reply_text(hava)


# ── /hayvan ──
@Client.on_message(filters.command(["hayvan", "tatli", "pet"]))
async def hayvan_command(client: Client, message: Message):

    """/hayvan komutu: Rastgele sevimli bir hayvan GIF'i ve adı gönderir."""
    name, gif_url = random.choice(GIFS["animals"])
    caption = f"🐾 **Günün Sevimli Dostu:** {name} ❤️\n✨ *Gününün neşeyle dolması dileğiyle!*"
    try:
        await message.reply_animation(animation=gif_url, caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /yildiz & /yıldız ──
@Client.on_message(filters.command(["yildiz", "yıldız", "burc", "burç"]))
async def yildiz_command(client: Client, message: Message):
    """/yıldız komutu: Rastgele yıldız & burç falı yorumu sunar."""
    yildiz = random.choice(YILDIZ_FALLARI)
    user_name = message.from_user.first_name if message.from_user else "Ejderha"
    caption = (
        f"⭐ **{user_name} İÇİN YILDIZ FALI** ⭐\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{yildiz}"
    )
    try:
        await message.reply_animation(animation=GIFS["star"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /saksak, /şakşak, /iltifat ──
@Client.on_message(filters.command(["saksak", "şakşak", "iltifat", "ovgu"]))
async def saksak_command(client: Client, message: Message):
    """/şakşak veya /iltifat komutu: Kullanıcıya tatlı bir iltifat eder."""
    iltifat = random.choice(ILTIFATLAR)
    user_mention = message.from_user.mention if message.from_user else "Dostum"
    caption = f"💖 **Sevgili {user_mention},**\n━━━━━━━━━━━━━━━━━━━━━━━━\n{iltifat}"
    try:
        await message.reply_animation(animation=GIFS["compliment"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /saril, /sarıl ──
@Client.on_message(filters.command(["saril", "sarıl", "hug"]))
async def saril_command(client: Client, message: Message):
    """/sarıl komutu: Belirtilen üyeye veya gruba ejderha sıcaklığında sarılır."""
    sender_name = message.from_user.first_name if message.from_user else "Savaşçı"
    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user.first_name
    elif len(message.command) > 1:
        target = " ".join(message.command[1:])

    if target:
        caption = f"🤗 **{sender_name}**, **{target}** adlı üyeye ejderha kanatlarıyla sımsıkı sarıldı! ❤️🔥"
    else:
        caption = f"🤗 **{sender_name}** tüm gruba sımsıcak sarılıyor! Sevgimiz daim olsun! ✨"

    try:
        await message.reply_animation(animation=GIFS["hug"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /op, /öp, /opucuk ──
@Client.on_message(filters.command(["op", "öp", "opucuk", "öpücük", "kiss"]))
async def op_command(client: Client, message: Message):
    """/öp komutu: Hedef üyeye tatlı bir öpücük gönderir."""
    sender_name = message.from_user.first_name if message.from_user else "Savaşçı"
    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user.first_name
    elif len(message.command) > 1:
        target = " ".join(message.command[1:])

    if target:
        caption = f"💋 **{sender_name}**, **{target}** yanağına sıcacık bir öpücük kondurdu! 💖"
    else:
        caption = f"💋 **{sender_name}** havaya bir öpücük üfledi, dileyen yakalasın! ✨"

    try:
        await message.reply_animation(animation=GIFS["kiss"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /dans ──
@Client.on_message(filters.command(["dans", "oyna", "dance"]))
async def dans_command(client: Client, message: Message):
    """/dans komutu: Müziğin ritmiyle ejderha dansı başlatır."""
    sender_name = message.from_user.first_name if message.from_user else "Savaşçı"
    caption = f"💃🕺 **{sender_name}** müziğin ateşli ritmine kapılıp piste fırladı! Ejderha dansı başlasın! 🎶🔥"
    try:
        await message.reply_animation(animation=GIFS["dance"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /agla, /ağla ──
@Client.on_message(filters.command(["agla", "ağla", "cry", "huzun"]))
async def agla_command(client: Client, message: Message):
    """/ağla komutu: Hüzünlü anlar için ağlama animasyonu gönderir."""
    sender_name = message.from_user.first_name if message.from_user else "Savaşçı"
    caption = f"🥺💧 **{sender_name}** köşeye çekilip sessizce gözyaşı döküyor... Biri ona sarılsın! 💔"
    try:
        await message.reply_animation(animation=GIFS["cry"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /kutla, /parti ──
@Client.on_message(filters.command(["kutla", "parti", "celebrate", "party"]))
async def kutla_command(client: Client, message: Message):
    """/kutla komutu: Grup için konfetili kutlama başlatır."""
    sender_name = message.from_user.first_name if message.from_user else "Savaşçı"
    caption = f"🎉🥳 **KUTLAMA ZAMANI!** {sender_name} konfetileri patlattı! Ejderha sarayında şölen var! 🎊✨"
    try:
        await message.reply_animation(animation=GIFS["party"], caption=caption)
    except Exception:
        await message.reply_text(caption)



# ══════════════════════════════════════════════════════════════
# 3. SOSYAL MENÜ CALLBACK BUTON YÖNETİCİSİ
# ══════════════════════════════════════════════════════════════
@Client.on_callback_query(filters.regex(r"^sosyal_"))
async def sosyal_callback_handler(client: Client, callback: CallbackQuery):
    """Sosyal menü buton tıklamalarını yönetir."""
    data = callback.data
    chat_id = callback.message.chat.id
    user_name = callback.from_user.first_name if callback.from_user else "Ejderha"

    back_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")]]
    )

    try:
        if data == "sosyal_refresh":
            await callback.message.edit_text(
                text=SOSYAL_MENU_TEXT,
                reply_markup=get_sosyal_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
            await callback.answer("🔄 Menü güncellendi!")
            return

        elif data == "sosyal_zar":
            num = random.randint(1, 6)
            dice_emojis = ["⚀ 1", "⚁ 2", "⚂ 3", "⚃ 4", "⚄ 5", "⚅ 6"]
            out_text = (
                f"🎲 **ZAR ATILDI!** 🎲\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Atan:** {user_name}\n"
                f"🎯 **Gelen Zar:** **{dice_emojis[num - 1]}**\n\n"
                f"✨ *Tekrar atmak için `/zar` yazabilirsiniz.*"
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb)
            await callback.answer(f"🎲 Zar: {num} geldi!")

        elif data == "sosyal_kahve":
            fal = random.choice(KAHVE_FALLARI)
            out_text = (
                f"☕ **GÜNLÜK KAHVE FALI** ☕\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{fal}\n\n"
                f"✨ *Detaylı fal için: `/kahve`*"
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb)
            await callback.answer("☕ Falınız bakıldı!")

        elif data == "sosyal_sans":
            pct = random.randint(20, 100)
            out_text = (
                f"🍀 **ŞANS DERECENİZ** 🍀\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **{user_name}** için bugünkü şans:\n"
                f"🔥 **Oran:** `%{pct}`\n\n"
                f"✨ *Tekrar denemek için: `/şans`*"
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb)
            await callback.answer(f"🍀 Şansınız: %{pct}")

        elif data == "sosyal_fikra":
            fikra = random.choice(FIKRALAR)
            await callback.message.edit_text(fikra, reply_markup=back_kb)
            await callback.answer("🎭 Fıkra hazır!")

        elif data == "sosyal_siir":
            siir = random.choice(SIIRLER)
            await callback.message.edit_text(siir, reply_markup=back_kb)
            await callback.answer("📜 Şiir hazır!")

        elif data == "sosyal_yildiz":
            yildiz = random.choice(YILDIZ_FALLARI)
            out_text = (
                f"⭐ **YILDIZ & BURÇ FALI** ⭐\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{yildiz}"
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb)
            await callback.answer("⭐ Yıldızınız parlıyor!")

        elif data == "sosyal_hayvan":
            name, _ = random.choice(GIFS["animals"])
            out_text = (
                f"🐾 **GÜNÜN SEVİMLİ DOSTU** 🐾\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ Seçilen Dost: {name}\n\n"
                f"*(GIF'li görmek için sohbete `/hayvan` yazabilirsiniz!)*"
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb)
            await callback.answer("🐶 Sevimli dost seçildi!")

        elif data == "sosyal_saksak":
            iltifat = random.choice(ILTIFATLAR)
            out_text = (
                f"💐 **ÖZEL İLTİFAT KÖŞESİ** 💐\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{iltifat}"
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb)
            await callback.answer("💐 İltifat fısıldandı!")

        elif data == "sosyal_gruprapor":
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            chat_title = callback.message.chat.title or "Bu Grup"

            leaders = await get_daily_leaderboard(chat_id=chat_id, limit=3)
            gstats = await get_group_stats(chat_id)

            if not leaders:
                await callback.answer("💬 Bu grupta bugün henüz kayıtlı mesaj yok!", show_alert=True)
                return

            total_messages = gstats.get("total_messages", 0)
            active_members = gstats.get("active_users", len(leaders))

            champion_name = leaders[0].get("name", "Ejderha")
            top_count = leaders[0].get("message_count", 0)

            medals = ["🥇", "🥈", "🥉"]
            top3_lines = []
            for idx, item in enumerate(leaders[:3]):
                name = item.get("name", "Savaşçı")
                count = item.get("message_count", 0)
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
            await callback.message.edit_text(out_text, reply_markup=back_kb)
            await callback.answer()

        elif data == "sosyal_mesajlar":
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")

            leaders = await get_daily_leaderboard(chat_id=chat_id, limit=5)

            if not leaders:
                await callback.answer("💬 Bugün henüz kayıtlı mesaj yok!", show_alert=True)
                return

            medals = ["👑", "🥈", "🥉", "4️⃣", "5️⃣"]
            lines = []
            for idx, item in enumerate(leaders[:5]):
                m = medals[idx] if idx < len(medals) else f"`{idx+1}.`"
                n = item.get("name", "Savaşçı")
                count = item.get("message_count", 0)
                tag = " 🔥[GERÇEK EJDERHA]" if idx == 0 else ""
                lines.append(f"{m} **{n}**{tag} — `{count}` mesaj")

            out_text = (
                f"📊 **GÜNLÜK MESAJ KRALLARI** 📊\n"
                f"📅 Tarih: `{today_str}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                + "\n".join(lines) +
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 Günün Lideri: **{leaders[0].get('name', 'Ejderha')}**"
            )
            await callback.message.edit_text(out_text, reply_markup=back_kb)
            await callback.answer()


    except Exception as e:
        logger.error(f"sosyal_callback hatası: {e}")
        try:
            await callback.answer(f"Hata: {e}", show_alert=True)
        except Exception:
            pass
