package driver

import (
	"context"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Repository, driver tablosuna erisimi soyutlar.
type Repository interface {
	Create(ctx context.Context, d *Driver) error
	GetByID(ctx context.Context, id uuid.UUID) (*Driver, error)
	FindOrCreateByTCNo(ctx context.Context, adSoyad, tcNo, telefon string) (*Driver, error)
	List(ctx context.Context) ([]Driver, error)
}

type pgRepository struct {
	pool *pgxpool.Pool
}

// NewRepository, verilen pool ile bir Repository olusturur.
func NewRepository(pool *pgxpool.Pool) Repository {
	return &pgRepository{pool: pool}
}

func (r *pgRepository) Create(ctx context.Context, d *Driver) error {
	return r.pool.QueryRow(ctx, `
		INSERT INTO driver (ad_soyad, tc_no, telefon) VALUES ($1, $2, $3)
		RETURNING id, created_at
	`, d.AdSoyad, d.TCNo, d.Telefon).Scan(&d.ID, &d.CreatedAt)
}

func (r *pgRepository) GetByID(ctx context.Context, id uuid.UUID) (*Driver, error) {
	var d Driver
	err := r.pool.QueryRow(ctx, `
		SELECT id, ad_soyad, tc_no, telefon, created_at FROM driver WHERE id = $1
	`, id).Scan(&d.ID, &d.AdSoyad, &d.TCNo, &d.Telefon, &d.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &d, nil
}

// FindOrCreateByTCNo, tc_no bos degilse mevcut soforu bulur, yoksa yenisini olusturur.
// tc_no bossa (ANPR/hizli girisde bilinmeyebilir) her zaman yeni kayit acar.
func (r *pgRepository) FindOrCreateByTCNo(ctx context.Context, adSoyad, tcNo, telefon string) (*Driver, error) {
	if tcNo != "" {
		var d Driver
		err := r.pool.QueryRow(ctx, `
			SELECT id, ad_soyad, tc_no, telefon, created_at FROM driver WHERE tc_no = $1
		`, tcNo).Scan(&d.ID, &d.AdSoyad, &d.TCNo, &d.Telefon, &d.CreatedAt)
		if err == nil {
			return &d, nil
		}
	}
	newDriver := &Driver{AdSoyad: adSoyad, TCNo: tcNo, Telefon: telefon}
	if err := r.Create(ctx, newDriver); err != nil {
		return nil, err
	}
	return newDriver, nil
}

func (r *pgRepository) List(ctx context.Context) ([]Driver, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, ad_soyad, tc_no, telefon, created_at FROM driver ORDER BY ad_soyad
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []Driver
	for rows.Next() {
		var d Driver
		if err := rows.Scan(&d.ID, &d.AdSoyad, &d.TCNo, &d.Telefon, &d.CreatedAt); err != nil {
			return nil, err
		}
		results = append(results, d)
	}
	return results, rows.Err()
}
