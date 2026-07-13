// Package blacklist, kara listeye alinan arac/sofor kayitlarini yonetir.
// Tum roller (admin, depo_yoneticisi, guvenlik_gorevlisi, operasyon) bu endpoint'lere
// erisebilir; ekstra rol kisitlamasi yoktur, sadece gecerli JWT yeterlidir.
// Her yazma islemi audit_log'a dusurulur.
package blacklist

import (
	"time"

	"github.com/google/uuid"
)

// Tip sabitleri.
const (
	TipVehicle = "vehicle"
	TipDriver  = "driver"
)

// Blacklist, blacklist tablosundaki bir satiri temsil eder.
type Blacklist struct {
	ID               uuid.UUID  `json:"id"`
	Tip              string     `json:"tip"`
	RefID            uuid.UUID  `json:"ref_id"`
	Sebep            string     `json:"sebep"`
	EklenenYetkiliID *uuid.UUID `json:"eklenen_yetkili_id,omitempty"`
	CreatedAt        time.Time  `json:"created_at"`
	Aktif            bool       `json:"aktif"`
}

// CreateRequest, kara listeye ekleme istegi govdesidir.
type CreateRequest struct {
	Tip   string    `json:"tip" validate:"required,oneof=vehicle driver"`
	RefID uuid.UUID `json:"ref_id" validate:"required"`
	Sebep string    `json:"sebep" validate:"required"`
}
