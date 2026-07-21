// Package audit, kritik aksiyonlarin (kara liste degisiklikleri, kayit silme vb.) izlenebilirligini saglar.
package audit

import (
	"time"

	"github.com/google/uuid"
)

// LogEntry, audit_log tablosundaki bir satiri temsil eder.
type LogEntry struct {
	ID        uuid.UUID              `json:"id"`
	UserID    *uuid.UUID             `json:"user_id,omitempty"`
	Action    string                 `json:"action"`
	Entity    string                 `json:"entity"`
	EntityID  *uuid.UUID             `json:"entity_id,omitempty"`
	Detay     map[string]interface{} `json:"detay,omitempty"`
	CreatedAt time.Time              `json:"created_at"`
}
