package blacklist

import (
	"context"
	"errors"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/example/plaka-takip-backend/internal/audit"
)

// Service, kara liste is kurallarini icerir. Her yazma islemi (ekleme/kaldirma)
// audit_log'a dusurulur - gereksinim 5.
type Service struct {
	repo  Repository
	audit *audit.Service
}

// NewService, verilen Repository ve audit.Service ile bir Service olusturur.
func NewService(repo Repository, auditSvc *audit.Service) *Service {
	return &Service{repo: repo, audit: auditSvc}
}

// Add, kara listeye yeni bir kayit ekler ve audit_log'a "blacklist.add" olarak yazar.
func (s *Service) Add(ctx context.Context, addedByUserID uuid.UUID, req CreateRequest) (*Blacklist, error) {
	b := &Blacklist{Tip: req.Tip, RefID: req.RefID, Sebep: req.Sebep, EklenenYetkiliID: &addedByUserID}
	if err := s.repo.Create(ctx, b); err != nil {
		return nil, err
	}
	_ = s.audit.Log(ctx, &addedByUserID, "blacklist.add", "blacklist", &b.ID, map[string]interface{}{
		"tip": b.Tip, "ref_id": b.RefID.String(), "sebep": b.Sebep,
	})
	return b, nil
}

// List, tum kara liste kayitlarini dondurur.
func (s *Service) List(ctx context.Context) ([]Blacklist, error) {
	return s.repo.List(ctx)
}

// Remove, bir kara liste kaydini pasif hale getirir ve audit_log'a "blacklist.remove" olarak yazar.
func (s *Service) Remove(ctx context.Context, removedByUserID, id uuid.UUID) error {
	if err := s.repo.Deactivate(ctx, id); err != nil {
		return err
	}
	return s.audit.Log(ctx, &removedByUserID, "blacklist.remove", "blacklist", &id, nil)
}

// Check, verilen tip+ref_id icin aktif bir kara liste kaydi olup olmadigini soyler.
// ANPR webhook'u ve manuel vehicle-log kaydi bu metodu cagirarak kritik uyariyi tetikler.
func (s *Service) Check(ctx context.Context, tip string, refID uuid.UUID) (*Blacklist, bool, error) {
	b, err := s.repo.FindActive(ctx, tip, refID)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	return b, true, nil
}
