package vehicle

import (
	"context"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Repository, vehicle tablosuna erisimi soyutlar.
type Repository interface {
	Create(ctx context.Context, v *Vehicle) error
	GetByID(ctx context.Context, id uuid.UUID) (*Vehicle, error)
	GetByPlaka(ctx context.Context, plaka string) (*Vehicle, error)
	FindOrCreateByPlaka(ctx context.Context, plaka string) (*Vehicle, error)
	List(ctx context.Context) ([]Vehicle, error)
	Update(ctx context.Context, v *Vehicle) error
	Delete(ctx context.Context, id uuid.UUID) error
}

type pgRepository struct {
	pool *pgxpool.Pool
}

// NewRepository, verilen pool ile bir Repository olusturur.
func NewRepository(pool *pgxpool.Pool) Repository {
	return &pgRepository{pool: pool}
}

func (r *pgRepository) Create(ctx context.Context, v *Vehicle) error {
	return r.pool.QueryRow(ctx, `
		INSERT INTO vehicle (plaka, arac_turu, muayene_tarihi) VALUES ($1, $2, $3)
		RETURNING id, created_at
	`, v.Plaka, v.AracTuru, v.MuayeneTarihi).Scan(&v.ID, &v.CreatedAt)
}

func (r *pgRepository) GetByID(ctx context.Context, id uuid.UUID) (*Vehicle, error) {
	var v Vehicle
	err := r.pool.QueryRow(ctx, `
		SELECT id, plaka, arac_turu, muayene_tarihi, created_at FROM vehicle WHERE id = $1
	`, id).Scan(&v.ID, &v.Plaka, &v.AracTuru, &v.MuayeneTarihi, &v.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *pgRepository) GetByPlaka(ctx context.Context, plaka string) (*Vehicle, error) {
	var v Vehicle
	err := r.pool.QueryRow(ctx, `
		SELECT id, plaka, arac_turu, muayene_tarihi, created_at FROM vehicle WHERE plaka = $1
	`, plaka).Scan(&v.ID, &v.Plaka, &v.AracTuru, &v.MuayeneTarihi, &v.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &v, nil
}

// FindOrCreateByPlaka, ANPR/vehicle-log akislarinda plaka sistemde yoksa otomatik olusturur.
func (r *pgRepository) FindOrCreateByPlaka(ctx context.Context, plaka string) (*Vehicle, error) {
	v, err := r.GetByPlaka(ctx, plaka)
	if err == nil {
		return v, nil
	}
	newVehicle := &Vehicle{Plaka: plaka}
	if err := r.Create(ctx, newVehicle); err != nil {
		return nil, err
	}
	return newVehicle, nil
}

func (r *pgRepository) List(ctx context.Context) ([]Vehicle, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, plaka, arac_turu, muayene_tarihi, created_at FROM vehicle ORDER BY plaka
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []Vehicle
	for rows.Next() {
		var v Vehicle
		if err := rows.Scan(&v.ID, &v.Plaka, &v.AracTuru, &v.MuayeneTarihi, &v.CreatedAt); err != nil {
			return nil, err
		}
		results = append(results, v)
	}
	return results, rows.Err()
}

func (r *pgRepository) Update(ctx context.Context, v *Vehicle) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE vehicle SET arac_turu = $1, muayene_tarihi = $2 WHERE id = $3
	`, v.AracTuru, v.MuayeneTarihi, v.ID)
	return err
}

func (r *pgRepository) Delete(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM vehicle WHERE id = $1`, id)
	return err
}
