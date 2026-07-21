package expectedarrival

import (
	"context"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Repository, expected_arrival tablosuna erisimi soyutlar.
type Repository interface {
	Create(ctx context.Context, e *ExpectedArrival) error
	List(ctx context.Context, depotIDs []uuid.UUID) ([]ExpectedArrival, error)
	Delete(ctx context.Context, id uuid.UUID) error
	SetDurum(ctx context.Context, id uuid.UUID, durum string) error
	// FindWaitingByPlaka, verilen depoda "bekleniyor" durumundaki en yakin eslesen kaydi bulur.
	// ANPR event'i geldiginde otomatik eslestirme icin kullanilir.
	FindWaitingByPlaka(ctx context.Context, depotID uuid.UUID, plaka string) (*ExpectedArrival, error)
}

type pgRepository struct {
	pool *pgxpool.Pool
}

// NewRepository, verilen pool ile bir Repository olusturur.
func NewRepository(pool *pgxpool.Pool) Repository {
	return &pgRepository{pool: pool}
}

func (r *pgRepository) Create(ctx context.Context, e *ExpectedArrival) error {
	return r.pool.QueryRow(ctx, `
		INSERT INTO expected_arrival (depot_id, plaka, beklenen_zaman, durum)
		VALUES ($1, $2, $3, $4)
		RETURNING id, created_at
	`, e.DepotID, e.Plaka, e.BeklenenZaman, DurumBekleniyor).Scan(&e.ID, &e.CreatedAt)
}

func (r *pgRepository) List(ctx context.Context, depotIDs []uuid.UUID) ([]ExpectedArrival, error) {
	var rows pgx.Rows
	var err error
	if depotIDs == nil {
		rows, err = r.pool.Query(ctx, `
			SELECT id, depot_id, plaka, beklenen_zaman, durum, created_at
			FROM expected_arrival ORDER BY beklenen_zaman DESC
		`)
	} else {
		rows, err = r.pool.Query(ctx, `
			SELECT id, depot_id, plaka, beklenen_zaman, durum, created_at
			FROM expected_arrival WHERE depot_id = ANY($1) ORDER BY beklenen_zaman DESC
		`, depotIDs)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []ExpectedArrival
	for rows.Next() {
		var e ExpectedArrival
		if err := rows.Scan(&e.ID, &e.DepotID, &e.Plaka, &e.BeklenenZaman, &e.Durum, &e.CreatedAt); err != nil {
			return nil, err
		}
		results = append(results, e)
	}
	return results, rows.Err()
}

func (r *pgRepository) Delete(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM expected_arrival WHERE id = $1`, id)
	return err
}

func (r *pgRepository) SetDurum(ctx context.Context, id uuid.UUID, durum string) error {
	_, err := r.pool.Exec(ctx, `UPDATE expected_arrival SET durum = $1 WHERE id = $2`, durum, id)
	return err
}

func (r *pgRepository) FindWaitingByPlaka(ctx context.Context, depotID uuid.UUID, plaka string) (*ExpectedArrival, error) {
	var e ExpectedArrival
	err := r.pool.QueryRow(ctx, `
		SELECT id, depot_id, plaka, beklenen_zaman, durum, created_at
		FROM expected_arrival
		WHERE depot_id = $1 AND plaka = $2 AND durum = $3
		ORDER BY beklenen_zaman ASC
		LIMIT 1
	`, depotID, plaka, DurumBekleniyor).Scan(&e.ID, &e.DepotID, &e.Plaka, &e.BeklenenZaman, &e.Durum, &e.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &e, nil
}
