// Package depot, tesis/depo lokasyonlarinin yonetimini icerir.
package depot

import (
	"time"

	"github.com/google/uuid"
)

// Depot, depot tablosundaki bir satiri temsil eder.
type Depot struct {
	ID        uuid.UUID `json:"id"`
	Name      string    `json:"name"`
	Location  string    `json:"location"`
	CreatedAt time.Time `json:"created_at"`
}

// CreateRequest, yeni depo olusturma istegi govdesidir.
type CreateRequest struct {
	Name     string `json:"name" validate:"required"`
	Location string `json:"location"`
}

// UpdateRequest, depo guncelleme istegi govdesidir.
type UpdateRequest struct {
	Name     string `json:"name" validate:"required"`
	Location string `json:"location"`
}
