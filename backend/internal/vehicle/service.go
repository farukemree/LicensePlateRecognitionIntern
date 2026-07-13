package vehicle

import (
	"context"

	"github.com/google/uuid"
)

// Service, vehicle ile ilgili is kurallarini icerir.
type Service struct {
	repo Repository
}

// NewService, verilen Repository ile bir Service olusturur.
func NewService(repo Repository) *Service {
	return &Service{repo: repo}
}

func (s *Service) Create(ctx context.Context, req CreateRequest) (*Vehicle, error) {
	v := &Vehicle{Plaka: req.Plaka, AracTuru: req.AracTuru, MuayeneTarihi: req.MuayeneTarihi}
	if err := s.repo.Create(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) Get(ctx context.Context, id uuid.UUID) (*Vehicle, error) {
	return s.repo.GetByID(ctx, id)
}

func (s *Service) GetByPlaka(ctx context.Context, plaka string) (*Vehicle, error) {
	return s.repo.GetByPlaka(ctx, plaka)
}

// FindOrCreateByPlaka, ANPR/vehiclelog akislari icin plaka yoksa otomatik olusturur.
func (s *Service) FindOrCreateByPlaka(ctx context.Context, plaka string) (*Vehicle, error) {
	return s.repo.FindOrCreateByPlaka(ctx, plaka)
}

func (s *Service) List(ctx context.Context) ([]Vehicle, error) {
	return s.repo.List(ctx)
}

func (s *Service) Update(ctx context.Context, id uuid.UUID, req UpdateRequest) (*Vehicle, error) {
	v := &Vehicle{ID: id, AracTuru: req.AracTuru, MuayeneTarihi: req.MuayeneTarihi}
	if err := s.repo.Update(ctx, v); err != nil {
		return nil, err
	}
	return s.repo.GetByID(ctx, id)
}

func (s *Service) Delete(ctx context.Context, id uuid.UUID) error {
	return s.repo.Delete(ctx, id)
}
