# ============================================
# 🐲 Ejderha Müzik Botu - String Session Yöneticisi & Üretici
# ============================================
# Pyrogram v2 ile uyumlu, telefon numarası ve 2FA desteğiyle
# temiz bir SESSION_STRING üretir veya mevcut session'ı test eder.

import os
import asyncio
from typing import Optional

from dotenv import load_dotenv  # type: ignore[import-untyped]
from pyrogram import Client  # type: ignore[import-untyped]
from utils.session_cleaner import clean_session_string, validate_session_string

load_dotenv()


async def test_session(api_id: int, api_hash: str, raw_session: str) -> bool:
    """Mevcut session string'in geçerliliğini test eder."""
    cleaned_session = clean_session_string(raw_session)

    if not validate_session_string(cleaned_session):
        print("❌ HATA: Session string Base64 formatına uygun değil (Bozuk padding veya geçersiz karakterler).")
        return False

    print("⏳ Telegram sunucusuna bağlanılıyor...")
    try:
        async with Client(
            name="test_session_checker",
            api_id=api_id,
            api_hash=api_hash,
            session_string=cleaned_session,
            in_memory=True,
        ) as app:
            me = await app.get_me()
            print("\n" + "═" * 55)
            print("✅ SESSION STRING GEÇERLİ VE AKTİF!")
            print(f"👤 İsim: {me.first_name}")
            print(f"🆔 ID: {me.id}")
            print(f"🏷 Kullanıcı Adı: @{me.username or 'Yok'}")
            print(f"📱 Telefon: {me.phone_number or 'Gizli'}")
            print("═" * 55)
            return True
    except Exception as e:
        print(f"\n❌ Bağlantı başarısız oldu: {e}")
        return False


async def generate_new_session(api_id: int, api_hash: str) -> None:
    """Yeni ve temiz bir Pyrogram v2 Session String üretir."""
    print("\n" + "═" * 55)
    print("🐲 Pyrogram String Session Oluşturucu")
    print("═" * 55)
    print("📌 Telefon numaranızı uluslararası formatta girin (Örn: +905xxxxxxxxx)")

    async with Client(
        name="session_generator",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
    ) as app:
        session_str = await app.export_session_string()
        cleaned_session = clean_session_string(session_str)
        me = await app.get_me()

        # Telegram Kayıtlı Mesajlar'a gönder
        saved_msg_info: str
        try:
            await app.send_message(
                "me",
                f"🐲 **Ejderha Müzik Botu - SESSION_STRING** 🐲\n\n"
                f"Hesap: `{me.first_name}` (@{me.username or 'Yok'})\n\n"
                f"```\n{cleaned_session}\n```\n\n"
                f"⚠️ **Uyarı:** Bu metni kimseyle paylaşmayın!",
            )
            saved_msg_info = "✅ Session String ayrıca Telegram'daki 'Kayıtlı Mesajlar' (Saved Messages) kutunuza gönderildi!"
        except Exception:
            saved_msg_info = "⚠️ Kayıtlı Mesajlara gönderilemedi."

        print("\n" + "═" * 55)
        print("🎉 TEBRİKLER! SESSION STRING BAŞARIYLA OLUŞTURULDU:")
        print("═" * 55)
        print(f"\n{cleaned_session}\n")
        print("═" * 55)
        print(saved_msg_info)
        print("📌 Bu string'i .env dosyanızdaki 'SESSION_STRING' değerine yapıştırın.")
        print("═" * 55)


async def main() -> None:
    """Ana menü: mevcut session'ı test et veya yeni session üret."""
    print("═" * 55)
    print("🐲 Ejderha Müzik Botu - Session Aracı")
    print("═" * 55)

    # Ortam değişkenlerini oku
    api_id_env: Optional[str] = os.getenv("API_ID")
    api_hash_env: Optional[str] = os.getenv("API_HASH")
    session_string: Optional[str] = os.getenv("SESSION_STRING")

    # API bilgilerini belirle
    api_id: int
    api_hash: str

    if api_id_env and api_hash_env:
        print(f"✅ .env dosyasından API_ID ({api_id_env}) ve API_HASH yüklendi.")
        use_env = input("Bu API bilgileri kullanılsın mı? (E/H) [Varsayılan: E]: ").strip().lower()
        if use_env in ("", "e", "evet", "y", "yes"):
            api_id = int(api_id_env)
            api_hash = api_hash_env
        else:
            api_id = int(input("API_ID girin: ").strip())
            api_hash = input("API_HASH girin: ").strip()
    else:
        api_id = int(input("API_ID girin: ").strip())
        api_hash = input("API_HASH girin: ").strip()

    print("\nLütfen bir işlem seçin:")
    print("1 - Mevcut SESSION_STRING'i Test Et")
    print("2 - Yeni Bir SESSION_STRING Üret")
    secim = input("Seçiminiz (1/2) [Varsayılan: 2]: ").strip()

    if secim == "1":
        if not session_string:
            session_string = input("Test edilecek SESSION_STRING'i yapıştırın: ").strip()
        success = await test_session(api_id, api_hash, session_string)
        if not success:
            regenerate = input("\nYeni bir session oluşturmak ister misiniz? (E/H): ").strip().lower()
            if regenerate in ("e", "evet", "y", "yes"):
                await generate_new_session(api_id, api_hash)
    else:
        await generate_new_session(api_id, api_hash)


if __name__ == "__main__":
    asyncio.run(main())
