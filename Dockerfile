# ============================================
# 🐲 Ejderha Müzik Botu - Dockerfile (Railway & Server)
# ============================================
# ntgcalls kütüphanesinin ihtiyaç duyduğu X11 ve FFmpeg
# sistem kütüphanelerini Debian/Ubuntu kök dizinine kurar.

FROM python:3.11-slim

# ── Sistem Bağımlılıkları ve X11 Kütüphaneleri ────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libx11-6 \
    libxext6 \
    libxrandr2 \
    libxdamage1 \
    libxfixes3 \
    libxcb1 \
    libasound2 \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── Çalışma Dizini ────────────────────────────────────────────
WORKDIR /app

# ── Python Bağımlılıkları ─────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Proje Dosyaları ───────────────────────────────────────────
COPY . .

# ── Başlatma Komutu ───────────────────────────────────────────
CMD ["python", "main.py"]
