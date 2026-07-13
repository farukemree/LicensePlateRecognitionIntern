// main.go, uygulamanin giris noktasidir: config yukler, migration calistirir,
// tum modulleri (repository->service->handler) birbirine baglar ve HTTP sunucusunu ayaga kaldirir.
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"

	"github.com/example/plaka-takip-backend/internal/anpr"
	"github.com/example/plaka-takip-backend/internal/audit"
	"github.com/example/plaka-takip-backend/internal/auth"
	"github.com/example/plaka-takip-backend/internal/blacklist"
	"github.com/example/plaka-takip-backend/internal/cache"
	"github.com/example/plaka-takip-backend/internal/config"
	"github.com/example/plaka-takip-backend/internal/db"
	"github.com/example/plaka-takip-backend/internal/depot"
	"github.com/example/plaka-takip-backend/internal/driver"
	"github.com/example/plaka-takip-backend/internal/expectedarrival"
	"github.com/example/plaka-takip-backend/internal/notification"
	"github.com/example/plaka-takip-backend/internal/realtime"
	"github.com/example/plaka-takip-backend/internal/router"
	"github.com/example/plaka-takip-backend/internal/vehicle"
	"github.com/example/plaka-takip-backend/internal/vehiclelog"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config yuklenemedi: %v", err)
	}

	// Migration'lar her baslangicta otomatik calisir; elle "migrate" CLI komutu gerekmez.
	if err := db.RunMigrations(cfg.Database); err != nil {
		log.Fatalf("migration basarisiz: %v", err)
	}

	pool, err := db.NewPool(ctx, cfg.Database)
	if err != nil {
		log.Fatalf("veritabani baglantisi kurulamadi: %v", err)
	}
	defer pool.Close()

	var appCache cache.Cache
	if cfg.Redis.Enabled {
		appCache = cache.NewRedisCache(cfg.Redis.Addr, cfg.Redis.Password, cfg.Redis.DB)
		log.Println("cache: redis etkin")
	} else {
		appCache = cache.NewNoopCache()
		log.Println("cache: redis devre disi, noop cache kullaniliyor")
	}
	_ = appCache // ileride sorgu sonucu cache'lemek icin modul servislerine gecirilebilir.

	auditService := audit.NewService(pool)

	notificationRepo := notification.NewRepository(pool)
	notificationService := notification.NewWebPushService(
		notificationRepo, cfg.WebPush.VAPIDPublicKey, cfg.WebPush.VAPIDPrivateKey, cfg.WebPush.VAPIDSubject,
	)

	hub := realtime.NewHub()
	go hub.Run()

	depotService := depot.NewService(depot.NewRepository(pool))
	vehicleService := vehicle.NewService(vehicle.NewRepository(pool))
	driverService := driver.NewService(driver.NewRepository(pool))
	blacklistService := blacklist.NewService(blacklist.NewRepository(pool), auditService)
	expectedArrivalService := expectedarrival.NewService(expectedarrival.NewRepository(pool))
	correctionService := anpr.NewCorrectionService(anpr.NewCorrectionRepository(pool))

	vehicleLogService := vehiclelog.NewService(
		vehiclelog.NewRepository(pool),
		vehicleService, driverService, blacklistService, correctionService, expectedArrivalService,
		hub, notificationService,
	)

	authMW, err := auth.NewMiddleware(ctx, cfg.Auth.JWKSURL, cfg.Auth.Issuer, cfg.Auth.Audience, pool)
	if err != nil {
		log.Fatalf("auth middleware olusturulamadi: %v", err)
	}

	handlers := router.Handlers{
		Depot:           depot.NewHandler(depotService),
		Vehicle:         vehicle.NewHandler(vehicleService),
		VehicleLog:      vehiclelog.NewHandler(vehicleLogService),
		Blacklist:       blacklist.NewHandler(blacklistService),
		ExpectedArrival: expectedarrival.NewHandler(expectedArrivalService),
		ANPR: anpr.NewHandler(
			vehicleService, blacklistService, expectedArrivalService, correctionService, hub, notificationService,
		),
	}

	engine := router.New(authMW, hub, handlers)

	addr := fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port)
	srv := &http.Server{Addr: addr, Handler: engine}

	go func() {
		log.Printf("sunucu %s adresinde dinliyor", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("sunucu baslatilamadi: %v", err)
		}
	}()

	<-ctx.Done()
	log.Println("kapatma sinyali alindi, sunucu nazikce durduruluyor...")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("sunucu duzgun kapatilamadi: %v", err)
	}
}
