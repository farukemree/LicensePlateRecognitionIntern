// rbac.go, rol bazli yetkilendirme ve depo erisim kontrolu icin Gin middleware'lerini icerir.
package auth

import (
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/example/plaka-takip-backend/pkg/httpresponse"
)

// Sistemdeki dort sabit rol.
const (
	RoleAdmin             = "admin"
	RoleDepoYoneticisi    = "depo_yoneticisi"
	RoleGuvenlikGorevlisi = "guvenlik_gorevlisi"
	RoleOperasyon         = "operasyon"
)

// AllRoles, gecerli JWT yeten ama ekstra rol kisitlamasi olmayan endpoint'ler icin kullanilir
// (ornegin kara liste endpoint'leri - spesifikasyon geregi tum roller erisebilir).
var AllRoles = []string{RoleAdmin, RoleDepoYoneticisi, RoleGuvenlikGorevlisi, RoleOperasyon}

// RequireRoles, giris yapmis kullanicinin rolunun verilen listede olmasini zorunlu kilar.
func RequireRoles(roles ...string) gin.HandlerFunc {
	allowed := make(map[string]struct{}, len(roles))
	for _, r := range roles {
		allowed[r] = struct{}{}
	}
	return func(c *gin.Context) {
		u, err := MustCurrentUser(c)
		if err != nil {
			c.Abort()
			return
		}
		if _, ok := allowed[u.Rol]; !ok {
			httpresponse.Forbidden(c, "bu islem icin yetkiniz yok")
			c.Abort()
			return
		}
		c.Next()
	}
}

// RequireDepotAccess, path parametresinde gelen depot_id'nin kullanicinin erisebildigi
// depolardan biri olmasini kontrol eder. admin rolu her depoya erisebilir.
func RequireDepotAccess(paramName string) gin.HandlerFunc {
	return func(c *gin.Context) {
		u, err := MustCurrentUser(c)
		if err != nil {
			c.Abort()
			return
		}

		raw := c.Param(paramName)
		if raw == "" {
			raw = c.Query(paramName)
		}
		if raw == "" {
			// depot_id verilmemis (ornegin liste endpoint'i); erisim filtrelemesi service katmaninda yapilir.
			c.Next()
			return
		}

		depotID, err := uuid.Parse(raw)
		if err != nil {
			httpresponse.BadRequest(c, "gecersiz depot_id")
			c.Abort()
			return
		}

		if !u.HasDepotAccess(depotID) {
			httpresponse.Forbidden(c, "bu depoya erisim yetkiniz yok")
			c.Abort()
			return
		}
		c.Next()
	}
}

// AccessibleDepotIDs, admin ise nil (kisitlama yok, tum depolar) dondurur;
// digerlerinde kullanicinin erisebildigi depot_id listesini dondurur.
// Repository katmaninda WHERE depot_id = ANY($1) seklinde kullanilmak uzere tasarlandi.
func AccessibleDepotIDs(u User) []uuid.UUID {
	if u.Rol == RoleAdmin {
		return nil
	}
	return u.DepotIDs
}
