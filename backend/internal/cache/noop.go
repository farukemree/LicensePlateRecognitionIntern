package cache

import (
	"context"
	"time"
)

// NoopCache, Redis olmadan sistemin ayaga kalkabilmesi icin hicbir sey saklamayan
// bir Cache implementasyonudur. Her Get "bulunamadi" doner.
type NoopCache struct{}

// NewNoopCache, NoopCache olusturur.
func NewNoopCache() *NoopCache {
	return &NoopCache{}
}

func (n *NoopCache) Get(ctx context.Context, key string) (string, bool, error) {
	return "", false, nil
}

func (n *NoopCache) Set(ctx context.Context, key, value string, ttl time.Duration) error {
	return nil
}

func (n *NoopCache) Del(ctx context.Context, key string) error {
	return nil
}
