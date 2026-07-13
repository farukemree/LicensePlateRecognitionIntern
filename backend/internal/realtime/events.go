// events.go, WebSocket uzerinden yayinlanan event tiplerini tanimlar.
package realtime

import "github.com/google/uuid"

const (
	// EventVehicleDetected, ANPR servisi bir plaka tespit ettiginde (henuz inceleme oncesi) yayinlanir.
	EventVehicleDetected = "vehicle.detected"
	// EventVehicleReadyForReview, ANPR sonucu guvenlik gorevlisinin ekranindaki formu
	// otomatik doldurmaya hazir oldugunda yayinlanir.
	EventVehicleReadyForReview = "vehicle.ready_for_review"
	// EventVehicleBlacklistAlert, kara listedeki bir arac/sofor tespit edildiginde yayinlanan
	// ONCELIKLI/KRITIK event'tir. UI'da kirmizi/acil olarak isaretlenmelidir.
	EventVehicleBlacklistAlert = "vehicle.blacklist_alert"
)

// Event, WebSocket uzerinden gonderilen JSON mesaj zarfidir:
// {"type": "...", "depot_id": "...", "payload": {...}}
type Event struct {
	Type    string      `json:"type"`
	DepotID uuid.UUID   `json:"depot_id"`
	Payload interface{} `json:"payload"`
}

// BlacklistAlertPayload, vehicle.blacklist_alert event'inin payload'udur.
// "sebep" alani spesifikasyon geregi mutlaka bulunmalidir.
type BlacklistAlertPayload struct {
	Tip        string    `json:"tip"`
	RefID      uuid.UUID `json:"ref_id"`
	Plaka      string    `json:"plaka,omitempty"`
	Sebep      string    `json:"sebep"`
	DepotID    uuid.UUID `json:"depot_id"`
	DetectedAt string    `json:"detected_at,omitempty"`
}

// ReadyForReviewPayload, vehicle.ready_for_review event'inin payload'udur.
type ReadyForReviewPayload struct {
	Plaka           string  `json:"plaka"`
	ConfidenceScore float64 `json:"confidence_score"`
	ImageURL        string  `json:"image_url,omitempty"`
	CameraID        string  `json:"camera_id,omitempty"`
	DetectedAt      string  `json:"detected_at,omitempty"`
}
