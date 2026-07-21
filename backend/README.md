# Plaka Takip Sistemi — Backend

Depo/tesis giris-cikis noktalarinda ANPR (plaka tanima) ile araclari otomatik taniyan,
guvenlik gorevlisinin onayiyla kaydeden, kara liste kontrolu yapan, coklu depo destekleyen
ve zamanla ogrenen (human-in-the-loop feedback) platformun Go backend'i.

## 1. Mimari Ozet

- **Modeler monolit**: tek bir binary (`cmd/api`), icinde `internal/<modul>` paketleri net
  sinirlarla ayrilmis (depot, vehicle, driver, vehiclelog, blacklist, expectedarrival, anpr,
  realtime, notification, cache, audit, auth).
- Her modul **Repository -> Service -> Handler** katmanlarina ayrilir; katmanlar interface
  uzerinden baglanir (test edilebilirlik icin).
- **Gin** HTTP router, **pgx** ile PostgreSQL, **gorilla/websocket** ile depo bazli "oda"
  mantigina sahip realtime hub, **Redis opsiyonel** (cache.Cache interface arkasinda, kapaliyken
  NoopCache devreye girer), **Web Push (VAPID)** ile SMTP'siz sistem-ici bildirim.
- Kimlik dogrulama: backend Keycloak'a (OIDC) baglanmaz, sadece JWKS uzerinden JWT imzasini
  dogrular ve token'daki `sub` alanindan yerel `user` tablosundaki rol/depo erisimini yukler.
- ANPR (YOLOv8) ve ML servisleri **ayri Python mikroservisleridir**; bu repo sadece bunlarla
  HTTP webhook (`POST /api/v1/anpr/events`) ve okuma endpoint'i (`GET /api/v1/anpr/corrections`)
  uzerinden haberlesir.

## 2. Kurulum On Kosullari

- Go 1.25+ (yerel gelistirme `go1.26` ile test edildi; `Dockerfile` icinde `golang:1.25-bookworm` kullanilir)
- Docker + Docker Compose plugin (PostgreSQL/Redis'i container olarak calistirmak icin)
- (Opsiyonel, yerel gelistirme icin) yerel PostgreSQL 16+

Bagimliliklar `go.mod`/`go.sum` icinde sabitlenmistir; klonladiktan sonra:

```bash
cd backend
go mod download
```

PostgreSQL'i (ve istege bagli Redis'i) yerelde ayaga kaldirmak icin `docker-compose.yml`
kullanilir (asagida detay var).

## 3. Adim Adim Olusturma Sirasi (referans)

Kod tabani su sirayla insa edildi (bagimliligi olan dosyalar once):

1. `go.mod`
2. `internal/config/config.go`
3. `internal/db/postgres.go` + `internal/db/migrations/0001_init.{up,down}.sql`
4. `pkg/httpresponse/response.go`, `pkg/validator/validator.go`
5. `internal/auth/middleware.go`, `internal/auth/rbac.go`
6. `internal/cache/{cache,redis,noop}.go`
7. `internal/audit/{model,service}.go`
8. `internal/realtime/{events,client,hub}.go`
9. `internal/notification/{model,repository,service,webpush}.go`
10. `internal/depot/{model,repository,service,handler}.go`
11. `internal/vehicle/*`, `internal/driver/*`
12. `internal/blacklist/*`
13. `internal/expectedarrival/*`
14. `internal/anpr/{event,correction,handler}.go`
15. `internal/vehiclelog/*` (anpr.CorrectionService'e bagimli)
16. `internal/router/router.go`
17. `cmd/api/main.go` (tum modulleri birbirine bagladigi yer)
18. `docker-compose.yml`, `Dockerfile`, `.env.example`

## 4. Veritabani / Migration

Migration dosyalari `internal/db/migrations/*.sql` altinda `embed.FS` ile binary'ye
gomulur ve **backend her baslangicta otomatik calistirir** (`db.RunMigrations` -
`cmd/api/main.go` icinde `main()`'in en basinda cagrilir). Elle `migrate` CLI komutu
calistirmaniza gerek yoktur.

Migration'i elle calistirmak/geri almak isterseniz (opsiyonel, `golang-migrate` CLI kurulu ise):

```bash
migrate -path internal/db/migrations -database "$DATABASE_URL" up
migrate -path internal/db/migrations -database "$DATABASE_URL" down 1
```

## 5. Yerel Test Adimlari

```bash
cd backend
go build ./...          # derleme kontrolu
go vet ./...             # statik analiz

cp .env.example .env     # gerekli degerleri doldurun (asagidaki not'a bakin)
docker compose up -d --build
docker compose logs -f backend   # migration + baslangic loglarini izleyin

curl http://localhost:8080/healthz
# -> {"success":true,"data":{"status":"ok"}}
```

> **Not (Keycloak):** `AUTH_JWKS_URL` ve `AUTH_ISSUER` zorunlu alanlardir (config.Load()
> bunlar bos ise hata verir). Keycloak kurulumu bu promptun kapsami disinda oldugu icin,
> gercek bir Keycloak realm'i kurana kadar bu degerleri kendi ortaminiza gore doldurmaniz
> gerekir. `/healthz` disindaki tum `/api/v1/*` endpoint'leri (ANPR webhook haric) gecerli
> bir JWT ister.

ANPR webhook'unu test etmek icin ornek istek (JWT gerektirmez, bkz. TODO notu):

```bash
curl -X POST http://localhost:8080/api/v1/anpr/events \
  -H "Content-Type: application/json" \
  -d '{
    "depot_id": "00000000-0000-0000-0000-000000000000",
    "camera_id": "cam-1",
    "plaka": "34ABC123",
    "confidence_score": 0.92,
    "image_url": "http://example.com/foo.jpg",
    "detected_at": "2026-07-13T10:00:00Z"
  }'
```

(Gercek bir depo/vehicle ile denemek icin once `POST /api/v1/depots` ile bir depo
olusturup donen `id`'yi kullanin — bu endpoint JWT ister.)

## 6. Docker Compose ile Calistirma

`docker-compose.yml` icinde `backend` + `postgres` servisleri tanimlidir (Redis, spesifikasyon
geregi opsiyonel oldugu icin yorum satiri olarak birakilmistir — acmak icin ilgili blogu
uncomment edip `.env`'de `REDIS_ENABLED=true` yapmaniz yeterli).

- **restart: unless-stopped**: makine yeniden baslarsa/servis cokerse otomatik ayaga kalkar.
- **healthcheck**: backend icin `/healthz`, postgres icin `pg_isready`.
- **volume**: `postgres_data` ile veritabani container silinse bile kalicidir.
- Postgres/Redis portlari **host'a acilmaz** (sadece backend'in kendi Docker network'unden
  erismesi yeterli); disariya sadece backend'in 8080 portu acilir.

```bash
docker compose up -d --build     # ilk kurulum / guncelleme sonrasi
docker compose logs -f backend   # loglari izle
docker compose down              # durdur (volume'lar kalir)
```

## 7. Dagitim Senaryosu — LAN Icindeki Ubuntu Makinesine SSH ile

Bu backend, internete acik bir sunucu **degil**; sadece ayni yerel agdaki (LAN) kameralar,
kiosk'lar ve saha bilgisayarlarinin erisebildigi bir Ubuntu makinesinde calisir.

### 7.1 Hedef Ubuntu makinesinde bir kerelik kurulum

```bash
ssh kullanici@<lan-ip>

sudo apt update && sudo apt upgrade -y

# Docker Engine + Compose plugin (resmi script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # yeniden giris yapin ki grup degisikligi etkin olsun

sudo apt install -y git openssh-server ufw fail2ban

# openssh-server zaten kuruluysa "already the newest version" mesaji normaldir.

# UFW: SADECE LAN subnet'inden gelen SSH ve backend (8080) trafigine izin ver.
# <lan-subnet>'i kendi agınıza gore degistirin (ornek: 192.168.1.0/24).
sudo ufw allow from <lan-subnet> to any port 22
sudo ufw allow from <lan-subnet> to any port 8080
sudo ufw enable
# 5432 (Postgres) ve 6379 (Redis) portlari HICBIR yerden acilmaz -
# docker-compose.yml zaten bu portlari host'a expose etmiyor.

# SSH: sifreli girisi kapat, sadece key ile giris
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

sudo systemctl enable fail2ban --now
```

### 7.2 Ilk dagitim

```bash
ssh kullanici@<lan-ip>
git clone <repo-url> plaka-takip
cd plaka-takip/backend

cp .env.example .env
nano .env    # DB sifresi, AUTH_JWKS_URL/AUTH_ISSUER, VAPID anahtarlari gibi degerleri doldurun
             # SERVER_HOST=0.0.0.0 kalsin (LAN icinden erisim icin), disariya kapatma ufw'nin isi

docker compose up -d --build
curl http://localhost:8080/healthz
```

Ayni LAN'daki baska bir cihazdan dogrulama:

```bash
curl http://<lan-ip>:8080/healthz
```

### 7.3 Guncelleme akisi

```bash
ssh kullanici@<lan-ip>
cd plaka-takip/backend
git pull
docker compose up -d --build
docker compose logs -f backend
```

Elle mudahale gerektirmez: migration'lar container baslarken otomatik calisir.

## 8. TODO / Sonraki Faz

- **ANPR webhook / ML feedback endpoint'i icin makine-makine kimlik dogrulamasi**:
  `POST /api/v1/anpr/events` ve `GET /api/v1/anpr/corrections` su an JWT/Keycloak akisinin
  disinda birakildi (Python servisi genelde bir tarayici kullanicisi degil). LAN-ici guvenilir
  agdan geldigi varsayilir; ileri fazda paylasimli-secret header veya mTLS eklenmelidir.
- **Gercek Kafka/RabbitMQ entegrasyonu**: su an dahili Go channel/pub-sub (realtime.Hub)
  yeterli kabul edildi; olceklendikce mesaj kuyrugu eklenebilir.
- **YOLOv8 ANPR servisi ve Python ML servisi**: bu promptun kapsami disinda, ayri repo/servis
  olarak gelistirilecek.
- **Redis'in gercek devreye alinmasi**: interface hazir (`internal/cache`), sadece
  `docker-compose.yml`'de redis servisini acip `.env`'de `REDIS_ENABLED=true` yapmak yeterli;
  hangi sorgularin cache'lenecegi henuz karara baglanmadi.
- **Log rotasyonu**: `docker compose logs -f backend` yeterli kabul edildi; dosyaya yazip
  `lumberjack` ile rotasyon istenirse eklenebilir.
- **Tailscale/WireGuard**: sadece LAN-disi uzak erisim ihtiyaci dogarsa gerekli; su an kapsam
  disinda birakildi.
- **Rate limiting / brute-force koruması (uygulama katmaninda)**: su an sadece fail2ban (SSH
  seviyesinde) var; API seviyesinde rate limiting eklenmedi.
