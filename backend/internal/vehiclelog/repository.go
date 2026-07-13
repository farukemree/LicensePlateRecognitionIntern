package vehiclelog

import (
	"context"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Repository, vehicle_log tablosuna erisimi soyutlar.
type Repository interface {
	Create(ctx context.Context, v *VehicleLog) error
	List(ctx context.Context, depotIDs []uuid.UUID) ([]VehicleLog, error)
	GetByID(ctx context.Context, id uuid.UUID) (*VehicleLog, error)
}

type pgRepository struct {
	pool *pgxpool.Pool
}

// NewRepository, verilen pool ile bir Repository olusturur.
func NewRepository(pool *pgxpool.Pool) Repository {
	return &pgRepository{pool: pool}
}

func (r *pgRepository) Create(ctx context.Context, v *VehicleLog) error {
	return r.pool.QueryRow(ctx, `
		INSERT INTO vehicle_log (
			depot_id, vehicle_id, driver_id, user_id, yon, irsaliye_no, romork_no,
			muhur_no, konteyner_no, tasimacilik_sirketi, emniyet_kemeri, asma_kilit, tarih, aciklama
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
		RETURNING id, created_at
	`, v.DepotID, v.VehicleID, v.DriverID, v.UserID, v.Yon, v.IrsaliyeNo, v.RomorkNo,
		v.MuhurNo, v.KonteynerNo, v.TasimacilikSirketi, v.EmniyetKemeri, v.AsmaKilit, v.Tarih, v.Aciklama,
	).Scan(&v.ID, &v.CreatedAt)
}

func (r *pgRepository) List(ctx context.Context, depotIDs []uuid.UUID) ([]VehicleLog, error) {
	var rows pgx.Rows
	var err error
	const cols = `id, depot_id, vehicle_id, driver_id, user_id, yon, irsaliye_no, romork_no,
			muhur_no, konteyner_no, tasimacilik_sirketi, emniyet_kemeri, asma_kilit, tarih, aciklama, created_at`
	if depotIDs == nil {
		rows, err = r.pool.Query(ctx, `SELECT `+cols+` FROM vehicle_log ORDER BY tarih DESC LIMIT 500`)
	} else {
		rows, err = r.pool.Query(ctx, `SELECT `+cols+` FROM vehicle_log WHERE depot_id = ANY($1) ORDER BY tarih DESC LIMIT 500`, depotIDs)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []VehicleLog
	for rows.Next() {
		var v VehicleLog
		if err := rows.Scan(&v.ID, &v.DepotID, &v.VehicleID, &v.DriverID, &v.UserID, &v.Yon, &v.IrsaliyeNo,
			&v.RomorkNo, &v.MuhurNo, &v.KonteynerNo, &v.TasimacilikSirketi, &v.EmniyetKemeri, &v.AsmaKilit,
			&v.Tarih, &v.Aciklama, &v.CreatedAt); err != nil {
			return nil, err
		}
		results = append(results, v)
	}
	return results, rows.Err()
}

func (r *pgRepository) GetByID(ctx context.Context, id uuid.UUID) (*VehicleLog, error) {
	var v VehicleLog
	err := r.pool.QueryRow(ctx, `
		SELECT id, depot_id, vehicle_id, driver_id, user_id, yon, irsaliye_no, romork_no,
			muhur_no, konteyner_no, tasimacilik_sirketi, emniyet_kemeri, asma_kilit, tarih, aciklama, created_at
		FROM vehicle_log WHERE id = $1
	`, id).Scan(&v.ID, &v.DepotID, &v.VehicleID, &v.DriverID, &v.UserID, &v.Yon, &v.IrsaliyeNo,
		&v.RomorkNo, &v.MuhurNo, &v.KonteynerNo, &v.TasimacilikSirketi, &v.EmniyetKemeri, &v.AsmaKilit,
		&v.Tarih, &v.Aciklama, &v.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &v, nil
}
