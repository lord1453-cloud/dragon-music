# ============================================
# 🐲 Ejderha Müzik Botu - Ana Giriş Noktası
# ============================================
# Bot ve userbot istemcilerini başlatır, PyTgCalls'u
# aktif eder ve botu ayakta tutar.
# Graceful shutdown desteği içerir.

import logging
import asyncio
import signal
import sys
import glob
import os

from pytgcalls import idle

from bot.config import BOT_NAME, BOT_VERSION, LOG_LEVEL, DOWNLOADS_DIR
from bot.clients import bot_client, user_client, call_client

# ── Loglama Ayarları ──────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="🐲 %(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _cleanup_downloads():
    """Eski indirme dosyalarını temizler."""
    try:
        for f in glob.glob(os.path.join(DOWNLOADS_DIR, "*")):
            try:
                os.remove(f)
            except Exception:
                pass
    except Exception:
        pass


async def main():
    """Ana async fonksiyon - tüm istemcileri başlatır."""
    logger.info(f"{BOT_NAME} v{BOT_VERSION} başlatılıyor...")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Eski indirme dosyalarını temizle
    _cleanup_downloads()
    logger.info("🔥 Eski indirme dosyaları temizlendi.")

    # Bot istemcisini başlat
    try:
        await bot_client.start()
        bot_info = await bot_client.get_me()
        logger.info(f"🐲 Bot başlatıldı: @{bot_info.username}")
    except Exception as e:
        logger.error(f"❌ Bot istemcisi başlatılamadı: {e}")
        raise

    # Userbot istemcisini başlat
    try:
        await user_client.start()
        user_info = await user_client.get_me()
        logger.info(f"🐉 Userbot başlatıldı: {user_info.first_name}")
    except Exception as e:
        logger.error(f"❌ Userbot başlatılamadı: {e}")
        if "AUTH_KEY_DUPLICATED" in str(e):
            logger.error("⚠️ AUTH_KEY_DUPLICATED Hatası: Bu session string başka bir yerde aynı anda çalışıyor veya eski oturum sonlandırılmadı. Lütfen çalışan diğer bot/process örneklerini kapatın veya yeni bir SESSION_STRING oluşturun.")
        raise

    # PyTgCalls'u başlat
    try:
        await call_client.start()
        logger.info("🌋 PyTgCalls başlatıldı - Sesli sohbet hazır!")
    except Exception as e:
        logger.error(f"❌ PyTgCalls başlatılamadı: {e}")
        raise

    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"✨ {BOT_NAME} tamamen hazır! Ejderha uçuşa geçti!")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Botu ayakta tut (PyTgCalls v1.2.9 idle)
    await idle()

    # Kapatma işlemleri (PyTgCalls v1.2.9'da stop() yoktur, user_client/bot_client stop edilir)
    logger.info("🐲 Ejderha uykuya dalıyor...")
    await user_client.stop()
    await bot_client.stop()
    _cleanup_downloads()
    logger.info("💤 Ejderha uykuya daldı. Hoşça kal!")


if __name__ == "__main__":
    # Graceful shutdown için sinyal yakalama
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: loop.stop())

    # Ana fonksiyonu çalıştır
    asyncio.get_event_loop().run_until_complete(main())
