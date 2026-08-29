# ============================================
# 🐲 Ejderha Müzik Botu - Bot Paketi
# ============================================
# Bu modül bot paketini tanımlar.
# Döngüsel import sorununu önlemek için burada doğrudan
# clients import edilmez; clients modülüne ihtiyaç duyan
# kodlar doğrudan 'from bot.clients import ...' kullanmalıdır.

# ── Telegram 64-bit Yeni Kanal/Grup ID Yaması ─────────────────
# Pyrogram 2.0.106'da eski 32-bit sınırı (-1002147483647) bulunur.
# Yeni oluşturulan Telegram gruplarının ID'leri (-1004299297214 gibi)
# bu sınırı aştığı için MIN_CHANNEL_ID genişletilir.
try:
    import pyrogram.utils
    pyrogram.utils.MIN_CHANNEL_ID = -1009999999999
    pyrogram.utils.MAX_CHANNEL_ID = -1000000000000
except Exception:
    pass
