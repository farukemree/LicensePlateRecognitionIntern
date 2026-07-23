# ai-service İyileştirme Planı

> **Kapsam:** Yalnızca `ai-service/` (`main.py`, `requirements.txt`, `Dockerfile`, yeni `.env.example`).
> Backend (Go) ve frontend'e **dokunulmaz**. Plan tek bir çalışma oturumunda (tek prompt) uygulanacak şekilde önceliklendirilmiştir.
> **Değişmez kısıt:** Servis uygulama sonunda hâlâ ayağa kalkmalı, iki Gebze kamera thread'i başlamalı ve mevcut tüm endpoint'ler bozulmadan çalışmalıdır.

---

## Bölüm 1 — Kritik: Güvenlik & Konfigürasyon

### 1.1 Gömülü sırları ve sabit adresleri env'e taşı
- **Sorun:** Kamera RTSP şifresi (`center@dhl99`) ve IP'ler kaynak kodda düz metin (`main.py:155,172,179`). Backend adresi de sabit (`DOTNET_API_URL`, `main.py:269`).
- **Yapılacak:**
  - `_GEBZE_SIFRE_ENCODED`, kamera IP/port ve profil değerlerini `os.getenv(...)` ile oku.
  - Yeni `ai-service/.env.example` oluştur; tüm env değişkenlerini varsayılanlarıyla listele.
  - `Dockerfile`/`docker run` bunları `-e` veya `--env-file` ile geçirsin (README'ye tek satır not).
- **Kabul:** Kaynak kodda düz metin şifre kalmaz; env verilmezse eski davranışa düşen makul varsayılanlar çalışır.

### 1.2 `requirements.txt`'e `requests` ekle
- **Sorun:** Kod `import requests` yapıyor ama `requirements.txt`'te yok; yalnızca transitif (ultralytics) geldiği için kırılgan.
- **Yapılacak:** `requests==2.32.3` satırını ekle (kullanılmayan `httpx` satırını kaldır — kodda kullanılmıyor).
- **Kabul:** `pip install -r requirements.txt` sonrası `requests` doğrudan bağımlılık.

---

## Bölüm 2 — Kritik: Backend kontratına hizalanma (plaka + görüntü akışı)

> Bu bölüm projenin asıl hedefi olan "plakayı ve araç görüntüsünü sisteme gönderme" akışını çalışır hale getirir.
> Not: Go tarafı bilinmeyen JSON alanlarını yok sayar (hata vermez), dolayısıyla **fazladan alan göndermek güvenli**; asıl mesele beklenen alanların doğru ad/tiple gitmesidir.

### 2.1 Hedef URL'yi env'den al ve doğru endpoint'e yönlendir
- **Sorun:** `DOTNET_API_URL = "http://192.168.1.141:5000/api/v1/plates/detected"` — repoda olmayan bir .NET adresi. Go backend `:8080/api/v1/anpr/events` dinliyor.
- **Yapılacak:** `BACKEND_EVENTS_URL = os.getenv("BACKEND_EVENTS_URL", "http://localhost:8080/api/v1/anpr/events")`.

### 2.2 Payload'ı Go `WebhookEvent` şemasına hizala
Go `event.go` şunu bekliyor: `depot_id (UUID, zorunlu)`, `camera_id (string)`, `plaka`, `confidence_score`, `image_url`, `detected_at`.
- **Yapılacak:** `send_plate_to_dotnet_sync` içinde POST gövdesini şu alan adlarıyla kur:
  - `plaka_metni` → `plaka`
  - `depo_id (int)` → `depot_id` — **env'den gerçek bir UUID** (`DEPOT_ID`), kamera→depo eşlemesi config'te.
  - `kamera_id (int)` → `camera_id` (string'e çevir)
  - `guven_skoru` → `confidence_score`
  - `tarih_saat` → `detected_at`
  - `yon`, `arac_tipi`, base64 alanları fazladan gönderilebilir (Go yok sayar) — ama asıl görsel için 2.3.
- **Kabul:** `POST /api/v1/anpr/events`'e gönderilen gövde Go tarafında 200 döner (depot UUID DB'de mevcutsa).

### 2.3 Araç görüntüsünü erişilebilir kıl (image_url)
- **Sorun:** Görsel şu an sadece base64 gövdede; Go tarafında saklanacak alan yok, `image_url` (URL) bekleniyor.
- **Yapılacak (ai-service içi, tek başına yeterli):**
  - En iyi kırpılmış plaka + tam kareyi `captures/` klasörüne kaydet (dosya adı: `kam{id}_{plaka}_{ts}.jpg`).
  - FastAPI `StaticFiles` ile `/captures` route'unu mount et.
  - `image_url = f"{AI_SERVICE_PUBLIC_BASE_URL}/captures/{dosya_adi}"` olarak payload'a koy.
  - `base64` alanlarını geriye dönük uyumluluk için opsiyonel bırak (silme).
- **Kabul:** Gönderilen `image_url` tarayıcıdan açılınca gerçek araç/plaka görselini gösterir.

---

## Bölüm 3 — Dayanıklılık (canlı 7/24 çalışma için)

### 3.1 Kare işleme döngüsünü hata-güvenli yap
- **Sorun:** `while True` içindeki YOLO/OCR bloğunda `try/except` yok (`main.py:801+`). Tek bir bozuk karede fırlayan exception, o kameranın thread'ini **kalıcı olarak** öldürür.
- **Yapılacak:** Döngü gövdesini `try/except Exception`'a al; hatayı logla, `continue` ile devam et.
- **Kabul:** Yapay bir exception enjekte edildiğinde thread ölmez, log basıp sonraki kareye geçer.

### 3.2 Model çıkarımlarına thread kilidi
- **Sorun:** İki kamera thread'i aynı global `model`, `detection_model`, `reader` nesnelerini paylaşıyor. PyTorch/Ultralytics çıkarımı çok-thread'de güvenli değil → çakışma/bozuk sonuç riski.
- **Yapılacak:** Modül düzeyinde `INFERENCE_LOCK = threading.Lock()`; her `model(...)`, `detection_model(...)`, `reader.readtext(...)` çağrısını kilit altına al (ya da her thread'e ayrı `Reader` ver).
- **Kabul:** İki kamera aynı anda çalışırken sonuçlar birbirine karışmaz.

### 3.3 Zaman pencereli tekrar-gönderim filtresi
- **Sorun:** `son_okunan_plaka` yalnızca son plakayı hatırlıyor ve süresiz bloke ediyor (`main.py:1069`). Aynı plaka aynı kameradan tekrar geçerse bir daha asla gönderilmez.
- **Yapılacak:** `{plaka: son_gonderim_zamani}` sözlüğü tut; `PLAKA_TEKRAR_PENCERESI` (örn. 30 sn) içinde tekrarı engelle, sonrasında tekrar gönderime izin ver.
- **Kabul:** Aynı plaka pencere dolduktan sonra yeniden gönderilebilir.

---

## Bölüm 4 — Modernizasyon & Kalite

- **4.1 `print` → `logging`:** Modül düzeyinde `logging` kur (seviye env'den: `LOG_LEVEL`). Emoji'li mesajlar korunabilir ama `logger.info/warning/error` üzerinden.
- **4.2 Deprecated `datetime.utcnow()`:** `datetime.now(timezone.utc)` ile değiştir (`main.py:1100`).
- **4.3 Deprecated `@app.on_event("startup")`:** FastAPI `lifespan` context manager'a taşı (`main.py:1286`).
- **4.4 Sağlık uçları:** Mevcut `/`'a ek `/healthz` (canlı) ve `/readyz` (modeller yüklendi + en az bir kamera thread'i canlı) ekle.

---

## Bölüm 5 — (Opsiyonel / Stretch) OCR & tespit ince ayarları

Zaman kalırsa; bu maddeler bağımsız ve atlanabilir:
- Sabit eşikleri env'e al: blur eşiği (`keskinlik_skoru < 100`), `MIN_GUVEN_ESIGI`, `EN_IYI_KARE_SAYISI`.
- `plaka_ocr_preprocessing` → `plakayi_izole_et` → `on_isleme_varyantlari` zincirindeki **çok katlı resize**'ı gözden geçir (400px + 3x üst üste büyütme bulanıklaştırıyor olabilir).
- `captures/` için basit temizlik (N günden eski dosyaları sil) — disk şişmesini önle.

---

## Kapsam dışı (bilerek — ayrı iş)
- Go backend'e görsel saklama kolonu / DB migration eklemek.
- Frontend'e WebSocket istemcisi ve görsel gösterimi bağlamak.
- Gerçek model fine-tuning (retrain veri seti zaten birikiyor, ayrı bir görev).

---

## Uygulama sırası (tek oturum)
1 → 2 → 3 zorunlu çekirdek; 4 hızlı ve düşük riskli; 5 yalnızca zaman kalırsa.

## ▶️ Tek-prompt yürütme talimatı (kopyala-yapıştır)

> `ai-service/IYILESTIRME_PLANI.md` dosyasındaki planı uygula. Bölüm 1–4'ü tamamen, Bölüm 5'i zaman kalırsa yap.
> Yalnızca `ai-service/` içindeki dosyaları değiştir (`main.py`, `requirements.txt`, `Dockerfile`, yeni `.env.example`).
> Her env değişkeni için eski davranışa düşen bir varsayılan bırak; servis değişiklik sonrası hâlâ ayağa kalkmalı ve iki kamera thread'i başlamalı.
> Backend/frontend'e dokunma. Bitince değiştirdiğin dosyaların ve her bölümde ne yaptığının kısa özetini ver.
