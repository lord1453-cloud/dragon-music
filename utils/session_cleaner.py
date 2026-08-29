# ============================================
# 🐲 Ejderha Müzik Botu - Session Cleaner & Validator
# ============================================
import re
import base64
import logging

logger = logging.getLogger(__name__)


def clean_session_string(session_str: str) -> str:
    """
    Ortam değişkeninden veya .env dosyasından okunan SESSION_STRING değerini
    temizler, gizli kaçış karakterlerini arındırır ve eksik Base64 padding'ini tamamlar.
    """
    if not session_str:
        return ""

    # 1. Baş ve sondaki boşlukları, yeni satırları ve tırnak işaretlerini temizle
    cleaned = session_str.strip().strip("'\"").strip()

    # 2. String içerisindeki görünmez \r, \n, \t veya boşluk karakterlerini temizle
    cleaned = re.sub(r"[\r\n\t\s]+", "", cleaned)

    # 3. Base64 URL-safe padding kontrolü ve tamamlaması (-len % 4 kuralı)
    missing_padding = len(cleaned) % 4
    if missing_padding != 0:
        cleaned += "=" * (4 - missing_padding)

    return cleaned


def validate_session_string(session_str: str) -> bool:
    """
    Session string'in Base64 formatına uygun decode edilip edilemediğini test eder.
    """
    if not session_str:
        return False
    try:
        cleaned = clean_session_string(session_str)
        base64.urlsafe_b64decode(cleaned.encode("ascii"))
        return True
    except Exception as e:
        logger.error(f"❌ SESSION_STRING Base64 çözümleme hatası: {e}")
        return False
