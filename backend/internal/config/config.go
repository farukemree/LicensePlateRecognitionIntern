// Package config, uygulamanin tum ortam degiskenlerini tek bir yapida toplar.
package config

import (
	"fmt"

	"github.com/kelseyhightower/envconfig"
)

// Config, .env / ortam degiskenlerinden okunan tum ayarlari tutar.
type Config struct {
	Server   ServerConfig
	Database DatabaseConfig
	Redis    RedisConfig
	Auth     AuthConfig
	WebPush  WebPushConfig
}

// ServerConfig, HTTP sunucusunun dinleyecegi adres/port bilgisidir.
// LAN dagitim senaryosunda Host=0.0.0.0 olarak birakilip, disariya kapanma
// islemi ufw (isletim sistemi guvenlik duvari) ile yapilir.
type ServerConfig struct {
	Host string `envconfig:"SERVER_HOST" default:"0.0.0.0"`
	Port int    `envconfig:"SERVER_PORT" default:"8080"`
}

// DatabaseConfig, PostgreSQL baglanti bilgilerini tutar.
type DatabaseConfig struct {
	Host     string `envconfig:"DB_HOST" default:"localhost"`
	Port     int    `envconfig:"DB_PORT" default:"5432"`
	User     string `envconfig:"DB_USER" default:"plaka"`
	Password string `envconfig:"DB_PASSWORD" default:"plaka"`
	Name     string `envconfig:"DB_NAME" default:"plaka_takip"`
	SSLMode  string `envconfig:"DB_SSLMODE" default:"disable"`
}

// DSN, pgx/postgres baglanti dizesini olusturur.
func (d DatabaseConfig) DSN() string {
	return fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=%s",
		d.User, d.Password, d.Host, d.Port, d.Name, d.SSLMode)
}

// RedisConfig, opsiyonel cache katmani icin ayarlardir.
// Enabled=false ise cache.NoopCache devreye girer, Redis olmadan sistem calisir.
type RedisConfig struct {
	Enabled  bool   `envconfig:"REDIS_ENABLED" default:"false"`
	Addr     string `envconfig:"REDIS_ADDR" default:"localhost:6379"`
	Password string `envconfig:"REDIS_PASSWORD" default:""`
	DB       int    `envconfig:"REDIS_DB" default:"0"`
}

// AuthConfig, Keycloak (OIDC) JWT dogrulamasi icin gerekli bilgiler.
type AuthConfig struct {
	JWKSURL  string `envconfig:"AUTH_JWKS_URL" required:"true"`
	Issuer   string `envconfig:"AUTH_ISSUER" required:"true"`
	Audience string `envconfig:"AUTH_AUDIENCE" default:""`
}

// WebPushConfig, Web Push (VAPID) bildirimleri icin anahtarlardir.
type WebPushConfig struct {
	VAPIDPublicKey  string `envconfig:"VAPID_PUBLIC_KEY" default:""`
	VAPIDPrivateKey string `envconfig:"VAPID_PRIVATE_KEY" default:""`
	VAPIDSubject    string `envconfig:"VAPID_SUBJECT" default:"mailto:admin@example.com"`
}

// Load, ortam degiskenlerinden Config yapisini doldurur.
func Load() (*Config, error) {
	var cfg Config
	if err := envconfig.Process("", &cfg); err != nil {
		return nil, fmt.Errorf("config yuklenemedi: %w", err)
	}
	return &cfg, nil
}
