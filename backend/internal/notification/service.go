package notification

import (
	"context"

	"github.com/google/uuid"
)

// Service, bildirim gonderiminin tek noktasidir. Spesifikasyon geregi tek implementasyon
// (WebPush, bkz. webpush.go) yeterlidir; interface ileride farkli kanallar eklemeye izin verir.
type Service interface {
	// NotifyDepot, verilen depoya erisimi olan TUM kullanicilara bildirim gonderir
	// (kara liste uyarisi gibi depo genelindeki kritik olaylar icin).
	NotifyDepot(ctx context.Context, depotID uuid.UUID, tip, baslik, mesaj string) error
	// NotifyUser, tek bir kullaniciya bildirim gonderir.
	NotifyUser(ctx context.Context, userID uuid.UUID, depotID *uuid.UUID, tip, baslik, mesaj string) error
	// Subscribe, kullanicinin tarayicisindan gelen Web Push abonelik bilgisini kaydeder.
	Subscribe(ctx context.Context, userID uuid.UUID, endpoint, p256dh, authKey string) error
	// ListForUser, kullanicinin bildirim gecmisini dondurur (panelde gosterilmek uzere).
	ListForUser(ctx context.Context, userID uuid.UUID, limit int) ([]Notification, error)
}
