// Package vehiclelog, guvenlik gorevlisinin onayladigi depo giris/cikis kayitlarini yonetir.
package vehiclelog

import (
	"time"

	"github.com/google/uuid"
)

// Yon sabitleri.
const (
	YonGiris = "giris"
	YonCikis = "cikis"
)

// VehicleLog, vehicle_log tablosundaki bir satiri temsil eder.
type VehicleLog struct {
	ID                 uuid.UUID  `json:"id"`
	DepotID            uuid.UUID  `json:"depot_id"`
	VehicleID          uuid.UUID  `json:"vehicle_id"`
	DriverID           *uuid.UUID `json:"driver_id,omitempty"`
	UserID             *uuid.UUID `json:"user_id,omitempty"`
	Yon                string     `json:"yon"`
	IrsaliyeNo         string     `json:"irsaliye_no,omitempty"`
	RomorkNo           string     `json:"romork_no,omitempty"`
	MuhurNo            string     `json:"muhur_no,omitempty"`
	KonteynerNo        string     `json:"konteyner_no,omitempty"`
	TasimacilikSirketi string     `json:"tasimacilik_sirketi,omitempty"`
	EmniyetKemeri      bool       `json:"emniyet_kemeri"`
	AsmaKilit          bool       `json:"asma_kilit"`
	Tarih              time.Time  `json:"tarih"`
	Aciklama           string     `json:"aciklama,omitempty"`
	CreatedAt          time.Time  `json:"created_at"`
}

// SoforBilgisi, istekte opsiyonel olarak gelen sofor bilgisidir.
type SoforBilgisi struct {
	AdSoyad string `json:"ad_soyad"`
	TCNo    string `json:"tc_no"`
	Telefon string `json:"telefon"`
}

// ANPRBilgisi, bu kaydin bir ANPR tespitinden geldigini belirten opsiyonel bilgidir.
// PlakaTahmini, girilen nihai Plaka'dan farkliysa anpr_correction tablosuna otomatik kayit dusurulur
// (gereksinim 4).
type ANPRBilgisi struct {
	PlakaTahmini    string   `json:"plaka_tahmini"`
	ConfidenceScore *float64 `json:"confidence_score"`
	ImageURL        string   `json:"image_url"`
}

// CreateRequest, POST /api/v1/vehicle-logs istek govdesidir.
type CreateRequest struct {
	DepotID            uuid.UUID     `json:"depot_id" validate:"required"`
	Plaka              string        `json:"plaka" validate:"required"`
	AracTuru           string        `json:"arac_turu"`
	Sofor              *SoforBilgisi `json:"sofor"`
	Yon                string        `json:"yon" validate:"required,oneof=giris cikis"`
	IrsaliyeNo         string        `json:"irsaliye_no"`
	RomorkNo           string        `json:"romork_no"`
	MuhurNo            string        `json:"muhur_no"`
	KonteynerNo        string        `json:"konteyner_no"`
	TasimacilikSirketi string        `json:"tasimacilik_sirketi"`
	EmniyetKemeri      bool          `json:"emniyet_kemeri"`
	AsmaKilit          bool          `json:"asma_kilit"`
	Tarih              *time.Time    `json:"tarih"`
	Aciklama           string        `json:"aciklama"`
	ANPR               *ANPRBilgisi  `json:"anpr"`
}
