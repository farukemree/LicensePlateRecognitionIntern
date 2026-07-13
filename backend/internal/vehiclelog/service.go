package vehiclelog

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/example/plaka-takip-backend/internal/anpr"
	"github.com/example/plaka-takip-backend/internal/blacklist"
	"github.com/example/plaka-takip-backend/internal/driver"
	"github.com/example/plaka-takip-backend/internal/expectedarrival"
	"github.com/example/plaka-takip-backend/internal/notification"
	"github.com/example/plaka-takip-backend/internal/realtime"
	"github.com/example/plaka-takip-backend/internal/vehicle"
)

// Service, guvenlik gorevlisinin onayladigi giris/cikis kaydini isler (gereksinim 4):
//   - Plaka/sofor sisteme yoksa otomatik olusturur
//   - Kara liste kontrolu yapar, tespit varsa KRITIK WebSocket/Web Push uyarisi tetikler (gereksinim 6)
//   - ANPR tahmininden farkli bir plaka girildiyse anpr_correction kaydi dusurur
//   - Beklenen arac girisiyle otomatik eslestirmeyi dener (gereksinim 7)
type Service struct {
	repo                   Repository
	vehicleService         *vehicle.Service
	driverService          *driver.Service
	blacklistService       *blacklist.Service
	correctionService      *anpr.CorrectionService
	expectedArrivalService *expectedarrival.Service
	hub                    *realtime.Hub
	notificationService    notification.Service
}

// NewService, vehiclelog akisinin ihtiyac duydugu tum bagimliliklarla bir Service olusturur.
func NewService(
	repo Repository,
	vehicleService *vehicle.Service,
	driverService *driver.Service,
	blacklistService *blacklist.Service,
	correctionService *anpr.CorrectionService,
	expectedArrivalService *expectedarrival.Service,
	hub *realtime.Hub,
	notificationService notification.Service,
) *Service {
	return &Service{
		repo:                   repo,
		vehicleService:         vehicleService,
		driverService:          driverService,
		blacklistService:       blacklistService,
		correctionService:      correctionService,
		expectedArrivalService: expectedArrivalService,
		hub:                    hub,
		notificationService:    notificationService,
	}
}

// Create, formu onaylayan guvenlik gorevlisinden gelen kaydi isler.
func (s *Service) Create(ctx context.Context, userID uuid.UUID, req CreateRequest) (*VehicleLog, error) {
	v, err := s.vehicleService.FindOrCreateByPlaka(ctx, req.Plaka)
	if err != nil {
		return nil, err
	}

	var driverID *uuid.UUID
	if req.Sofor != nil && req.Sofor.AdSoyad != "" {
		d, err := s.driverService.FindOrCreate(ctx, req.Sofor.AdSoyad, req.Sofor.TCNo, req.Sofor.Telefon)
		if err != nil {
			return nil, err
		}
		driverID = &d.ID
	}

	tarih := time.Now()
	if req.Tarih != nil {
		tarih = *req.Tarih
	}

	log := &VehicleLog{
		DepotID:            req.DepotID,
		VehicleID:          v.ID,
		DriverID:           driverID,
		UserID:             &userID,
		Yon:                req.Yon,
		IrsaliyeNo:         req.IrsaliyeNo,
		RomorkNo:           req.RomorkNo,
		MuhurNo:            req.MuhurNo,
		KonteynerNo:        req.KonteynerNo,
		TasimacilikSirketi: req.TasimacilikSirketi,
		EmniyetKemeri:      req.EmniyetKemeri,
		AsmaKilit:          req.AsmaKilit,
		Tarih:              tarih,
		Aciklama:           req.Aciklama,
	}
	if err := s.repo.Create(ctx, log); err != nil {
		return nil, err
	}

	// ANPR tahmini ile nihai plaka farkliysa duzeltme kaydi dus (gereksinim 4).
	if req.ANPR != nil && req.ANPR.PlakaTahmini != "" && req.ANPR.PlakaTahmini != req.Plaka {
		if err := s.correctionService.RecordCorrection(
			ctx, req.ANPR.PlakaTahmini, req.Plaka, req.ANPR.ConfidenceScore, req.ANPR.ImageURL, log.ID,
		); err != nil {
			return nil, err
		}
	}

	// Beklenen arac girisiyle otomatik eslestirme (gereksinim 7) - ANPR akisi disinda manuel girildiyse de calisir.
	if _, _, err := s.expectedArrivalService.TryMatchArrival(ctx, req.DepotID, req.Plaka); err != nil {
		return nil, err
	}

	// Kara liste kontrolu (gereksinim 6): arac ve varsa sofor icin.
	if err := s.checkAndAlertBlacklist(ctx, req.DepotID, blacklist.TipVehicle, v.ID, req.Plaka); err != nil {
		return nil, err
	}
	if driverID != nil {
		if err := s.checkAndAlertBlacklist(ctx, req.DepotID, blacklist.TipDriver, *driverID, req.Plaka); err != nil {
			return nil, err
		}
	}

	return log, nil
}

func (s *Service) checkAndAlertBlacklist(ctx context.Context, depotID uuid.UUID, tip string, refID uuid.UUID, plaka string) error {
	bl, found, err := s.blacklistService.Check(ctx, tip, refID)
	if err != nil {
		return err
	}
	if !found {
		return nil
	}

	s.hub.Broadcast(realtime.Event{
		Type:    realtime.EventVehicleBlacklistAlert,
		DepotID: depotID,
		Payload: realtime.BlacklistAlertPayload{
			Tip:     tip,
			RefID:   refID,
			Plaka:   plaka,
			Sebep:   bl.Sebep,
			DepotID: depotID,
		},
	})
	return s.notificationService.NotifyDepot(ctx, depotID, "blacklist_alert",
		"Kara listedeki kayit tespit edildi: "+plaka, bl.Sebep)
}

func (s *Service) List(ctx context.Context, depotIDs []uuid.UUID) ([]VehicleLog, error) {
	return s.repo.List(ctx, depotIDs)
}

func (s *Service) Get(ctx context.Context, id uuid.UUID) (*VehicleLog, error) {
	return s.repo.GetByID(ctx, id)
}
