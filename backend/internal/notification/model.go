// Package notification, sadece sistem ici bildirimleri (WebSocket + Web Push) yonetir.
// SMTP/e-posta kapsam disidir.
package notification

import (
	"time"

	"github.com/google/uuid"
)

// Notification, notification tablosundaki bir satiri temsil eder (kullanicinin
// panelde gorebilecegi bildirim gecmisi).
type Notification struct {
	ID        uuid.UUID  `json:"id"`
	UserID    *uuid.UUID `json:"user_id,omitempty"`
	DepotID   *uuid.UUID `json:"depot_id,omitempty"`
	Tip       string     `json:"tip"`
	Baslik    string     `json:"baslik"`
	Mesaj     string     `json:"mesaj,omitempty"`
	Okundu    bool       `json:"okundu"`
	CreatedAt time.Time  `json:"created_at"`
}

// Subscription, bir kullanicinin tarayicisindan alinan Web Push abonelik bilgisidir.
type Subscription struct {
	ID        uuid.UUID `json:"id"`
	UserID    uuid.UUID `json:"user_id"`
	Endpoint  string    `json:"endpoint"`
	P256dh    string    `json:"p256dh"`
	Auth      string    `json:"auth"`
	CreatedAt time.Time `json:"created_at"`
}
