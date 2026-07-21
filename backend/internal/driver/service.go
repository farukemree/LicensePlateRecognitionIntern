package driver

import (
	"context"

	"github.com/google/uuid"
)

// Service, driver ile ilgili is kurallarini icerir.
type Service struct {
	repo Repository
}

// NewService, verilen Repository ile bir Service olusturur.
func NewService(repo Repository) *Service {
	return &Service{repo: repo}
}

func (s *Service) Get(ctx context.Context, id uuid.UUID) (*Driver, error) {
	return s.repo.GetByID(ctx, id)
}

// FindOrCreate, vehiclelog akisinda sofor bilgisi geldiginde kullanilir.
func (s *Service) FindOrCreate(ctx context.Context, adSoyad, tcNo, telefon string) (*Driver, error) {
	return s.repo.FindOrCreateByTCNo(ctx, adSoyad, tcNo, telefon)
}

func (s *Service) List(ctx context.Context) ([]Driver, error) {
	return s.repo.List(ctx)
}
