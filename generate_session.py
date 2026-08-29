# ============================================
# 🐲 Ejderha Müzik Botu - String Session Oluşturucu
# ============================================
# Pyrogram v2 ile uyumlu, telefon numarası ve 2FA desteğiyle
# temiz bir SESSION_STRING üretir ve Telegram Kayıtlı Mesajlarınıza gönderir.

import asyncio
import os
from dotenv import load_dotenv
from pyrogram import Client

# Varsa .env dosyasından oku
load_dotenv()

async def generate_session():
    print("=" * 55)
    print("🐲 Ejderha Müzik Botu - Pyrogram String Session Oluşturucu")
    print("=" * 55)
    
    api_id_env = os.getenv("API_ID")
    api_hash_env = os.getenv("API_HASH")
    
    if api_id_env and api_hash_env:
        print(f"✅ .env dosyasından API_ID ({api_id_env}) ve API_HASH bulundu.")
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

    print("\n⏳ Telegram sunucusuna bağlanılıyor...")
    
    # in_memory=True diske session dosyası yazılmasını engeller
    async with Client(
        name="session_generator",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True
    ) as app:
        session_str = await app.export_session_string()
        me = await app.get_me()
        
        # Telegram Kayıtlı Mesajlar'a gönder
        try:
            await app.send_message(
                "me",
                f"🐲 **Ejderha Müzik Botu - SESSION_STRING** 🐲\n\n"
                f"Hesap: `{me.first_name}` (@{me.username or 'Yok'})\n\n"
                f"```\n{session_str}\n```\n\n"
                f"⚠️ **Uyarı:** Bu metni kimseyle paylaşmayın!"
            )
            saved_msg_info = "✅ Session String ayrıca Telegram'daki 'Kayıtlı Mesajlar' (Saved Messages) kutunuza gönderildi!"
        except Exception:
            saved_msg_info = "⚠️ Kayıtlı Mesajlara gönderilemedi."

        print("\n" + "=" * 55)
        print("🎉 TEBRİKLER! SESSION STRING BAŞARIYLA OLUŞTURULDU:")
        print("=" * 55)
        print(f"\n{session_str}\n")
        print("=" * 55)
        print(saved_msg_info)
        print("📌 Bu string'i Railway / .env dosyanızdaki 'SESSION_STRING' değerine yapıştırın.")
        print("=" * 55)

if __name__ == "__main__":
    asyncio.run(generate_session())
