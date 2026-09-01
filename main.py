# ============================================
# 🐲 Ejderha Müzik Botu - Ana Giriş Noktası
# ============================================
# Bot ve userbot istemcilerini başlatır, PyTgCalls'u
# aktif eder ve botu ayakta tutar.
# Graceful shutdown ve gelişmiş hata yönetimi içerir.
# Önemli olayları Telegram log grubuna gönderir.

import os
import sys
import glob
import signal
import asyncio
import logging
import traceback
from datetime import datetime

from bot.config import BOT_NAME, BOT_VERSION, LOG_LEVEL, DOWNLOADS_DIR, LOG_GROUP_ID

# ── 1. Windows Console UTF-8 Desteği & Loglama Ayarları ─────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-22s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EjderhaBot")

from pyrogram import idle
from bot.clients import bot_client, user_client, call_client


# ── 2. Telegram Log Grubu Yardımcı Fonksiyonu ────────────────
async def send_log(text: str) -> None:
    """Belirtilen log grubuna mesaj gönderir. Bot atamazsa Userbot ile dener."""
    if not LOG_GROUP_ID:
        return
    try:
        if bot_client and getattr(bot_client, "is_connected", False):
            await bot_client.send_message(
                chat_id=LOG_GROUP_ID,
                text=text,
            )
            return
    except Exception as e:
        logger.warning(f"Bot istemcisi ile log gönderilemedi: {e}")

    try:
        if user_client and getattr(user_client, "is_connected", False):
            await user_client.send_message(
                chat_id=LOG_GROUP_ID,
                text=text,
            )
    except Exception as e2:
        logger.warning(f"Log grubuna mesaj gönderilemedi: {e2}")


def _cleanup_downloads():
    """Eski indirme dosyalarını temizler."""
    try:
        count = 0
        for f in glob.glob(os.path.join(DOWNLOADS_DIR, "*")):
            try:
                os.remove(f)
                count += 1
            except Exception:
                pass
        if count > 0:
            logger.debug(f"🧹 {count} adet geçici dosya temizlendi.")
    except Exception as e:
        logger.warning(f"İndirme dizini temizlenirken uyarı: {e}")


async def start_services():
    """Tüm istemcileri sırasıyla ve kontrollü şekilde başlatır."""
    loop = asyncio.get_running_loop()
    bot_client.loop = loop
    bot_client.dispatcher.loop = loop
    user_client.loop = loop
    user_client.dispatcher.loop = loop

    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info("═" * 60)
    logger.info(f"🚀 {BOT_NAME} v{BOT_VERSION} Başlatılıyor...")
    logger.info(f"🕒 Başlatma Zamanı: {start_time}")
    logger.info("═" * 60)

    # Eski indirme dosyalarını temizle
    _cleanup_downloads()

    # 0. Otomatik YouTube Çerez / Oturum Yenileyiciyi Başlat
    from utils.cookie_manager import start_cookie_refresher, stop_cookie_refresher
    start_cookie_refresher()

    # 1. Bot İstemcisini Başlat
    try:
        logger.info("🤖 Bot istemcisi bağlanıyor...")
        await bot_client.start()
        bot_info = await bot_client.get_me()
        logger.info(f"✅ Bot bağlandı: @{bot_info.username} [ID: {bot_info.id}]")
    except Exception as e:
        from pyrogram.errors import FloodWait
        if isinstance(e, FloodWait):
            logger.warning(
                f"⏳ Telegram FloodWait: Telegram sunucusu çok fazla ardışık oturum açma nedeniyle "
                f"{e.value} saniye bekleme istedi. {e.value} saniye bekleniyor..."
            )
            await asyncio.sleep(e.value + 2)
            await bot_client.start()
            bot_info = await bot_client.get_me()
            logger.info(f"✅ Bot bağlandı: @{bot_info.username} [ID: {bot_info.id}]")
        else:
            logger.critical(f"❌ Bot istemcisi başlatılamadı: {e}", exc_info=True)
            if "API_ID_INVALID" in str(e):
                logger.error(
                    "👉 ÇÖZÜM: API_ID veya API_HASH geçersiz! "
                    "Lütfen Railway 'Variables' sekmesindeki veya .env dosyasındaki API_ID ve API_HASH "
                    "değerlerini my.telegram.org adresindeki orijinal değerlerle kontrol edin."
                )
            raise

    # 2. Userbot İstemcisini Başlat (Session String)
    try:
        logger.info("🐉 Userbot istemcisi (SESSION_STRING) bağlanıyor...")
        await user_client.start()
        user_info = await user_client.get_me()
        logger.info(f"✅ Userbot bağlandı: {user_info.first_name} [ID: {user_info.id}]")
    except Exception as e:
        logger.critical(f"❌ Userbot başlatılamadı: {e}", exc_info=True)
        err_msg = str(e)
        if "Incorrect padding" in err_msg or "binascii" in err_msg:
            logger.error(
                "👉 ÇÖZÜM: SESSION_STRING geçersiz veya kopyalanırken bozulmuş. "
                "Lütfen 'python generate_session.py' komutunu çalıştırarak yeni bir session string üretin ve .env dosyasına ekleyin."
            )
        elif "AUTH_KEY_DUPLICATED" in err_msg:
            logger.error(
                "👉 ÇÖZÜM: Bu oturum (session) başka bir process veya sunucuda aynı anda aktif. "
                "Çakışan diğer botu kapatın veya yeni bir SESSION_STRING üretin."
            )
        elif "SESSION_REVOKED" in err_msg or "AUTH_KEY_UNREGISTERED" in err_msg:
            logger.error(
                "👉 ÇÖZÜM: Telegram oturumu sonlandırılmış. Lütfen 'generate_session.py' ile yeniden oturum açın."
            )
        # Hata mesajını log grubuna gönder
        await send_log(
            f"🐲 **EJDERHA BOT - KRİTİK HATA** 🐲\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ Userbot başlatılamadı!\n"
            f"📛 Hata: `{err_msg[:200]}`\n"
            f"🕒 Zaman: `{start_time}`"
        )
        raise

    # 3. PyTgCalls Başlat
    if call_client:
        try:
            logger.info("🌋 PyTgCalls ses motoru başlatılıyor...")
            await call_client.start()
            logger.info("✅ PyTgCalls hazır - Sesli sohbet akışı aktif!")
        except Exception as e:
            logger.error(f"❌ PyTgCalls başlatılamadı: {e}", exc_info=True)
            await send_log(
                f"🐲 **EJDERHA BOT - HATA** 🐲\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"❌ PyTgCalls başlatılamadı!\n"
                f"📛 Hata: `{str(e)[:200]}`"
            )
            raise
    else:
        logger.warning("⚠️ PyTgCalls modülü aktif değil, sesli sohbet özellikleri devre dışı.")

    # 4. Harici Web Admin Paneli Senkronizasyonunu Başlat
    try:
        from bot.plugins.group_sync import init_panel_db, _periodic_sync_worker
        init_panel_db()
        asyncio.create_task(_periodic_sync_worker(bot_client))
        logger.info("🌐 Harici Web Paneli grup senkronizasyon motoru aktif edildi.")
    except Exception as e:
        logger.warning(f"Harici Panel senkronizasyonu başlatılamadı: {e}")

    logger.info("═" * 60)
    logger.info(f"✨ {BOT_NAME} tamamen hazır! Ejderha uçuşa geçti!")
    logger.info("═" * 60)

    # ── Başarılı başlatma logunu Telegram grubuna gönder ──
    await send_log(
        f"🐲 **EJDERHA BOT BAŞLATILDI** 🐲\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ **Durum:** Tüm servisler aktif!\n"
        f"🤖 **Bot:** @{bot_info.username}\n"
        f"🐉 **Userbot:** {user_info.first_name}\n"
        f"🌋 **PyTgCalls:** {'Aktif' if call_client else 'Devre Dışı'}\n"
        f"📦 **Sürüm:** `v{BOT_VERSION}`\n"
        f"🕒 **Zaman:** `{start_time}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ Ejderha uçuşa geçti!"
    )


async def stop_services():
    """Çıkış yapılırken istemcileri güvenle kapatır (Graceful Shutdown)."""
    logger.info("🛑 Servisler kapatılıyor...")

    # Kapatma logunu gruba gönder (bot hâlâ bağlıysa)
    try:
        await send_log(
            f"🐲 **EJDERHA BOT KAPATILIYOR** 🐲\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛑 Bot kapatılıyor...\n"
            f"🕒 Zaman: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"💤 Ejderha uykuya dalıyor..."
        )
    except Exception:
        pass

    if user_client and getattr(user_client, "is_connected", False):
        try:
            await user_client.stop()
            logger.info("🔒 Userbot oturumu kapatıldı.")
        except Exception as e:
            logger.warning(f"Userbot kapatılırken hata: {e}")

    if bot_client and getattr(bot_client, "is_connected", False):
        try:
            await bot_client.stop()
            logger.info("🔒 Bot istemcisi kapatıldı.")
        except Exception as e:
            logger.warning(f"Bot kapatılırken hata: {e}")

    try:
        from utils.cookie_manager import stop_cookie_refresher
        stop_cookie_refresher()
    except Exception:
        pass

    _cleanup_downloads()
    logger.info("💤 Ejderha güvenle uykuya daldı.")


async def main():
    try:
        await start_services()
        await idle()
    except asyncio.CancelledError:
        logger.info("İşlem iptal edildi (Cancelled).")
    except Exception as e:
        logger.critical(f"💥 Bot çalışırken kritik hata oluştu: {e}")
        logger.debug(traceback.format_exc())
        # Çalışma zamanı hatasını log grubuna gönder
        try:
            await send_log(
                f"🐲 **EJDERHA BOT - KRİTİK HATA** 🐲\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💥 Çalışma zamanı hatası!\n"
                f"📛 Hata: `{str(e)[:300]}`\n"
                f"🕒 Zaman: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
            )
        except Exception:
            pass
    finally:
        await stop_services()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot kullanıcı tarafından durduruldu.")
