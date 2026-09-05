# ============================================
# 🐲 Ejderha Müzik Botu - Zengin Sosyal & Eğlence Modülü
# ============================================
# /sosyal menüsü, zar atma, kahve falı, şans ölçer,
# fıkra, şiir, hayvan GIF'leri, yıldız falı ve iltifat komutları.
# Tüm komutlar hareketli ve çalışan GIF'lerle zenginleştirilmiştir.

import os
import random
import hashlib
import logging
from datetime import datetime
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    User,
)
from pyrogram.enums import ParseMode, ChatType

from utils.db import get_daily_leaderboard, get_group_stats, get_slap_leaderboard, record_slap_event
from utils.decorators import clean_command

logger = logging.getLogger(__name__)


# ── ÇALIŞAN SABİT GIF VE ANİMASYON CDN LİNKLERİ ──────────────
GIFS = {
    "dice": "https://media.giphy.com/media/3oriO04qxVReM5rJEA/giphy.gif",
    "coffee": "https://media.giphy.com/media/3oriO13KTkzPwTykp2/giphy.gif",
    "luck": "https://media.giphy.com/media/l3UcjBJUov1gCRGbS/giphy.gif",
    "joke": "https://media.giphy.com/media/10JhviFuU2gWD6/giphy.gif",
    "poetry": "https://media.giphy.com/media/26FPy3QZLnLCy5Ip2/giphy.gif",
    "weather_sun": "https://media.giphy.com/media/u01ioCe6G8URG/giphy.gif",
    "weather_rain": "https://media.giphy.com/media/mno6BJfyRCbde/giphy.gif",
    "star": "https://media.giphy.com/media/xT9IgzoKnwFNmISR8I/giphy.gif",
    "compliment": "https://media.giphy.com/media/M90mJvfWfd5mbUuULX/giphy.gif",
    "hug": "https://media.giphy.com/media/u9BxQbM5bxvwY/giphy.gif",
    "kiss": "https://media.giphy.com/media/G3va31oEEnIkM/giphy.gif",
    "dance": "https://media.giphy.com/media/blSTtZehjAZ8I/giphy.gif",
    "cry": "https://media.giphy.com/media/L95W4wv8nnb9K/giphy.gif",
    "party": "https://media.giphy.com/media/artj92V8o75VPL7AeQ/giphy.gif",
    "animals": [
        ("🐈 **Mırmır Kedi**", "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif"),
        ("🐕 **Neşeli Köpecik**", "https://media.giphy.com/media/bbshzgyFQDqPHXBo4c/giphy.gif"),
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
            InlineKeyboardButton("🥊 Tokat At", callback_data="sosyal_slap"),
            InlineKeyboardButton("🏆 Tokat Tablosu", callback_data="sosyal_slapboard"),
        ],
        [
            InlineKeyboardButton("💘 Aşk Ölçer (Ship)", callback_data="sosyal_ship"),
            InlineKeyboardButton("🌤️ Hava Durumu", callback_data="sosyal_hava"),
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
@Client.on_message(clean_command(["sosyal", "eglence"]))
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
@Client.on_message(clean_command(["zar", "dice", "zarat"]))
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
@Client.on_message(clean_command(["sans", "şans", "sansim", "şansım", "sansolc", "şansölç"]))
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
@Client.on_message(clean_command(["kahve", "kahvefali", "kahvefal", "fal"]))
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
@Client.on_message(clean_command(["fikra", "fıkra", "komik", "espiri", "espri", "fıkraanlat"]))
async def fikra_command(client: Client, message: Message):
    """/fıkra komutu: Rastgele komik bir fıkra anlatır."""
    fikra = random.choice(FIKRALAR)
    try:
        await message.reply_animation(animation=GIFS["joke"], caption=fikra)
    except Exception:
        await message.reply_text(fikra)


# ── /siir & /şiir ──
@Client.on_message(clean_command(["siir", "şiir", "dize", "siiroku", "şiiroku"]))
async def siir_command(client: Client, message: Message):
    """/şiir komutu: Rastgele güzel bir şiir dizesi gönderir."""
    siir = random.choice(SIIRLER)
    try:
        await message.reply_animation(animation=GIFS["poetry"], caption=siir)
    except Exception:
        await message.reply_text(siir)


# ── /hava ──
@Client.on_message(clean_command(["hava", "havadurumu", "gundemhava"]))
async def hava_command(client: Client, message: Message):
    """/hava komutu: Günlük eğlenceli hava durumu tahmini yapar."""
    hava = random.choice(HAVALAR)
    gif_choice = GIFS["weather_sun"] if "güneşli" in hava or "parçalı" in hava else GIFS["weather_rain"]
    try:
        await message.reply_animation(animation=gif_choice, caption=hava)
    except Exception:
        await message.reply_text(hava)


# ── /hayvan ──
@Client.on_message(clean_command(["hayvan", "tatli", "tatlı", "sevimlihayvan", "sevimli"]))
async def hayvan_command(client: Client, message: Message):

    """/hayvan komutu: Rastgele sevimli bir hayvan GIF'i ve adı gönderir."""
    name, gif_url = random.choice(GIFS["animals"])
    caption = f"🐾 **Günün Sevimli Dostu:** {name} ❤️\n✨ *Gününün neşeyle dolması dileğiyle!*"
    try:
        await message.reply_animation(animation=gif_url, caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /yildiz & /yıldız ──
@Client.on_message(clean_command(["yildiz", "yıldız", "burc", "burç", "yildizfali", "yıldızfalı"]))
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
@Client.on_message(clean_command(["saksak", "şakşak", "iltifat", "ovgu", "övgü"]))
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
@Client.on_message(clean_command(["saril", "sarıl"]))
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
@Client.on_message(clean_command(["op", "öp", "opucuk", "öpücük"]))
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
@Client.on_message(clean_command(["dans", "oyna"]))
async def dans_command(client: Client, message: Message):
    """/dans komutu: Müziğin ritmiyle ejderha dansı başlatır."""
    sender_name = message.from_user.first_name if message.from_user else "Savaşçı"
    caption = f"💃🕺 **{sender_name}** müziğin ateşli ritmine kapılıp piste fırladı! Ejderha dansı başlasın! 🎶🔥"
    try:
        await message.reply_animation(animation=GIFS["dance"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /agla, /ağla ──
@Client.on_message(clean_command(["agla", "ağla", "huzun"]))
async def agla_command(client: Client, message: Message):
    """/ağla komutu: Hüzünlü anlar için ağlama animasyonu gönderir."""
    sender_name = message.from_user.first_name if message.from_user else "Savaşçı"
    caption = f"🥺💧 **{sender_name}** köşeye çekilip sessizce gözyaşı döküyor... Biri ona sarılsın! 💔"
    try:
        await message.reply_animation(animation=GIFS["cry"], caption=caption)
    except Exception:
        await message.reply_text(caption)


# ── /kutla, /parti ──
@Client.on_message(clean_command(["kutla", "parti"]))
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
            zar_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 Tekrar Zar At", callback_data="sosyal_zar")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=zar_kb)
            await callback.answer(f"🎲 Zar: {num} geldi!")

        elif data == "sosyal_kahve":
            fal = random.choice(KAHVE_FALLARI)
            out_text = (
                f"☕ **GÜNLÜK KAHVE FALI** ☕\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{fal}\n\n"
                f"✨ *Detaylı fal için: `/kahve`*"
            )
            kahve_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("☕ Yeni Fal Bak", callback_data="sosyal_kahve")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=kahve_kb)
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
            sans_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🍀 Tekrar Ölç", callback_data="sosyal_sans")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=sans_kb)
            await callback.answer(f"🍀 Şansınız: %{pct}")

        elif data == "sosyal_fikra":
            fikra = random.choice(FIKRALAR)
            fikra_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎭 Başka Fıkra", callback_data="sosyal_fikra")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(fikra, reply_markup=fikra_kb)
            await callback.answer("🎭 Fıkra hazır!")

        elif data == "sosyal_siir":
            siir = random.choice(SIIRLER)
            siir_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📜 Başka Şiir", callback_data="sosyal_siir")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(siir, reply_markup=siir_kb)
            await callback.answer("📜 Şiir hazır!")

        elif data == "sosyal_yildiz":
            yildiz = random.choice(YILDIZ_FALLARI)
            out_text = (
                f"⭐ **YILDIZ & BURÇ FALI** ⭐\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{yildiz}\n\n"
                f"✨ *Tekrar bakmak için: `/yıldız`*"
            )
            yildiz_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Yeni Fal Bak", callback_data="sosyal_yildiz")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=yildiz_kb)
            await callback.answer("⭐ Yıldızınız parlıyor!")

        elif data == "sosyal_hayvan":
            name, _ = random.choice(GIFS["animals"])
            out_text = (
                f"🐾 **GÜNÜN SEVİMLİ DOSTU** 🐾\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ Seçilen Dost: {name}\n\n"
                f"*(GIF'li animasyon için sohbete `/hayvan` yazabilirsiniz!)*"
            )
            hayvan_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🐾 Başka Hayvan", callback_data="sosyal_hayvan")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=hayvan_kb)
            await callback.answer("🐶 Sevimli dost seçildi!")

        elif data == "sosyal_saksak":
            iltifat = random.choice(ILTIFATLAR)
            out_text = (
                f"💐 **ÖZEL İLTİFAT KÖŞESİ** 💐\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{iltifat}\n\n"
                f"✨ *Yeni iltifat için: `/şakşak`*"
            )
            saksak_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💐 Yeni İltifat", callback_data="sosyal_saksak")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=saksak_kb)
            await callback.answer("💐 İltifat fısıldandı!")

        elif data == "sosyal_hava":
            hava = random.choice(HAVALAR)
            out_text = (
                f"🌤️ **GÜNLÜK HAVA DURUMU** 🌤️\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{hava}\n\n"
                f"✨ *Detaylı tahmin için: `/hava`*"
            )
            hava_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌤️ Başka Hava", callback_data="sosyal_hava")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=hava_kb)
            await callback.answer("🌤️ Hava durumu güncellendi!")

        elif data == "sosyal_slap":
            sender = callback.from_user
            sender_name = sender.first_name if sender else "Ejderha"
            sender_id = sender.id if sender else 0

            target_user = None
            target_name = "Kendisi"
            target_id = sender_id

            if callback.message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                target_user = await _get_random_chat_member(client, chat_id, exclude_ids={sender_id})
                if target_user:
                    target_name = target_user.first_name
                    target_id = target_user.id

            if target_user:
                target_display = target_name
            else:
                target_display = "Havaya (Boşluğa)"

            if sender_id and target_id and target_id != sender_id:
                await record_slap_event(sender_id, sender_name, target_id, target_name)

            out_text = (
                f"🥊 **OSMANLI TOKADI İNDİRİLDİ!** 💥\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👋 **{sender_name}**, hedefine kilitlendi ve **{target_display}**'a sert bir Osmanlı tokadı yapıştırdı! 💫\n\n"
                f"📌 *Belirli birine tokat atmak için: `/slap @kullanıcı` veya bir mesaja `/slap` yanıtı verin!*"
            )
            slap_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🥊 Tekrar Tokatla", callback_data="sosyal_slap")],
                [
                    InlineKeyboardButton("🏆 Tokat Tablosu", callback_data="sosyal_slapboard"),
                    InlineKeyboardButton("🔙 Sosyal Menü", callback_data="sosyal_refresh"),
                ],
            ])
            await callback.message.edit_text(out_text, reply_markup=slap_kb)
            await callback.answer("🥊 Tokat patlatıldı!")

        elif data == "sosyal_slapboard":
            leaders = await get_slap_leaderboard(limit=10)
            if not leaders:
                out_text = (
                    f"🥊 **TOKAT LİDERLİK TABLOSU** 🥊\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Henüz kimse tokat atmadı! İlk tokadı sen patlat:\n"
                    f"👉 `/slap` veya aşağıdaki butonla tokatla!"
                )
            else:
                sorted_givers = sorted(leaders, key=lambda x: x.get("slaps_given", 0), reverse=True)[:5]
                sorted_receivers = sorted(leaders, key=lambda x: x.get("slaps_received", 0), reverse=True)[:5]
                medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

                givers_text = ""
                for idx, item in enumerate(sorted_givers):
                    c = item.get("slaps_given", 0)
                    if c > 0:
                        n = item.get("user_name", f"Kullanıcı_{item.get('user_id')}")
                        givers_text += f"{medals[idx]} **{n}** — `{c}` tokat\n"
                if not givers_text:
                    givers_text = "Henüz tokat atan yok.\n"

                receivers_text = ""
                for idx, item in enumerate(sorted_receivers):
                    c = item.get("slaps_received", 0)
                    if c > 0:
                        n = item.get("user_name", f"Kullanıcı_{item.get('user_id')}")
                        receivers_text += f"{medals[idx]} **{n}** — `{c}` tokat\n"
                if not receivers_text:
                    receivers_text = "Henüz tokat yiyen yok.\n"

                total_slaps = sum(d.get("slaps_given", 0) for d in leaders)
                out_text = (
                    f"🏆 **EJDERHA TOKAT LİDERLİK TABLOSU** 🏆\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🥊 **EN ÇOK TOKAT ATANLAR:**\n{givers_text}\n"
                    f"🤕 **EN ÇOK TOKAT YİYENLER:**\n{receivers_text}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💥 **Toplam Atılan Tokat:** `{total_slaps}`\n"
                    f"✨ *Sıralamaya girmek için: `/slap`*"
                )

            slapboard_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🥊 Tokat At", callback_data="sosyal_slap")],
                [
                    InlineKeyboardButton("🔄 Tabloyu Yenile", callback_data="sosyal_slapboard"),
                    InlineKeyboardButton("🔙 Sosyal Menü", callback_data="sosyal_refresh"),
                ],
            ])
            await callback.message.edit_text(out_text, reply_markup=slapboard_kb)
            await callback.answer("🏆 Tokat tablosu yüklendi!")

        elif data == "sosyal_ship":
            sender = callback.from_user
            sender_name = sender.first_name if sender else "Sen"
            sender_id = sender.id if sender else 0

            u1_name = sender_name
            u1_id = sender_id
            u2_name = "Gizemli Üye"
            u2_id = 999999

            if callback.message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                rand_u = await _get_random_chat_member(client, chat_id, exclude_ids={sender_id})
                if rand_u:
                    u2_name = rand_u.first_name
                    u2_id = rand_u.id
                else:
                    u2_name = "Ejderha Bot 🐲"
            else:
                u2_name = "Ejderha Bot 🐲"

            today_str = datetime.now().strftime("%Y-%m-%d")
            pair_key = f"{min(u1_id, u2_id)}_{max(u1_id, u2_id)}_{today_str}_{random.randint(1, 1000)}"
            percent = int(hashlib.md5(pair_key.encode()).hexdigest(), 16) % 101

            filled = round(percent / 10)
            empty = 10 - filled
            progress_bar = "█" * filled + "░" * empty

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

            out_text = (
                f"💘 **EJDERHA AŞK ÖLÇER (SHIP)** 💘\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **1. Kişi:** {u1_name}\n"
                f"👤 **2. Kişi:** {u2_name}\n\n"
                f"📊 **Aşk Uyumu:** `[{progress_bar}] %{percent}`\n"
                f"💬 **Ejderha Yorumu:**\n{verdict}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ *İstediğiniz iki kişiyi eşleştirmek için: `/ship @üye1 @üye2`*"
            )
            ship_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💘 Başka Çift Dene", callback_data="sosyal_ship")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=ship_kb)
            await callback.answer(f"💘 Uyum: %{percent}!")

        elif data == "sosyal_gruprapor":
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
            rapor_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Raporu Güncelle", callback_data="sosyal_gruprapor")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=rapor_kb)
            await callback.answer()

        elif data == "sosyal_mesajlar":
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
            mesaj_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Sıralamayı Güncelle", callback_data="sosyal_mesajlar")],
                [InlineKeyboardButton("🔙 Sosyal Menüye Dön", callback_data="sosyal_refresh")],
            ])
            await callback.message.edit_text(out_text, reply_markup=mesaj_kb)
            await callback.answer()


    except Exception as e:
        logger.error(f"sosyal_callback hatası: {e}")
        try:
            await callback.answer(f"Hata: {e}", show_alert=True)
        except Exception:
            pass
