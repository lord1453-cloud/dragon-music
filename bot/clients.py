# ============================================
# 🐲 Ejderha Müzik Botu - İstemci Tanımları
# ============================================
# Pyrogram bot client, userbot client ve PyTgCalls
# instance'larını oluşturur ve dışa açar.

from pyrogram import Client
from pytgcalls import PyTgCalls

from bot.config import BOT_TOKEN, API_ID, API_HASH, SESSION_STRING

# ── Bot İstemcisi ─────────────────────────────────────────────
# Komutları dinleyen ana bot hesabı.
# plugins parametresi ile bot/plugins klasöründeki tüm handler'ları otomatik yükler.
bot_client = Client(
    name="ejderha_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="bot/plugins"),
    in_memory=True,
)

# ── Userbot İstemcisi ─────────────────────────────────────────
# Sesli sohbete katılmak için kullanılan kullanıcı hesabı.
# Session string ile giriş yapar, telefon numarası gerektirmez.
user_client = Client(
    name="ejderha_user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True,
)

# ── PyTgCalls İstemcisi ──────────────────────────────────────
# Sesli sohbetlerde ses akışını yöneten istemci.
# Userbot client üzerinden çalışır.
call_client = PyTgCalls(user_client)
