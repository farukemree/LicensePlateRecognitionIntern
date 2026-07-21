// Package expectedarrival, beklenen arac girislerinin CRUD ve ANPR ile otomatik eslesme mantigini icerir.
package expectedarrival

import (
	"time"

	"github.com/google/uuid"
)

// Durum sabitleri.
const (
	DurumBekleniyor = "bekleniyor"
	DurumGeldi      = "geldi"
	DurumZamanAsimi = "zaman_asimi"
)

// ExpectedArrival, expected_arrival tablosundaki bir satiri temsil eder.
type ExpectedArrival struct {
	ID            uuid.UUID `json:"id"`
	DepotID       uuid.UUID `json:"depot_id"`
	Plaka         string    `json:"plaka"`
	BeklenenZaman time.Time `json:"beklenen_zaman"`
	Durum         string    `json:"durum"`
	CreatedAt     time.Time `json:"created_at"`
}

// CreateRequest, yeni beklenen arac kaydi olusturma istegi govdesidir.
type CreateRequest struct {
	DepotID       uuid.UUID `json:"depot_id" validate:"required"`
	Plaka         string    `json:"plaka" validate:"required"`
	BeklenenZaman time.Time `json:"beklenen_zaman" validate:"required"`
}
