# ============================================
# 🐲 Ejderha Müzik Botu - Harici Web Admin Paneli
# ============================================
# Flask tabanlı bağımsız Web Sunucusu.
# Botun üye olduğu tüm grupları, kurucuları, üye sayılarını
# ve canlı durum göstergesini sunar.

import os
import sqlite3
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)
logger = logging.getLogger("PanelServer")

# ── Flask Uygulama Tanımı ─────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

# Güvenlik Ayarları
app.secret_key = os.getenv("SECRET_KEY", os.getenv("PANEL_SECRET", "ejderha_secret_key_2026_super_secure"))
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "ejderha2026")
PANEL_PORT = int(os.getenv("PANEL_PORT", os.getenv("PORT", "8080")))
DB_PATH = os.path.join(BASE_DIR, "data", "panel_data.db")


# ── Veritabanı Okuma Yardımcıları ────────────────────────────
def get_db_connection():
    """panel_data.db veritabanına bağlantı oluşturur."""
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_if_needed():
    """Gerekirse tabloları ilklendirir."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                chat_type TEXT,
                username TEXT,
                owner_id INTEGER,
                owner_name TEXT,
                owner_username TEXT,
                members_count INTEGER,
                bot_role TEXT,
                is_admin INTEGER,
                last_sync TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_status (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Veritabanı kontrol hatası: {e}")


def get_system_status() -> dict:
    """Botun canlılık, sürüm ve senkronizasyon durumunu çeker."""
    status_dict = {}
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT key, value, updated_at FROM system_status").fetchall()
        conn.close()
        for r in rows:
            status_dict[r["key"]] = {
                "value": r["value"],
                "updated_at": r["updated_at"]
            }
    except Exception:
        pass
    return status_dict


def is_bot_online(status_dict: dict) -> bool:
    """Heartbeat zamanına bakarak botun aktif (canlı) olup olmadığını belirler."""
    if "bot_heartbeat" not in status_dict:
        return False
    try:
        hb_time_str = status_dict["bot_heartbeat"]["updated_at"]
        hb_time = datetime.strptime(hb_time_str, "%Y-%m-%d %H:%M:%S")
        # Son 90 saniye içinde sinyal geldiyse canlıdır
        return (datetime.now() - hb_time) < timedelta(seconds=90)
    except Exception:
        return False


def get_all_groups() -> list:
    """Veritabanındaki tüm grupları çeker."""
    groups = []
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT * FROM groups ORDER BY members_count DESC").fetchall()
        conn.close()
        for r in rows:
            groups.append(dict(r))
    except Exception as e:
        logger.error(f"Gruplar okunamadı: {e}")
    return groups


# ── Giriş / Yetkilendirme Dekoratörü ─────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ── Rotalar (Routes) ──────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    """Yönetici giriş sayfası."""
    if session.get("logged_in"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == PANEL_PASSWORD:
            session["logged_in"] = True
            session["login_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return redirect(url_for("index"))
        else:
            error = "Geçersiz şifre! Lütfen tekrar deneyin."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    """Oturumu kapatır."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    """Ana Admin Paneli Dashboard'u."""
    init_db_if_needed()
    groups = get_all_groups()
    sys_status = get_system_status()
    bot_online = is_bot_online(sys_status)

    total_groups = len(groups)
    total_members = sum(g.get("members_count", 0) for g in groups)
    admin_groups = sum(1 for g in groups if g.get("is_admin") == 1)
    supergroups = sum(1 for g in groups if g.get("chat_type") == "supergroup")
    channels = sum(1 for g in groups if g.get("chat_type") == "channel")

    last_sync = sys_status.get("last_sync_time", {}).get("value", "Henüz yapılmadı")
    bot_version = sys_status.get("bot_version", {}).get("value", "v1.2.0")

    return render_template(
        "index.html",
        groups=groups,
        total_groups=total_groups,
        total_members=total_members,
        admin_groups=admin_groups,
        supergroups=supergroups,
        channels=channels,
        bot_online=bot_online,
        bot_version=bot_version,
        last_sync=last_sync,
    )


@app.route("/api/stats")
@login_required
def api_stats():
    """Anlık JSON durum çıktısı."""
    groups = get_all_groups()
    sys_status = get_system_status()
    return jsonify({
        "status": "success",
        "bot_online": is_bot_online(sys_status),
        "total_groups": len(groups),
        "total_members": sum(g.get("members_count", 0) for g in groups),
        "admin_groups": sum(1 for g in groups if g.get("is_admin") == 1),
        "last_sync": sys_status.get("last_sync_time", {}).get("value", "Bilinmiyor"),
        "groups": groups,
    })


BOT_TOKEN = os.getenv("BOT_TOKEN", "")


@app.route("/api/broadcast", methods=["POST"])
@login_required
def api_broadcast():
    """Web panelinden tüm gruplara doğrudan toplu duyuru gönderir."""
    import json
    import urllib.request
    import time

    data = request.get_json() or {}
    message_text = data.get("message", "").strip()

    if not message_text:
        return jsonify({"status": "error", "message": "Duyuru metni boş olamaz!"}), 400

    if not BOT_TOKEN:
        return jsonify({"status": "error", "message": "BOT_TOKEN .env dosyasında bulunamadı!"}), 500

    groups = get_all_groups()
    if not groups:
        return jsonify({"status": "error", "message": "Veritabanında kayıtlı grup bulunamadı!"}), 404

    formatted_text = f"🐲 **EJDERHA RESMİ DUYURU** 🐲\n━━━━━━━━━━━━━━━━━━━━━━━━\n{message_text}\n━━━━━━━━━━━━━━━━━━━━━━━━"

    success_count = 0
    failed_count = 0
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    for group in groups:
        chat_id = group.get("chat_id")
        if not chat_id:
            continue

        payload = {
            "chat_id": chat_id,
            "text": formatted_text,
            "parse_mode": "Markdown",
        }
        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    success_count += 1
                else:
                    failed_count += 1
        except Exception:
            failed_count += 1

        time.sleep(0.08)

    return jsonify({
        "status": "success",
        "total": len(groups),
        "success_count": success_count,
        "failed_count": failed_count,
    })


# ── Başlatıcı ────────────────────────────────────────────────
if __name__ == "__main__":
    init_db_if_needed()
    print("=" * 60)
    print("🐲 EJDERHA BOT - HARİCİ WEB ADMİN PANELİ BAŞLATILIYOR")
    print(f"🌐 Panel Adresi: http://0.0.0.0:{PANEL_PORT}")
    print(f"🔑 Giriş Şifresi: (PANEL_PASSWORD ortam değişkeni veya varsayılan)")
    print("=" * 60)
    app.run(host="0.0.0.0", port=PANEL_PORT, debug=False)
