# 🐲 Ejderha Müzik Botu

Telegram sesli sohbetlerinde çalışan, ejderha temalı, modüler ve yüksek performanslı bir müzik botu.

## ✨ Özellikler

- 🎵 **Sesli Sohbette Müzik Çalma** - YouTube'dan arama yaparak sesli sohbette müzik çalar
- 🎬 **Görüntülü Yayın (Video Stream)** - 720p HD MP4 video yayını desteği (`/voynat`, `/vplay`)
- 🟢 **Spotify Desteği** - Spotify şarkı, albüm ve çalma listesi linklerini otomatik algılar ve YouTube üzerinden kuyruğa ekler
- 🍪 **YouTube 403 / Bot Koruması** - `cookies.txt` entegrasyonu ile "Sign in to confirm you're not a bot" hatasını çözer
- 📥 **Müzik İndirme** - Şarkıları MP3 (320kbps) olarak indirip Telegram'a gönderir
- 📋 **Kuyruk Sistemi** - Birden fazla şarkı veya videoyu sıraya ekleyebilme
- ⏸️ **Gelişmiş Kontroller** - Duraklatma, devam ettirme, atlama, karıştırma, temizleme
- 🐲 **Ejderha Teması** - Fantastik dil ve ejderha emojileriyle benzersiz deneyim
- 🎛️ **Inline Menü** - Butonlarla gezinilebilir detaylı menü sistemi

## 📋 Komutlar

| Komut | Açıklama |
|-------|----------|
| `/start` veya `/menu` | Ejderha temalı karşılama menüsünü açar |
| `/oynat <şarkı adı / Spotify / YouTube>` | Şarkıyı ses olarak çalar veya sıraya ekler |
| `/voynat <video adı veya link>` | 720p HD görüntülü yayın başlatır veya sıraya ekler |
| `/duraklat` | Yayını duraklatır |
| `/devam` | Yayını devam ettirir |
| `/gec` | Sıradaki şarkıya/videoya geçer |
| `/karistir` | Kuyruktaki bekleyen şarkıları karıştırır |
| `/temizle` | Bekleyen kuyruğu temizler |
| `/bitir` | Yayını durdurur, kuyruğu temizler ve ayrılır |
| `/sira` | Müzik/video kuyruğunu listeler |
| `/indir <şarkı adı veya link>` | Şarkıyı MP3 olarak indirir ve gönderir |


## 🔧 Gereksinimler

- Python 3.10+
- FFmpeg
- Telegram Bot Token
- Telegram API ID ve API Hash
- Pyrogram Session String

## 🚀 Kurulum

### 📌 Adım 1: Ortam Değişkenlerini Hazırlayın

`.env.example` dosyasını `.env` olarak kopyalayın ve değerleri doldurun:

```bash
cp .env.example .env
```

Gerekli değişkenler:

| Değişken | Açıklama | Nereden Alınır? |
|----------|----------|-----------------|
| `BOT_TOKEN` | Bot token'ı | [@BotFather](https://t.me/BotFather) |
| `API_ID` | Telegram API ID | [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Telegram API Hash | [my.telegram.org](https://my.telegram.org) |
| `SESSION_STRING` | Pyrogram session string | Aşağıdaki adıma bakın |

### 📌 Adım 2: Session String Üretin

Session string, sesli sohbete katılmak için gereken kullanıcı hesabı oturumudur:

```bash
pip install pyrogram tgcrypto
python -c "
from pyrogram import Client
import asyncio

async def main():
    async with Client('session', api_id=API_ID, api_hash='API_HASH') as app:
        print(await app.export_session_string())

asyncio.run(main())
"
```

> ⚠️ `API_ID` ve `API_HASH` değerlerini kendi değerlerinizle değiştirin.
> Telefon numaranız ve doğrulama kodunuz sorulacaktır.

---

### 🚂 Railway ile Kurulum

1. Bu projeyi GitHub'a yükleyin
2. [Railway.app](https://railway.app) hesabınıza giriş yapın
3. **New Project** → **Deploy from GitHub repo** seçin
4. Repo'nuzu seçin
5. **Variables** sekmesinden `.env` değişkenlerini ekleyin:
   - `BOT_TOKEN`
   - `API_ID`
   - `API_HASH`
   - `SESSION_STRING`
6. Deploy butonuna tıklayın ✅

> Railway otomatik olarak `apt.txt`'deki FFmpeg'i, `requirements.txt`'deki Python paketlerini
> ve `Procfile`'daki başlatma komutunu kullanacaktır.

---

### 🖥️ Ubuntu VDS ile Kurulum

#### 1. Sistem Güncellemesi ve Bağımlılıklar

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv ffmpeg git
```

#### 2. Projeyi İndirin

```bash
git clone https://github.com/KULLANICI_ADI/spideymuzikbot.git
cd spideymuzikbot
```

#### 3. Sanal Ortam Oluşturun

```bash
python3 -m venv venv
source venv/bin/activate
```

#### 4. Python Paketlerini Kurun

```bash
pip install -r requirements.txt
```

#### 5. Ortam Değişkenlerini Ayarlayın

```bash
cp .env.example .env
nano .env
# Tüm değişkenleri doldurun ve kaydedin
```

#### 6. Botu Başlatın

```bash
python main.py
```

#### 7. (Opsiyonel) Arka Planda Çalıştırma - systemd

```bash
sudo nano /etc/systemd/system/ejderhabot.service
```

Aşağıdaki içeriği yapıştırın:

```ini
[Unit]
Description=Ejderha Müzik Botu
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/spideymuzikbot
ExecStart=/root/spideymuzikbot/venv/bin/python main.py
Restart=always
RestartSec=10
Environment=PATH=/root/spideymuzikbot/venv/bin:/usr/local/bin:/usr/bin

[Install]
WantedBy=multi-user.target
```

Servisi aktif edin:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ejderhabot
sudo systemctl start ejderhabot
```

Logları kontrol etmek için:

```bash
sudo journalctl -u ejderhabot -f
```

---

## 📁 Proje Yapısı

```
spideymuzikbot/
├── bot/
│   ├── __init__.py           # Bot paket başlatıcı
│   ├── clients.py            # Pyrogram & PyTgCalls istemcileri
│   ├── config.py             # Yapılandırma yönetimi
│   ├── theme.py              # Ejderha temalı mesajlar ve menüler
│   └── plugins/
│       ├── __init__.py
│       ├── start.py          # /start, /menu komutları
│       ├── play.py           # /oynat komutu
│       ├── controls.py       # /duraklat, /devam, /gec
│       ├── queue.py          # /sira komutu
│       ├── download.py       # /indir komutu
│       └── callbacks.py      # Inline buton handler'ları
├── utils/
│   ├── __init__.py
│   ├── queue_manager.py      # Kuyruk yönetim sınıfı
│   └── ytdl.py               # YouTube arama ve indirme
├── .env.example              # Örnek ortam değişkenleri
├── main.py                   # Ana giriş noktası
├── requirements.txt          # Python bağımlılıkları
├── Procfile                  # Railway deployment
├── apt.txt                   # Sistem bağımlılıkları
├── runtime.txt               # Python sürümü
└── README.md                 # Bu dosya
```

## 🐲 Ejderha Teması

Bot, tüm mesajlarında ejderha temalı fantastik bir dil kullanır:

- 🐲 *"Ejderha uyanıyor..."*
- 🔥 *"Müzik ejderhanın nefesiyle çalıyor..."*
- 🌋 *"Ejderha pençeleriyle müziği kapıyor..."*
- ⚔️ *"Ejderha kanat çırptı! Sıradaki şarkıya geçiyor..."*

## 📄 Lisans

Bu proje açık kaynaklıdır. İstediğiniz gibi kullanabilir ve değiştirebilirsiniz.

---

*🐲 Kod ateşle yazılır, müzikle çalınır! 🔥*
