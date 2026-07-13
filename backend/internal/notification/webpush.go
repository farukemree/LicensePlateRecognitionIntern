package notification

import (
	"context"
	"encoding/json"
	"log"

	webpushgo "github.com/SherClockHolmes/webpush-go"
	"github.com/google/uuid"
)

// WebPushService, Service arayuzunun Web Push (VAPID) tabanli implementasyonudur.
// Her bildirim ayrica notification tablosuna yazilir ki kullanici gecmisi panelden gorebilsin.
type WebPushService struct {
	repo      Repository
	vapidPub  string
	vapidPriv string
	vapidSub  string
}

// NewWebPushService, verilen repository ve VAPID anahtarlariyla bir WebPushService olusturur.
func NewWebPushService(repo Repository, vapidPublicKey, vapidPrivateKey, vapidSubject string) *WebPushService {
	return &WebPushService{
		repo:      repo,
		vapidPub:  vapidPublicKey,
		vapidPriv: vapidPrivateKey,
		vapidSub:  vapidSubject,
	}
}

type pushPayload struct {
	Baslik string `json:"baslik"`
	Mesaj  string `json:"mesaj"`
	Tip    string `json:"tip"`
}

func (s *WebPushService) NotifyDepot(ctx context.Context, depotID uuid.UUID, tip, baslik, mesaj string) error {
	userIDs, err := s.repo.UsersForDepot(ctx, depotID)
	if err != nil {
		return err
	}
	for _, userID := range userIDs {
		if err := s.NotifyUser(ctx, userID, &depotID, tip, baslik, mesaj); err != nil {
			log.Printf("notification: kullanici %s bilgilendirilemedi: %v", userID, err)
		}
	}
	return nil
}

func (s *WebPushService) NotifyUser(ctx context.Context, userID uuid.UUID, depotID *uuid.UUID, tip, baslik, mesaj string) error {
	n := &Notification{UserID: &userID, DepotID: depotID, Tip: tip, Baslik: baslik, Mesaj: mesaj}
	if err := s.repo.Create(ctx, n); err != nil {
		return err
	}
	s.sendWebPush(ctx, userID, tip, baslik, mesaj)
	return nil
}

func (s *WebPushService) sendWebPush(ctx context.Context, userID uuid.UUID, tip, baslik, mesaj string) {
	if s.vapidPub == "" || s.vapidPriv == "" {
		// VAPID anahtarlari tanimli degil (ornegin gelistirme ortami); sadece DB kaydi ile yetinilir.
		return
	}

	subs, err := s.repo.SubscriptionsForUser(ctx, userID)
	if err != nil {
		log.Printf("notification: abonelikler okunamadi: %v", err)
		return
	}

	body, err := json.Marshal(pushPayload{Baslik: baslik, Mesaj: mesaj, Tip: tip})
	if err != nil {
		log.Printf("notification: payload serialize edilemedi: %v", err)
		return
	}

	for _, sub := range subs {
		wpSub := &webpushgo.Subscription{
			Endpoint: sub.Endpoint,
			Keys: webpushgo.Keys{
				P256dh: sub.P256dh,
				Auth:   sub.Auth,
			},
		}
		resp, err := webpushgo.SendNotification(body, wpSub, &webpushgo.Options{
			Subscriber:      s.vapidSub,
			VAPIDPublicKey:  s.vapidPub,
			VAPIDPrivateKey: s.vapidPriv,
			TTL:             30,
		})
		if err != nil {
			log.Printf("notification: web push gonderilemedi: %v", err)
			continue
		}
		resp.Body.Close()
	}
}

func (s *WebPushService) Subscribe(ctx context.Context, userID uuid.UUID, endpoint, p256dh, authKey string) error {
	sub := &Subscription{UserID: userID, Endpoint: endpoint, P256dh: p256dh, Auth: authKey}
	return s.repo.SaveSubscription(ctx, sub)
}

func (s *WebPushService) ListForUser(ctx context.Context, userID uuid.UUID, limit int) ([]Notification, error) {
	if limit <= 0 {
		limit = 50
	}
	return s.repo.ListByUser(ctx, userID, limit)
}
