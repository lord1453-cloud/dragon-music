# ============================================
# 🐲 Ejderha Müzik Botu - Yönetici (Admin) Modülü
# ============================================
# /admin, /unadmin, /ban, /unban, /kick ve /kickme
# komutlarını tam yetki kontrolü ve Telegram get_chat_member
# doğrulamasıyla yönetir.

import logging
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions, ChatPrivileges
from pyrogram.enums import ChatMemberStatus, ChatType

from utils.decorators import admin_only, clean_command, get_user_display_name, get_user_id

logger = logging.getLogger(__name__)


async def _extract_target_user(client: Client, message: Message) -> Tuple[Optional[int], Optional[str]]:
    """
    Komutun hedef aldığı kullanıcıyı tespit eder.
    1. Mesaja yanıt verilmişse (reply) yanıtlanan kullanıcının ID'sini alır.
    2. Komut argümanında ID veya @kullanıcıadı verilmişse onu çözer.
    """
    # 1. Reply kontrolü
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        if target:
            name = target.first_name or target.username or f"Kullanıcı_{target.id}"
            return target.id, name
        elif message.reply_to_message.sender_chat:
            return message.reply_to_message.sender_chat.id, message.reply_to_message.sender_chat.title

    # 2. Argüman kontrolü
    if len(message.command) > 1:
        raw_arg = message.command[1].strip()
        if raw_arg.isdigit() or (raw_arg.startswith("-") and raw_arg[1:].isdigit()):
            uid = int(raw_arg)
            return uid, f"Kullanıcı_{uid}"
        elif raw_arg.startswith("@"):
            try:
                user = await client.get_users(raw_arg)
                name = user.first_name or user.username or raw_arg
                return user.id, name
            except Exception as e:
                logger.debug(f"Kullanıcı adı çözülemedi ({raw_arg}): {e}")
                return None, None

    return None, None


# ══════════════════════════════════════════════════════════════
# 1. KULLANICIYI BANLAMA (/yasakla)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["yasakla", "ban"]) & filters.group)
@admin_only("⛔ Bu komut için yetkiniz yok!")
async def ban_command(client: Client, message: Message):
    """
    /yasakla [kullanıcı / yanıt]:
    Yalnızca yöneticiler tarafından çalıştırılabilir.
    Hedef kullanıcıyı gruptan süresiz yasaklar.
    """
    target_id, target_name = await _extract_target_user(client, message)
    if not target_id:
        await message.reply_text("ℹ️ **Kullanım:** Bir mesajı yanıtlayarak `/yasakla` yazın veya `/yasakla @kullanici` şeklinde belirtin.")
        return

    # Botun kendini veya grup sahibini banlamasını engelle
    if target_id == message.chat.id or (message.from_user and target_id == message.from_user.id):
        await message.reply_text("❌ Kendinizi banlayamazsınız!")
        return

    try:
        # Hedef kullanıcının yetkisini kontrol et (Admin banlanamaz)
        member = await client.get_chat_member(message.chat.id, target_id)
        if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
            await message.reply_text("❌ Bir yöneticiyi veya grup sahibini yasaklayamazsınız!")
            return
    except Exception:
        pass

    try:
        await client.ban_chat_member(message.chat.id, target_id)
        admin_name = get_user_display_name(message)
        await message.reply_text(f"🚫 **{target_name}** gruptan yasaklandı.\n👮‍♂️ **Yönetici:** {admin_name}")
    except Exception as e:
        logger.error(f"Banlama hatası: {e}")
        await message.reply_text("❌ Kullanıcı yasaklanamadı! Botun 'Kullanıcıları Yasakla' yetkisi olduğundan emin olun.")


# ══════════════════════════════════════════════════════════════
# 2. BAN KALDIRMA (/yasakkaldır, /banaç)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["yasakkaldır", "yasakkaldir", "banaç", "banac", "unban"]) & filters.group)
@admin_only("⛔ Bu komut için yetkiniz yok!")
async def unban_command(client: Client, message: Message):
    """
    /yasakkaldır [kullanıcı / yanıt]:
    Kullanıcının gruptaki yasaklamasını kaldırır.
    """
    target_id, target_name = await _extract_target_user(client, message)
    if not target_id:
        await message.reply_text("ℹ️ **Kullanım:** `/yasakkaldır <kullanıcı_id veya @kullanıcı>`")
        return

    try:
        await client.unban_chat_member(message.chat.id, target_id)
        await message.reply_text(f"✅ **{target_name}** kullanıcısının yasağı kaldırıldı.")
    except Exception as e:
        logger.error(f"Unban hatası: {e}")
        await message.reply_text("❌ Kullanıcının yasağı kaldırılamadı!")


# ══════════════════════════════════════════════════════════════
# 3. YÖNETİCİ ATAMA (/yetkiver)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["yetkiver", "admin"]) & filters.group)
@admin_only("⛔ Bu komut için yetkiniz yok!")
async def promote_command(client: Client, message: Message):
    """
    /yetkiver [kullanıcı / yanıt]:
    Kullanıcıya standart grup yöneticisi yetkilerini verir.
    """
    target_id, target_name = await _extract_target_user(client, message)
    if not target_id:
        await message.reply_text("ℹ️ **Kullanım:** Bir üyeyi yanıtlayarak `/yetkiver` yazın.")
        return

    try:
        privileges = ChatPrivileges(
            can_change_info=False,
            can_post_messages=True,
            can_edit_messages=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_manage_video_chats=True,
        )
        await client.promote_chat_member(message.chat.id, target_id, privileges=privileges)
        await message.reply_text(f"👑 **{target_name}** başarıyla yönetici yapıldı!")
    except Exception as e:
        logger.error(f"Admin yetki verme hatası: {e}")
        await message.reply_text("❌ Yönetici yetkisi verilemedi! Botun 'Yeni Yönetici Ekleme' yetkisine sahip olduğundan emin olun.")


# ══════════════════════════════════════════════════════════════
# 4. YÖNETİCİLİK ALMA (/yetkial)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["yetkial", "unadmin"]) & filters.group)
@admin_only("⛔ Bu komut için yetkiniz yok!")
async def demote_command(client: Client, message: Message):
    """
    /yetkial [kullanıcı / yanıt]:
    Bir kullanıcının gruptaki yöneticilik yetkilerini tamamen sıfırlar.
    """
    target_id, target_name = await _extract_target_user(client, message)
    if not target_id:
        await message.reply_text("ℹ️ **Kullanım:** Bir yöneticiyi yanıtlayarak `/yetkial` yazın.")
        return

    try:
        # Sıfır yetkili privileges ile yetkilerini geri al
        empty_privileges = ChatPrivileges(
            can_change_info=False,
            can_post_messages=False,
            can_edit_messages=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_invite_users=False,
            can_pin_messages=False,
            can_manage_video_chats=False,
            can_promote_members=False,
        )
        await client.promote_chat_member(message.chat.id, target_id, privileges=empty_privileges)
        await message.reply_text(f"📉 **{target_name}** kullanıcısının yöneticilik yetkileri alındı.")
    except Exception as e:
        logger.error(f"Admin yetki alma hatası: {e}")
        await message.reply_text("❌ Yetkiler geri alınamadı! Botun bu yöneticiyi yönetme hakkı olmayabilir.")


# ══════════════════════════════════════════════════════════════
# 5. KENDİNİ ATMA / AYRILMA (/ayrıl)
# ══════════════════════════════════════════════════════════════
@Client.on_message(clean_command(["ayrıl", "ayril", "banaat", "ayrilgruptan", "kickme"]) & filters.group)
async def kickme_command(client: Client, message: Message):
    """
    /kickme komutu:
    Kullanıcının kendi isteğiyle gruptan geçici olarak çıkarılmasını sağlar.
    Yasaklamaz, yalnızca çıkarır (tekrar davet linkiyle katılabilir).
    """
    if not message.from_user:
        await message.reply_text("❌ Anonim yöneticiler bu komutu kullanamaz!")
        return

    user_id = message.from_user.id
    user_name = get_user_display_name(message)

    try:
        # Önce banlayıp hemen unban ederek 'kick' simülasyonu yap
        await client.ban_chat_member(message.chat.id, user_id)
        await client.unban_chat_member(message.chat.id, user_id)
        await message.reply_text(f"👋 **{user_name}** kendi isteğiyle gruptan ayrıldı.")
    except Exception as e:
        logger.error(f"kickme hatası: {e}")
        await message.reply_text("❌ Gruptan çıkarılamadınız. Botun yetkilerini kontrol edin.")
