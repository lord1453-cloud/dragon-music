# ============================================
# 🐲 Ejderha Müzik Botu - İndirme Köprüsü
# ============================================
# /video ve /indir komutları artık merkezi ve optimize edilmiş
# bot/plugins/video.py üzerinden yönetilmektedir.
# Çift handler çakışmasını önlemek için bu dosya köprü olarak tutulur.

from bot.plugins.video import video_download_command, audio_download_command

__all__ = ["video_download_command", "audio_download_command"]
