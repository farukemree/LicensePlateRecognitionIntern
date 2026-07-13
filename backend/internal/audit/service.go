package audit

import (
	"context"
	"encoding/json"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Service, audit_log tablosuna kayit dusen tek noktadir. Diger modul servisleri
// (blacklist, vehiclelog, vb.) kritik aksiyonlarda bu servisi cagirir.
type Service struct {
	pool *pgxpool.Pool
}

// NewService, verilen pool ile bir audit Service olusturur.
func NewService(pool *pgxpool.Pool) *Service {
	return &Service{pool: pool}
}

// Log, action/entity bilgisiyle birlikte serbest formatli detay verisini audit_log'a yazar.
func (s *Service) Log(ctx context.Context, userID *uuid.UUID, action, entity string, entityID *uuid.UUID, detay map[string]interface{}) error {
	var detayArg interface{}
	if detay != nil {
		b, err := json.Marshal(detay)
		if err != nil {
			return err
		}
		detayArg = b
	}

	_, err := s.pool.Exec(ctx, `
		INSERT INTO audit_log (user_id, action, entity, entity_id, detay)
		VALUES ($1, $2, $3, $4, $5)
	`, userID, action, entity, entityID, detayArg)
	return err
}
