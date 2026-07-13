// Package driver, soforlerin yonetimini icerir. Ayri bir HTTP yuzeyi yoktur;
// vehiclelog akisi icinde plaka/soför bilgisi birlikte islenir.
package driver

import (
	"time"

	"github.com/google/uuid"
)

// Driver, driver tablosundaki bir satiri temsil eder.
type Driver struct {
	ID        uuid.UUID `json:"id"`
	AdSoyad   string    `json:"ad_soyad"`
	TCNo      string    `json:"tc_no"`
	Telefon   string    `json:"telefon"`
	CreatedAt time.Time `json:"created_at"`
}
