// correction.go, guvenlik gorevlisinin ANPR tahminini duzelttigi durumlari kaydeder.
// Bu tablo Python ML servisinin okuyup modeli yeniden egitmek icin kullanacagi geri bildirim kaynagidir.
package anpr

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Correction, anpr_correction tablosundaki bir satiri temsil eder.
type Correction struct {
	ID                 uuid.UUID  `json:"id"`
	OriginalPlateGuess string     `json:"original_plate_guess"`
	CorrectedPlate     string     `json:"corrected_plate"`
	ConfidenceScore    *float64   `json:"confidence_score,omitempty"`
	ImageURL           string     `json:"image_url,omitempty"`
	VehicleLogID       *uuid.UUID `json:"vehicle_log_id,omitempty"`
	CreatedAt          time.Time  `json:"created_at"`
}

// CorrectionRepository, anpr_correction tablosuna erisimi soyutlar.
type CorrectionRepository interface {
	Create(ctx context.Context, c *Correction) error
	List(ctx context.Context, limit int) ([]Correction, error)
}

type pgCorrectionRepository struct {
	pool *pgxpool.Pool
}

// NewCorrectionRepository, verilen pool ile bir CorrectionRepository olusturur.
func NewCorrectionRepository(pool *pgxpool.Pool) CorrectionRepository {
	return &pgCorrectionRepository{pool: pool}
}

func (r *pgCorrectionRepository) Create(ctx context.Context, c *Correction) error {
	return r.pool.QueryRow(ctx, `
		INSERT INTO anpr_correction (original_plate_guess, corrected_plate, confidence_score, image_url, vehicle_log_id)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, created_at
	`, c.OriginalPlateGuess, c.CorrectedPlate, c.ConfidenceScore, c.ImageURL, c.VehicleLogID).Scan(&c.ID, &c.CreatedAt)
}

func (r *pgCorrectionRepository) List(ctx context.Context, limit int) ([]Correction, error) {
	if limit <= 0 {
		limit = 100
	}
	rows, err := r.pool.Query(ctx, `
		SELECT id, original_plate_guess, corrected_plate, confidence_score, image_url, vehicle_log_id, created_at
		FROM anpr_correction ORDER BY created_at DESC LIMIT $1
	`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []Correction
	for rows.Next() {
		var c Correction
		if err := rows.Scan(&c.ID, &c.OriginalPlateGuess, &c.CorrectedPlate, &c.ConfidenceScore, &c.ImageURL, &c.VehicleLogID, &c.CreatedAt); err != nil {
			return nil, err
		}
		results = append(results, c)
	}
	return results, rows.Err()
}

// CorrectionService, duzeltme kayitlarini olusturma/okuma is mantigidir.
type CorrectionService struct {
	repo CorrectionRepository
}

// NewCorrectionService, verilen CorrectionRepository ile bir CorrectionService olusturur.
func NewCorrectionService(repo CorrectionRepository) *CorrectionService {
	return &CorrectionService{repo: repo}
}

// RecordCorrection, ANPR tahmini ile gorevlinin girdigi nihai plaka farkliysa cagrilir.
// vehiclelog.Service, POST /api/v1/vehicle-logs isleminde bunu tetikler (gereksinim 4).
func (s *CorrectionService) RecordCorrection(ctx context.Context, originalGuess, correctedPlate string, confidence *float64, imageURL string, vehicleLogID uuid.UUID) error {
	c := &Correction{
		OriginalPlateGuess: originalGuess,
		CorrectedPlate:     correctedPlate,
		ConfidenceScore:    confidence,
		ImageURL:           imageURL,
		VehicleLogID:       &vehicleLogID,
	}
	return s.repo.Create(ctx, c)
}

// ListCorrections, Python ML servisinin okuyabilecegi duzeltme gecmisini dondurur.
func (s *CorrectionService) ListCorrections(ctx context.Context, limit int) ([]Correction, error) {
	return s.repo.List(ctx, limit)
}
