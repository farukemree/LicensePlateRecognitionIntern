// Package router, tum HTTP route'larini ve middleware zincirini Gin uzerinden kurar.
package router

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/example/plaka-takip-backend/internal/anpr"
	"github.com/example/plaka-takip-backend/internal/auth"
	"github.com/example/plaka-takip-backend/internal/blacklist"
	"github.com/example/plaka-takip-backend/internal/depot"
	"github.com/example/plaka-takip-backend/internal/expectedarrival"
	"github.com/example/plaka-takip-backend/internal/realtime"
	"github.com/example/plaka-takip-backend/internal/vehicle"
	"github.com/example/plaka-takip-backend/internal/vehiclelog"
	"github.com/example/plaka-takip-backend/pkg/httpresponse"
)

// Handlers, router'in ihtiyac duydugu tum modul handler'larini tasir.
type Handlers struct {
	Depot           *depot.Handler
	Vehicle         *vehicle.Handler
	VehicleLog      *vehiclelog.Handler
	Blacklist       *blacklist.Handler
	ExpectedArrival *expectedarrival.Handler
	ANPR            *anpr.Handler
}

// New, tum route'lari kayitli bir *gin.Engine olusturur.
func New(authMW *auth.Middleware, hub *realtime.Hub, h Handlers) *gin.Engine {
	r := gin.New()
	r.Use(gin.Recovery(), gin.Logger(), corsMiddleware())

	// Health-check: Docker Compose healthcheck ve LAN dogrulama icin, auth gerektirmez.
	r.GET("/healthz", func(c *gin.Context) {
		httpresponse.OK(c, http.StatusOK, gin.H{"status": "ok"})
	})

	v1 := r.Group("/api/v1")

	// ANPR webhook + ML feedback okuma: Python mikroservisi tarafindan LAN icinden cagirilir.
	// LAN-ici guvenilir agdan geldigi varsayilir; ileri fazda paylasimli-secret/mTLS eklenebilir (bkz. README TODO).
	anprGroup := v1.Group("/anpr")
	h.ANPR.Register(anprGroup)

	// Bu noktadan sonraki tum route'lar JWT (Keycloak/JWKS) ile korunur.
	authenticated := v1.Group("")
	authenticated.Use(authMW.Handle())

	authenticated.GET("/ws", hub.ServeWS)

	h.Depot.Register(authenticated.Group("/depots"))
	h.Vehicle.Register(authenticated.Group("/vehicles"))
	h.VehicleLog.Register(authenticated.Group("/vehicle-logs"))
	// Kara liste: rol kisitlamasi yok, sadece gecerli JWT (gereksinim 5).
	h.Blacklist.Register(authenticated.Group("/blacklist"))
	h.ExpectedArrival.Register(authenticated.Group("/expected-arrivals"))

	return r
}

// corsMiddleware, LAN icindeki farkli host/portlardan (kiosk, saha bilgisayari) gelen
// tarayici isteklerine izin verir.
func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Authorization, Content-Type")
		if c.Request.Method == http.MethodOptions {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}
