// handler.go, ANPR (Python/YOLOv8) mikroservisinden gelen HTTP webhook'u karsilar.
package anpr

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/example/plaka-takip-backend/internal/blacklist"
	"github.com/example/plaka-takip-backend/internal/expectedarrival"
	"github.com/example/plaka-takip-backend/internal/notification"
	"github.com/example/plaka-takip-backend/internal/realtime"
	"github.com/example/plaka-takip-backend/internal/vehicle"
	"github.com/example/plaka-takip-backend/pkg/httpresponse"
	"github.com/example/plaka-takip-backend/pkg/validator"
)

// Handler, ANPR webhook'unu ve ML feedback okuma endpoint'ini Gin'e baglar.
type Handler struct {
	vehicleService         *vehicle.Service
	blacklistService       *blacklist.Service
	expectedArrivalService *expectedarrival.Service
	correctionService      *CorrectionService
	hub                    *realtime.Hub
	notificationService    notification.Service
}

// NewHandler, ANPR akisinin ihtiyac duydugu tum bagimliliklarla bir Handler olusturur.
func NewHandler(
	vehicleService *vehicle.Service,
	blacklistService *blacklist.Service,
	expectedArrivalService *expectedarrival.Service,
	correctionService *CorrectionService,
	hub *realtime.Hub,
	notificationService notification.Service,
) *Handler {
	return &Handler{
		vehicleService:         vehicleService,
		blacklistService:       blacklistService,
		expectedArrivalService: expectedArrivalService,
		correctionService:      correctionService,
		hub:                    hub,
		notificationService:    notificationService,
	}
}

// Register, anpr route'larini verilen gruba ekler.
func (h *Handler) Register(rg *gin.RouterGroup) {
	rg.POST("/events", h.handleEvent)
	rg.GET("/corrections", h.listCorrections)
}

// handleEvent, GEREKSINIM 3 ve 6: plakayi kaydeder, kara listeyi kontrol eder,
// ilgili depodaki guvenlik gorevlilerine WebSocket ile vehicle.ready_for_review yollar;
// kara listede ise ONCELIKLI vehicle.blacklist_alert + Web Push bildirimi tetikler.
func (h *Handler) handleEvent(c *gin.Context) {
	var evt WebhookEvent
	if err := c.ShouldBindJSON(&evt); err != nil {
		httpresponse.BadRequest(c, "gecersiz istek govdesi")
		return
	}
	if err := validator.Validate(evt); err != nil {
		httpresponse.BadRequest(c, err.Error())
		return
	}

	ctx := c.Request.Context()

	v, err := h.vehicleService.FindOrCreateByPlaka(ctx, evt.Plaka)
	if err != nil {
		httpresponse.Internal(c, "arac kaydi olusturulamadi")
		return
	}

	// Once araci beklenen giris listesiyle eslestirmeyi dene (gereksinim 7).
	if _, matched, err := h.expectedArrivalService.TryMatchArrival(ctx, evt.DepotID, evt.Plaka); err != nil {
		httpresponse.Internal(c, "beklenen arac eslestirmesi basarisiz")
		return
	} else {
		_ = matched
	}

	// Kara liste kontrolu (gereksinim 6): ONCELIKLI/KRITIK event.
	if bl, found, err := h.blacklistService.Check(ctx, blacklist.TipVehicle, v.ID); err != nil {
		httpresponse.Internal(c, "kara liste kontrolu basarisiz")
		return
	} else if found {
		h.hub.Broadcast(realtime.Event{
			Type:    realtime.EventVehicleBlacklistAlert,
			DepotID: evt.DepotID,
			Payload: realtime.BlacklistAlertPayload{
				Tip:        blacklist.TipVehicle,
				RefID:      v.ID,
				Plaka:      evt.Plaka,
				Sebep:      bl.Sebep,
				DepotID:    evt.DepotID,
				DetectedAt: evt.DetectedAt.Format(time.RFC3339),
			},
		})
		if err := h.notificationService.NotifyDepot(ctx, evt.DepotID, "blacklist_alert",
			"Kara listedeki arac tespit edildi: "+evt.Plaka, bl.Sebep); err != nil {
			httpresponse.Internal(c, "bildirim gonderilemedi")
			return
		}
	}

	// Guvenlik gorevlisinin formunu otomatik doldurmasi icin her zaman gonderilen event.
	h.hub.Broadcast(realtime.Event{
		Type:    realtime.EventVehicleReadyForReview,
		DepotID: evt.DepotID,
		Payload: realtime.ReadyForReviewPayload{
			Plaka:           evt.Plaka,
			ConfidenceScore: evt.ConfidenceScore,
			ImageURL:        evt.ImageURL,
			CameraID:        evt.CameraID,
			DetectedAt:      evt.DetectedAt.Format(time.RFC3339),
		},
	})

	httpresponse.OK(c, http.StatusOK, gin.H{"vehicle_id": v.ID, "plaka": v.Plaka})
}

// listCorrections, Python ML servisinin okuyup modeli yeniden egitmek icin kullanacagi
// duzeltme gecmisini dondurur (gereksinim: ML feedback donguse).
func (h *Handler) listCorrections(c *gin.Context) {
	corrections, err := h.correctionService.ListCorrections(c.Request.Context(), 200)
	if err != nil {
		httpresponse.Internal(c, "duzeltmeler listelenemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, corrections)
}
