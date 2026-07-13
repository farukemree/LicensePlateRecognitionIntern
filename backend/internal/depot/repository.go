package depot

import (
	"context"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Repository, depot tablosuna erisimi soyutlar.
type Repository interface {
	Create(ctx context.Context, d *Depot) error
	GetByID(ctx context.Context, id uuid.UUID) (*Depot, error)
	List(ctx context.Context, ids []uuid.UUID) ([]Depot, error)
	Update(ctx context.Context, d *Depot) error
	Delete(ctx context.Context, id uuid.UUID) error
}

type pgRepository struct {
	pool *pgxpool.Pool
}

// NewRepository, verilen pool ile bir Repository olusturur.
func NewRepository(pool *pgxpool.Pool) Repository {
	return &pgRepository{pool: pool}
}

func (r *pgRepository) Create(ctx context.Context, d *Depot) error {
	return r.pool.QueryRow(ctx, `
		INSERT INTO depot (name, location) VALUES ($1, $2)
		RETURNING id, created_at
	`, d.Name, d.Location).Scan(&d.ID, &d.CreatedAt)
}

func (r *pgRepository) GetByID(ctx context.Context, id uuid.UUID) (*Depot, error) {
	var d Depot
	err := r.pool.QueryRow(ctx, `
		SELECT id, name, location, created_at FROM depot WHERE id = $1
	`, id).Scan(&d.ID, &d.Name, &d.Location, &d.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &d, nil
}

// List, ids nil ise (admin rolu) tum depolari, aksi halde sadece verilen id'lerdeki depolari dondurur.
func (r *pgRepository) List(ctx context.Context, ids []uuid.UUID) ([]Depot, error) {
	var rows pgx.Rows
	var err error
	if ids == nil {
		rows, err = r.pool.Query(ctx, `SELECT id, name, location, created_at FROM depot ORDER BY name`)
	} else {
		rows, err = r.pool.Query(ctx, `
			SELECT id, name, location, created_at FROM depot WHERE id = ANY($1) ORDER BY name
		`, ids)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []Depot
	for rows.Next() {
		var d Depot
		if err := rows.Scan(&d.ID, &d.Name, &d.Location, &d.CreatedAt); err != nil {
			return nil, err
		}
		results = append(results, d)
	}
	return results, rows.Err()
}

func (r *pgRepository) Update(ctx context.Context, d *Depot) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE depot SET name = $1, location = $2 WHERE id = $3
	`, d.Name, d.Location, d.ID)
	return err
}

func (r *pgRepository) Delete(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM depot WHERE id = $1`, id)
	return err
}
