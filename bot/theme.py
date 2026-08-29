# ============================================
# 🐲 Ejderha Müzik Botu - Tema Modülü
# ============================================
# Tüm bot mesajlarını, emojileri ve inline keyboard
# düzenlerini merkezi olarak yönetir.
# Ejderha temalı fantastik dil burada tanımlanır.

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ── Ejderha Emojileri ─────────────────────────────────────────
DRAGON = "🐲"
DRAGON_FACE = "🐉"
FIRE = "🔥"
VOLCANO = "🌋"
MUSIC = "🎵"
VIDEO = "🎬"
SPOTIFY = "🟢"
SPARKLE = "✨"
SWORD = "⚔️"
CROWN = "👑"
GEM = "💎"
SCROLL = "📜"
SHIELD = "🛡️"
DOWNLOAD = "📥"
GEAR = "⚙️"
PAUSE = "⏸️"
PLAY = "▶️"
SKIP = "⏭️"
QUEUE = "📋"


# ── Karşılama Mesajı ─────────────────────────────────────────
WELCOME_TEXT = f"""
{DRAGON_FACE} **EJDERHA MÜZİK & VİDEO BOTU** {DRAGON_FACE}
━━━━━━━━━━━━━━━━━━━━━━━━

{FIRE} *Ejderha uyanıyor... Kanatlarını açıyor...*

Hoş geldin, cesur savaşçı! {SWORD}

Ben **Ejderha Müzik Botu**, sesli sohbetlerde
müziğin ve videonun ateşli nefesiyle yayın yapan
efsanevi bir yaratığım! {VOLCANO}

{SPARKLE} Ses ve Görüntülü Yayın (720p HD)
{SPARKLE} YouTube & Spotify Entegrasyonu
{SPARKLE} Ritim ve Görsellik kanatlarımda taşınır!

{GEM} Aşağıdaki butonlardan keşfetmeye başla:
━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ── Menü Metinleri ────────────────────────────────────────────
COMMANDS_TEXT = f"""
{SCROLL} **EJDERHA KOMUTLARI** {SCROLL}
━━━━━━━━━━━━━━━━━━━━━━━━

{FIRE} `/oynat` veya `/play <şarkı adı / Spotify linki / YouTube linki>`
↳ Ejderha müziği sesli sohbette ateşler! Çalıyorsa sıraya ekler.

{VIDEO} `/voynat` veya `/vplay` veya `/video <video adı veya link>`
↳ Ejderha görüntülü yayını (720p HD) başlatır!

{SPOTIFY} **Spotify Link Desteği:**
↳ Tekli şarkı, albüm veya çalma listesi linklerini `/oynat` ile atabilirsiniz.

{PAUSE} `/duraklat` veya `/pause`
↳ Ejderha nefesini tutar, yayın durur.

{PLAY} `/devam` veya `/resume`
↳ Ejderha tekrar kükreyerek yayına devam eder!

{SKIP} `/gec` veya `/atla` veya `/skip`
↳ Ejderha sıradaki parçaya/videoya kanat çırpar.

🛑 `/bitir` veya `/dur` veya `/stop`
↳ Yayını durdurur, kuyruğu temizler ve sohbetten ayrılır.

🔀 `/karistir` veya `/shuffle`
↳ Kuyruktaki şarkıları rastgele karıştırır.

🧹 `/temizle` veya `/clear`
↳ Sıradaki tüm bekleyen parçaları temizler.

{QUEUE} `/sira` veya `/queue`
↳ Ejderhanın müzik kuyruğunu gösterir.

{DOWNLOAD} `/indir <şarkı adı veya link>`
↳ Ejderha şarkıyı MP3 olarak pençeleriyle kapar!

{MUSIC} `/menu`
↳ Bu menüyü tekrar çağırır.
━━━━━━━━━━━━━━━━━━━━━━━━
"""

DOWNLOAD_HELP_TEXT = f"""
{DOWNLOAD} **NASIL İNDİRİLİR?** {DOWNLOAD}
━━━━━━━━━━━━━━━━━━━━━━━━

{DRAGON} Ejderha, istediğin şarkıyı pençeleriyle
yakalar ve sana MP3 olarak sunar!

{FIRE} **Kullanım:**
`/indir Tarkan Şımarık`
`/indir https://youtube.com/watch?v=...`

{SPARKLE} **Özellikler:**
• En yüksek kalitede MP3 (320kbps)
• YouTube linkli veya isimle arama
• Doğrudan Telegram'a ses dosyası olarak gelir
• Hızlı ve güvenilir indirme

{VOLCANO} **Not:** Ejderha sadece YouTube'dan
müzik indirir. Telif hakkına dikkat edin!
━━━━━━━━━━━━━━━━━━━━━━━━
"""

SETTINGS_TEXT = f"""
{GEAR} **EJDERHA AYARLARI** {GEAR}
━━━━━━━━━━━━━━━━━━━━━━━━

{SHIELD} **Bot Bilgileri:**
• Sürüm: `1.1.0`
• Motor: `Pyrogram + PyTgCalls v1.2.9`
• Ses Kalitesi: `320kbps / Opus 48kHz`
• Video Kalitesi: `720p HD MP4`
• Servisler: `YouTube (Cookies) & Spotify`

{DRAGON_FACE} **Ejderha Durumu:**
• Durum: Uyanık ve hazır! {FIRE}
• Dil: Türkçe 🇹🇷

{GEM} **Teknolojiler:**
• Python 3.10+
• FFmpeg ses/video işleme
• Asenkron WebRTC mimari
━━━━━━━━━━━━━━━━━━━━━━━━
"""

DEVELOPER_TEXT = f"""
{CROWN} **GELİŞTİRİCİ** {CROWN}
━━━━━━━━━━━━━━━━━━━━━━━━

{DRAGON_FACE} Bu bot, ejderhaların gücüyle
kodlanmıştır!

{FIRE} **Geliştirici:** SpideyDev
{SPARKLE} **GitHub:** [SpideyMuzikBot]
{GEM} **İletişim:** @SpideyDev

{VOLCANO} Ejderha her zaman gelişmeye devam eder!
Öneri ve isteklerinizi bekliyoruz.

{SWORD} *"Kod ateşle yazılır, müzikle çalınır!"*
━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ── Durum Mesajları ───────────────────────────────────────────

def msg_searching(query: str, is_video: bool = False) -> str:
    """Arama yapılırken gösterilecek mesaj."""
    media_type = "video" if is_video else "şarkı"
    return f"{DRAGON} **Ejderha {media_type} arıyor...** {FIRE}\n\n{SCROLL} `{query}` için göklerde süzülüyor..."

def msg_playing(title: str, duration: str = "", is_video: bool = False) -> str:
    """Şarkı veya video çalmaya başladığında gösterilecek mesaj."""
    dur_text = f"\n{SPARKLE} Süre: `{duration}`" if duration else ""
    icon = VIDEO if is_video else MUSIC
    header = "Görüntülü Yayını Başlattı!" if is_video else "Müziği Ateşliyor!"
    subtext = "Görüntü ve ses ejderhanın aleviyle aktarılıyor..." if is_video else "Müzik ejderhanın nefesiyle çalıyor..."
    return (
        f"{DRAGON_FACE} **Ejderha {header}** {FIRE}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{icon} **{title}**{dur_text}\n\n"
        f"{VOLCANO} *{subtext}*"
    )

def msg_queued(title: str, position: int, is_video: bool = False) -> str:
    """Şarkı veya video kuyruğa eklendiğinde gösterilecek mesaj."""
    icon = VIDEO if is_video else MUSIC
    return (
        f"{DRAGON} **Kuyruğa Eklendi!** {SPARKLE}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{icon} **{title}**\n"
        f"{SCROLL} Sıra: **#{position}**\n\n"
        f"{FIRE} *Ejderha sırasını bekliyor...*"
    )

def msg_spotify_importing(count: int) -> str:
    """Spotify listesi içe aktarılırken gösterilecek mesaj."""
    return (
        f"{SPOTIFY} **Spotify Listesi Algılandı!** {SPARKLE}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{MUSIC} Toplam **{count}** parça YouTube'da aranıp kuyruğa ekleniyor...\n\n"
        f"{FIRE} *Ejderha listeyi hazırlıyor...*"
    )

def msg_paused() -> str:
    """Müzik duraklatıldığında gösterilecek mesaj."""
    return f"{PAUSE} **Ejderha Nefesini Tuttu!** {DRAGON}\n\n*Yayın donduruldu... Devam etmek için /devam yazın.*"

def msg_resumed() -> str:
    """Müzik devam ettirildiğinde gösterilecek mesaj."""
    return f"{PLAY} **Ejderha Tekrar Kükredi!** {FIRE}\n\n*Yayın kaldığı yerden devam ediyor...*"

def msg_skipped(next_title: str = None, is_video: bool = False) -> str:
    """Şarkı atlandığında gösterilecek mesaj."""
    icon = VIDEO if is_video else MUSIC
    if next_title:
        return (
            f"{SKIP} **Ejderha Kanat Çırptı!** {DRAGON}\n\n"
            f"{icon} Şimdi çalıyor: **{next_title}**"
        )
    return f"{SKIP} **Ejderha Kanat Çırptı!** {DRAGON}\n\n{SCROLL} Kuyruk boş! Ejderha uykuya dalıyor... 💤"

def msg_stopped() -> str:
    """Müzik durdurulup çıkıldığında gösterilecek mesaj."""
    return f"🛑 **Ejderha Yayını Sonlandırdı!** {DRAGON}\n\n*Sesli sohbetten ayrılındı ve kuyruk temizlendi.* 💤"

def msg_shuffled() -> str:
    """Kuyruk karıştırıldığında gösterilecek mesaj."""
    return f"🔀 **Ejderha Kuyruğu Karıştırdı!** {DRAGON_FACE}\n\n*Bekleyen parçalar rastgele harmanlandı!* {FIRE}"

def msg_queue_cleared() -> str:
    """Kuyruk temizlendiğinde gösterilecek mesaj."""
    return f"🧹 **Ejderha Kuyruğu Temizledi!** {DRAGON}\n\n*Bekleyen tüm parçalar silindi.*"

def msg_queue_empty() -> str:
    """Kuyruk boş olduğunda gösterilecek mesaj."""
    return f"{QUEUE} **Kuyruk Boş!** {DRAGON}\n\n*Ejderhanın listesi tükenmiş! /oynat veya /voynat ile yeni parça ekleyin.* {FIRE}"

def msg_queue_list(tracks: list, current_title: str = None) -> str:
    """Kuyruk listesini gösteren mesaj."""
    text = f"{QUEUE} **Ejderhanın Yayın Kuyruğu** {DRAGON_FACE}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    if current_title:
        text += f"{FIRE} **Şu an çalıyor:** {current_title}\n\n"
    for i, track in enumerate(tracks, 1):
        icon = VIDEO if track.get("stream_type") == "video" else MUSIC
        text += f"{SPARKLE} **{i}.** {icon} {track['title']}\n"
    text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n{SCROLL} Toplam: **{len(tracks)}** parça"
    return text

def msg_downloading(title: str) -> str:
    """İndirme başladığında gösterilecek mesaj."""
    return (
        f"{DOWNLOAD} **Ejderha İndiriyor!** {DRAGON}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{MUSIC} **{title}**\n\n"
        f"{FIRE} *Ejderha pençeleriyle müziği kapıyor...*"
    )

def msg_download_complete(title: str) -> str:
    """İndirme tamamlandığında gösterilecek mesaj."""
    return (
        f"{GEM} **İndirme Tamamlandı!** {DRAGON_FACE}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{MUSIC} **{title}**\n\n"
        f"{SPARKLE} *Ejderha müziği başarıyla teslim etti!*"
    )

def msg_error(detail: str = "") -> str:
    """Hata mesajı."""
    extra = f"\n\n{SCROLL} Detay: `{detail}`" if detail else ""
    return f"{VOLCANO} **Ejderha Hata Aldı!** {DRAGON}\n\n*Bir şeyler ters gitti... Tekrar deneyin.*{extra}"

def msg_no_voice_chat() -> str:
    """Sesli sohbet bulunamadığında gösterilecek mesaj."""
    return f"{VOLCANO} **Sesli Sohbet Bulunamadı!** {DRAGON}\n\n*Lütfen önce grupta sesli sohbeti başlatın.*"

def msg_not_playing() -> str:
    """Hiçbir şey çalmıyorken gösterilecek mesaj."""
    return f"{DRAGON} **Ejderha Sessiz!**\n\n*Şu an çalan bir şey yok. /oynat veya /voynat ile yayını başlatın!* {FIRE}"

def msg_usage(command: str, example: str) -> str:
    """Kullanım hatası mesajı."""
    return (
        f"{SCROLL} **Kullanım Hatası** {DRAGON}\n\n"
        f"Doğru kullanım: `{command}`\n"
        f"Örnek: `{example}`"
    )

# ── Inline Keyboard Düzenleri ─────────────────────────────────

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Ana menü butonlarını döndürür."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{MUSIC} Komutlar", callback_data="menu_commands"),
            InlineKeyboardButton(f"{DOWNLOAD} Nasıl İndirilir?", callback_data="menu_download"),
        ],
        [
            InlineKeyboardButton(f"{GEAR} Ayarlar", callback_data="menu_settings"),
            InlineKeyboardButton(f"{CROWN} Geliştirici", callback_data="menu_developer"),
        ],
    ])

def get_back_button() -> InlineKeyboardMarkup:
    """Geri butonu döndürür."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔙 Ana Menü", callback_data="menu_main")],
    ])
