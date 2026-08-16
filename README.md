# astro-engine

Natal harita hesap servisi. Blogun Next.js uygulaması bunu `127.0.0.1:8787`
üzerinden çağırır; servis **dışarıya açık değildir**.

Plan ve gerekçeler: repo kökündeki [`NATAL-PLAN.md`](../NATAL-PLAN.md).

## Kurulum

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Çalıştırma

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8787 --workers 1
```

`--host 127.0.0.1` **pazarlıksız.** `0.0.0.0` yazılırsa motor tüm internete
açılır ve önünde hiçbir yetki katmanı yoktur.

Üretimde PM2 yönetir (`ecosystem.config.cjs`).

## Uçlar

| | |
|---|---|
| `GET /health` | Gerçek bir hesap yapar. Sadece `{"ok":true}` değil — efemeris dosyaları eksikse bunu yalnız gerçek hesap yakalar. |
| `GET /v1/geocode?q=izmir&limit=5` | Open-Meteo proxy + `timezonefinder` ile IANA zone |
| `POST /v1/natal` | Natal harita: gezegenler, eksenler, ev cuspları, açılar, dağılımlar, SVG çark, LLM bağlamı |

İstek/yanıt alanları **camelCase**; Python içinde snake_case, dönüşüm
Pydantic alias ile.

## İki kural

**1. Saat dilimi ADIYLA geçilir.** `"Europe/Istanbul"` — sayısal offset
(`"+03:00"`) bilerek reddedilir (`UNKNOWN_TIMEZONE`). Türkiye Eylül
2016'dan beri sabit UTC+3, öncesinde yaz saati vardı; sabit offset 2016
öncesi yaz doğumlarını bir saat kaydırır ve yükselen ile tüm ev sistemi
değişir. Sessiz ve ölümcül bir hata.

**2. Kerykeion `online=False` ile çağrılır.** Varsayılanı `True` ve o hâlde
lat/lng/tz verilse bile GeoNames'e gitmeye çalışır. Motorun tek dış çağrısı
geocoding olmalı.

## Lisans — okuyun

Kerykeion **AGPL-3.0**, Swiss Ephemeris (pyswisseph) **AGPL-3.0 veya
ticari**. Bu klasör Kerykeion'ı import ettiği için onunla tek program
sayılır ve AGPL kapsamındadır.

AGPL'in 13. maddesi kaynağı **"programla ağ üzerinden etkileşen
kullanıcılara"** sunmayı şart koşar. "Dağıtmıyorum, kendi sunucumda
çalıştırıyorum" bir muafiyet **değildir** — AGPL tam olarak bu boşluğu
kapatmak için yazıldı.

| Durum | Yükümlülük |
|---|---|
| `/admin` altında, tek kullanıcı site sahibi | **Yok** — bugünkü durum |
| Ziyaretçiye açık bir sayfa | Bu klasörün kaynağına bir bağlantı |
| API'yi satmak | Aynı + müşteriye de sunmak → Swiss Ephemeris ticari lisansı |

**Bugün yapılacak bir şey yok:** `/admin/astro-test` oturum korumalı.
Aracı ziyaretçilere açtığınız gün bu klasörü erişilebilir bir yere koyup
sayfaya "motor kaynak kodu" bağlantısı ekleyin. AGPL "dünyaya yayınla"
demiyor, "o hizmeti kullanana sun" diyor.

Blogun kendi kodu, veritabanı ve içerikleri bu kapsamda **değildir** —
ayrı process, HTTP üzerinden konuşuyor.

> Bunlar lisans metninin özeti, hukuki tavsiye değil.
