// Package vehicle, sisteme kayitli araclarin (plaka bazli) yonetimini icerir.
package vehicle

import (
	"time"

	"github.com/google/uuid"
)

// Vehicle, vehicle tablosundaki bir satiri temsil eder.
type Vehicle struct {
	ID            uuid.UUID  `json:"id"`
	Plaka         string     `json:"plaka"`
	AracTuru      string     `json:"arac_turu"`
	MuayeneTarihi *time.Time `json:"muayene_tarihi,omitempty"`
	CreatedAt     time.Time  `json:"created_at"`
}

// CreateRequest, yeni arac olusturma istegi govdesidir.
type CreateRequest struct {
	Plaka         string     `json:"plaka" validate:"required"`
	AracTuru      string     `json:"arac_turu"`
	MuayeneTarihi *time.Time `json:"muayene_tarihi"`
}

// UpdateRequest, arac guncelleme istegi govdesidir.
type UpdateRequest struct {
	AracTuru      string     `json:"arac_turu"`
	MuayeneTarihi *time.Time `json:"muayene_tarihi"`
}
