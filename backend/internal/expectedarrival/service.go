package expectedarrival

import (
	"context"
	"errors"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

// Service, beklenen arac girisleri ile ilgili is kurallarini icerir.
type Service struct {
	repo Repository
}

// NewService, verilen Repository ile bir Service olusturur.
func NewService(repo Repository) *Service {
	return &Service{repo: repo}
}

func (s *Service) Create(ctx context.Context, req CreateRequest) (*ExpectedArrival, error) {
	e := &ExpectedArrival{DepotID: req.DepotID, Plaka: req.Plaka, BeklenenZaman: req.BeklenenZaman}
	if err := s.repo.Create(ctx, e); err != nil {
		return nil, err
	}
	return e, nil
}

func (s *Service) List(ctx context.Context, depotIDs []uuid.UUID) ([]ExpectedArrival, error) {
	return s.repo.List(ctx, depotIDs)
}

func (s *Service) Delete(ctx context.Context, id uuid.UUID) error {
	return s.repo.Delete(ctx, id)
}

// TryMatchArrival, ANPR event'i geldiginde cagirilir: verilen depo+plaka icin
// "bekleniyor" durumundaki bir kayit varsa "geldi" olarak isaretler.
// Eslesme bulunamamasi hata degildir; (nil, false, nil) doner.
func (s *Service) TryMatchArrival(ctx context.Context, depotID uuid.UUID, plaka string) (*ExpectedArrival, bool, error) {
	e, err := s.repo.FindWaitingByPlaka(ctx, depotID, plaka)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	if err := s.repo.SetDurum(ctx, e.ID, DurumGeldi); err != nil {
		return nil, false, err
	}
	e.Durum = DurumGeldi
	return e, true, nil
}
