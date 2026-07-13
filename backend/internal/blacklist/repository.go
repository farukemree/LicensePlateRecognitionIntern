package blacklist

import (
	"context"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Repository, blacklist tablosuna erisimi soyutlar.
type Repository interface {
	Create(ctx context.Context, b *Blacklist) error
	List(ctx context.Context) ([]Blacklist, error)
	Deactivate(ctx context.Context, id uuid.UUID) error
	FindActive(ctx context.Context, tip string, refID uuid.UUID) (*Blacklist, error)
}

type pgRepository struct {
	pool *pgxpool.Pool
}

// NewRepository, verilen pool ile bir Repository olusturur.
func NewRepository(pool *pgxpool.Pool) Repository {
	return &pgRepository{pool: pool}
}

func (r *pgRepository) Create(ctx context.Context, b *Blacklist) error {
	return r.pool.QueryRow(ctx, `
		INSERT INTO blacklist (tip, ref_id, sebep, eklenen_yetkili_id)
		VALUES ($1, $2, $3, $4)
		RETURNING id, created_at, aktif
	`, b.Tip, b.RefID, b.Sebep, b.EklenenYetkiliID).Scan(&b.ID, &b.CreatedAt, &b.Aktif)
}

func (r *pgRepository) List(ctx context.Context) ([]Blacklist, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, tip, ref_id, sebep, eklenen_yetkili_id, created_at, aktif
		FROM blacklist ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []Blacklist
	for rows.Next() {
		var b Blacklist
		if err := rows.Scan(&b.ID, &b.Tip, &b.RefID, &b.Sebep, &b.EklenenYetkiliID, &b.CreatedAt, &b.Aktif); err != nil {
			return nil, err
		}
		results = append(results, b)
	}
	return results, rows.Err()
}

func (r *pgRepository) Deactivate(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `UPDATE blacklist SET aktif = false WHERE id = $1`, id)
	return err
}

// FindActive, verilen tip+ref_id icin aktif bir kara liste kaydi olup olmadigini kontrol eder.
// ANPR ve vehiclelog akislari bunu her tespit/kayitta cagirir.
func (r *pgRepository) FindActive(ctx context.Context, tip string, refID uuid.UUID) (*Blacklist, error) {
	var b Blacklist
	err := r.pool.QueryRow(ctx, `
		SELECT id, tip, ref_id, sebep, eklenen_yetkili_id, created_at, aktif
		FROM blacklist WHERE tip = $1 AND ref_id = $2 AND aktif = true
		LIMIT 1
	`, tip, refID).Scan(&b.ID, &b.Tip, &b.RefID, &b.Sebep, &b.EklenenYetkiliID, &b.CreatedAt, &b.Aktif)
	if err != nil {
		return nil, err
	}
	return &b, nil
}
