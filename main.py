# ============================================
# 🐲 Ejderha Müzik Botu - Ana Giriş Noktası
# ============================================
# Bot ve userbot istemcilerini başlatır, PyTgCalls'u
# aktif eder ve botu ayakta tutar.
# Graceful shutdown ve gelişmiş hata yönetimi içerir.

import os
import sys
import glob
import signal
import asyncio
import logging
import traceback
from datetime import datetime

from bot.config import BOT_NAME, BOT_VERSION, LOG_LEVEL, DOWNLOADS_DIR

# ── 1. Loglama Ayarları ──────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-22s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EjderhaBot")

try:
    from pytgcalls import idle  # type: ignore
except Exception:
    async def idle():  # type: ignore
        while True:
            await asyncio.sleep(3600)

from bot.clients import bot_client, user_client, call_client


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
    logger.info("═" * 60)
    logger.info(f"🚀 {BOT_NAME} v{BOT_VERSION} Başlatılıyor...")
    logger.info(f"🕒 Başlatma Zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("═" * 60)

    # Eski indirme dosyalarını temizle
    _cleanup_downloads()

    # 1. Bot İstemcisini Başlat
    try:
        logger.info("🤖 Bot istemcisi bağlanıyor...")
        await bot_client.start()
        bot_info = await bot_client.get_me()
        logger.info(f"✅ Bot bağlandı: @{bot_info.username} [ID: {bot_info.id}]")
    except Exception as e:
        logger.critical(f"❌ Bot istemcisi başlatılamadı: {e}", exc_info=True)
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
        raise

    # 3. PyTgCalls Başlat
    if call_client:
        try:
            logger.info("🌋 PyTgCalls ses motoru başlatılıyor...")
            await call_client.start()
            logger.info("✅ PyTgCalls hazır - Sesli sohbet akışı aktif!")
        except Exception as e:
            logger.error(f"❌ PyTgCalls başlatılamadı: {e}", exc_info=True)
            raise
    else:
        logger.warning("⚠️ PyTgCalls modülü aktif değil, sesli sohbet özellikleri devre dışı.")

    logger.info("═" * 60)
    logger.info(f"✨ {BOT_NAME} tamamen hazır! Ejderha uçuşa geçti!")
    logger.info("═" * 60)


async def stop_services():
    """Çıkış yapılırken istemcileri güvenle kapatır (Graceful Shutdown)."""
    logger.info("🛑 Servisler kapatılıyor...")

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
    finally:
        await stop_services()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Graceful shutdown sinyal yakalama (Linux / Docker)
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(stop_services()))

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Klavyeden kesme sinyali (Ctrl+C) alındı.")
    finally:
        loop.close()
