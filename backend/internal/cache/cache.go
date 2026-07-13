// Package cache, opsiyonel bir cache katmani tanimlar. Redis kesinlesene kadar
// NoopCache ile calisilabilir; ileride Redis devreye alinacaksa sadece
// New(cfg) fonksiyonunun dondurdugu implementasyon degisir, kullanici kod degismez.
package cache

import (
	"context"
	"time"
)

// Cache, uygulamanin ihtiyac duydugu minimal anahtar-deger islemleridir.
type Cache interface {
	Get(ctx context.Context, key string) (string, bool, error)
	Set(ctx context.Context, key, value string, ttl time.Duration) error
	Del(ctx context.Context, key string) error
}
