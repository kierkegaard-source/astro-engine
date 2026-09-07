# syntax=docker/dockerfile:1
#
# astro-engine — natal harita hesap servisi (FastAPI + kerykeion/Swiss Ephemeris).
# Coolify: Build Pack Dockerfile, Base Directory /astro-engine, port 8787.
#
# ## Neden Docker, NATAL-PLAN.md Bölüm 6 venv+PM2 derken
#
# Plan üç gerekçe sayıyor; bu sunucuda üçü de karşılanmış durumda:
#   1. "Docker'ın UFW tuzağı": port YAYINLANMIYOR. Coolify'da bu uygulamaya
#      domain verilmiyor ve hiçbir port dışarı açılmıyor; servis yalnız
#      `coolify` iç ağından, container adıyla erişilebilir. Planın
#      `--host 127.0.0.1` ile aldığı sonucun container karşılığı bu.
#      Aşağıdaki 0.0.0.0 container'ın KENDİ ağ arayüzü, host değil.
#   2. "Yeni altyapı parçası yok": bu sunucuda PM2 yok, Docker zaten var.
#      Yeni parça Docker değil, PM2 olurdu.
#   3. "Doğrulanamaz": burada doğrulanıyor, sunucuda derlenip health
#      uçlarıyla sınanıyor.
#
# Blog ona `ASTRO_ENGINE_URL` ile bağlanıyor. Motor kapalıyken blog çalışmaya
# devam eder, yalnız natal harita 503 döner.

# Python 3.11, 3.12 değil: requirements.txt pyswisseph'i 2.10.3.2'ye sabitliyor
# ve o sürüm PyPI'da yalnız cp310/cp311 için hazır Linux ikilisi yayınlıyor.
# 3.12'de pip kaynaktan derlemeye düşer, yani imaja gcc ve Python başlıkları
# girer; bu sunucu 4 GB ve build sırasında iki kez kilitlendi, derleme yükünü
# taşımaya gerek yok. kerykeion >=3.10 istiyor, 3.11 aralıkta.
FROM python:3.11-slim AS base

# Efemeris hesapları saat dilimi verisi istiyor; slim imajda tzdata paketi
# yok ve requirements.txt'teki tzdata modülü Python tarafını çözüyor,
# sistem tarafı için bu satır. curl da health kontrolü için.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Bağımlılıklar ayrı katmanda: app/ değiştiğinde pip tekrar koşmasın.
# Sürümler requirements.txt'te SABİT, orada gerekçesi yazılı.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Kök olmayan kullanıcı. Servis hiçbir şey yazmıyor, salt hesap yapıyor.
RUN useradd --system --create-home --uid 10001 engine \
    && chown -R engine:engine /srv
USER engine

EXPOSE 8787

# /health boş bir "ok" dönmüyor, gerçek bir hesap yapıyor: efemeris dosyaları
# eksikse yeşil görünmesin (app/main.py'deki not).
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8787/health >/dev/null || exit 1

# workers 1: sunucu 4 GB ve altı site daha var; kerykeion süreç başına
# yüz megabaytlarca efemeris verisi tutuyor.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787", "--workers", "1"]
