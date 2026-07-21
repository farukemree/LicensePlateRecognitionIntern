-- Plaka Takip Sistemi - ilk semadir. Tum tablolar, foreign key'ler ve indexler burada.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- depot: her tesis/depo lokasyonu
CREATE TABLE depot (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    location    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- vehicle: sisteme kayitli araclar
CREATE TABLE vehicle (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plaka           TEXT NOT NULL UNIQUE,
    arac_turu       TEXT,
    muayene_tarihi  DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vehicle_plaka ON vehicle (plaka);

-- driver: soforler
CREATE TABLE driver (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_soyad    TEXT NOT NULL,
    tc_no       TEXT,
    telefon     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- "user": Keycloak ile eslesen sistem kullanicilari (rol tabanli)
CREATE TABLE "user" (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_soyad        TEXT NOT NULL,
    rol             TEXT NOT NULL CHECK (rol IN ('admin', 'depo_yoneticisi', 'guvenlik_gorevlisi', 'operasyon')),
    keycloak_sub    TEXT NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- user_depot_access: kullanicinin gorebildigi depolar (coka-cok)
CREATE TABLE user_depot_access (
    user_id     UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    depot_id    UUID NOT NULL REFERENCES depot(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, depot_id)
);
CREATE INDEX idx_user_depot_access_depot ON user_depot_access (depot_id);

-- vehicle_log: depoya giris/cikis kayitlari
CREATE TABLE vehicle_log (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    depot_id                UUID NOT NULL REFERENCES depot(id),
    vehicle_id              UUID NOT NULL REFERENCES vehicle(id),
    driver_id               UUID REFERENCES driver(id),
    user_id                 UUID REFERENCES "user"(id),
    yon                     TEXT NOT NULL CHECK (yon IN ('giris', 'cikis')),
    irsaliye_no             TEXT,
    romork_no               TEXT,
    muhur_no                TEXT,
    konteyner_no            TEXT,
    tasimacilik_sirketi     TEXT,
    emniyet_kemeri          BOOLEAN NOT NULL DEFAULT false,
    asma_kilit              BOOLEAN NOT NULL DEFAULT false,
    tarih                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    aciklama                TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vehicle_log_depot_id ON vehicle_log (depot_id);
CREATE INDEX idx_vehicle_log_tarih ON vehicle_log (tarih);
CREATE INDEX idx_vehicle_log_vehicle_id ON vehicle_log (vehicle_id);

-- blacklist: kara listeye alinan arac/sofor kayitlari
CREATE TABLE blacklist (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tip                 TEXT NOT NULL CHECK (tip IN ('vehicle', 'driver')),
    ref_id              UUID NOT NULL,
    sebep               TEXT NOT NULL,
    eklenen_yetkili_id  UUID REFERENCES "user"(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    aktif               BOOLEAN NOT NULL DEFAULT true
);
CREATE INDEX idx_blacklist_ref_id ON blacklist (ref_id);
CREATE INDEX idx_blacklist_aktif ON blacklist (aktif);

-- expected_arrival: beklenen arac girisleri
CREATE TABLE expected_arrival (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    depot_id        UUID NOT NULL REFERENCES depot(id),
    plaka           TEXT NOT NULL,
    beklenen_zaman  TIMESTAMPTZ NOT NULL,
    durum           TEXT NOT NULL DEFAULT 'bekleniyor' CHECK (durum IN ('bekleniyor', 'geldi', 'zaman_asimi')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_expected_arrival_depot_id ON expected_arrival (depot_id);
CREATE INDEX idx_expected_arrival_plaka ON expected_arrival (plaka);

-- anpr_correction: ANPR tahmini ile gorevli duzeltmesi farkli oldugunda olusan kayit (ML feedback icin)
CREATE TABLE anpr_correction (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_plate_guess    TEXT NOT NULL,
    corrected_plate         TEXT NOT NULL,
    confidence_score        DOUBLE PRECISION,
    image_url               TEXT,
    vehicle_log_id          UUID REFERENCES vehicle_log(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_anpr_correction_vehicle_log_id ON anpr_correction (vehicle_log_id);

-- audit_log: kritik aksiyonlarin izlenebilirligi
CREATE TABLE audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES "user"(id),
    action      TEXT NOT NULL,
    entity      TEXT NOT NULL,
    entity_id   UUID,
    detay       JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_log_entity ON audit_log (entity, entity_id);

-- notification: uygulama ici bildirim gecmisi (WebPush + WebSocket beraberinde yazilir)
CREATE TABLE notification (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES "user"(id),
    depot_id    UUID REFERENCES depot(id),
    tip         TEXT NOT NULL,
    baslik      TEXT NOT NULL,
    mesaj       TEXT,
    okundu      BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notification_user_id ON notification (user_id);

-- webpush_subscription: kullanicinin tarayici Web Push abonelik bilgileri
CREATE TABLE webpush_subscription (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    endpoint    TEXT NOT NULL,
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, endpoint)
);
