// Package db, PostgreSQL baglanti havuzunu ve migration calistirmayi yonetir.
package db

import (
	"context"
	"embed"
	"fmt"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	"github.com/golang-migrate/migrate/v4/source/iofs"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/example/plaka-takip-backend/internal/config"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

// NewPool, verilen config'e gore bir PostgreSQL baglanti havuzu olusturur.
func NewPool(ctx context.Context, cfg config.DatabaseConfig) (*pgxpool.Pool, error) {
	pool, err := pgxpool.New(ctx, cfg.DSN())
	if err != nil {
		return nil, fmt.Errorf("pg havuzu olusturulamadi: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("veritabanina baglanilamadi: %w", err)
	}
	return pool, nil
}

// RunMigrations, embed edilmis SQL migration dosyalarini calistirir.
// Backend her baslangicta bunu cagirir; elle "migrate" CLI komutu calistirmaya gerek kalmaz.
func RunMigrations(cfg config.DatabaseConfig) error {
	src, err := iofs.New(migrationsFS, "migrations")
	if err != nil {
		return fmt.Errorf("migration kaynagi okunamadi: %w", err)
	}

	m, err := migrate.NewWithSourceInstance("iofs", src, cfg.DSN())
	if err != nil {
		return fmt.Errorf("migrate olusturulamadi: %w", err)
	}

	if err := m.Up(); err != nil && err != migrate.ErrNoChange {
		return fmt.Errorf("migration calistirilamadi: %w", err)
	}
	return nil
}
