// Package anpr, Python/YOLOv8 ANPR mikroservisinden gelen event/webhook'lari
// ve kullanici duzeltmelerinin (ML feedback) kaydini yonetir.
package anpr

import (
	"time"

	"github.com/google/uuid"
)

// WebhookEvent, ANPR servisinden POST /api/v1/anpr/events ile gelen payload'dur.
type WebhookEvent struct {
	DepotID         uuid.UUID `json:"depot_id" validate:"required"`
	CameraID        string    `json:"camera_id"`
	Plaka           string    `json:"plaka" validate:"required"`
	ConfidenceScore float64   `json:"confidence_score"`
	ImageURL        string    `json:"image_url"`
	DetectedAt      time.Time `json:"detected_at"`
}
