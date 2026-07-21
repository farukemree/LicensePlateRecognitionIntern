package depot

import (
	"context"

	"github.com/google/uuid"
)

// Service, depot ile ilgili is kurallarini icerir (bu modulde su an sadece repository'e delege eder).
type Service struct {
	repo Repository
}

// NewService, verilen Repository ile bir Service olusturur.
func NewService(repo Repository) *Service {
	return &Service{repo: repo}
}

func (s *Service) Create(ctx context.Context, req CreateRequest) (*Depot, error) {
	d := &Depot{Name: req.Name, Location: req.Location}
	if err := s.repo.Create(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

func (s *Service) Get(ctx context.Context, id uuid.UUID) (*Depot, error) {
	return s.repo.GetByID(ctx, id)
}

// List, kullanicinin erisebildigi depot id listesine gore filtrelenmis depolari dondurur.
// accessibleIDs nil ise (admin) tum depolar dondurulur.
func (s *Service) List(ctx context.Context, accessibleIDs []uuid.UUID) ([]Depot, error) {
	return s.repo.List(ctx, accessibleIDs)
}

func (s *Service) Update(ctx context.Context, id uuid.UUID, req UpdateRequest) (*Depot, error) {
	d := &Depot{ID: id, Name: req.Name, Location: req.Location}
	if err := s.repo.Update(ctx, d); err != nil {
		return nil, err
	}
	return s.repo.GetByID(ctx, id)
}

func (s *Service) Delete(ctx context.Context, id uuid.UUID) error {
	return s.repo.Delete(ctx, id)
}
