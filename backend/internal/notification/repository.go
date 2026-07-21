package notification

import (
	"context"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Repository, notification ve webpush_subscription tablolarina erisimi soyutlar.
type Repository interface {
	Create(ctx context.Context, n *Notification) error
	ListByUser(ctx context.Context, userID uuid.UUID, limit int) ([]Notification, error)
	MarkRead(ctx context.Context, id uuid.UUID) error
	SaveSubscription(ctx context.Context, sub *Subscription) error
	UsersForDepot(ctx context.Context, depotID uuid.UUID) ([]uuid.UUID, error)
	SubscriptionsForUser(ctx context.Context, userID uuid.UUID) ([]Subscription, error)
}

// pgRepository, Repository'nin PostgreSQL/pgx implementasyonudur.
type pgRepository struct {
	pool *pgxpool.Pool
}

// NewRepository, verilen pool ile bir Repository olusturur.
func NewRepository(pool *pgxpool.Pool) Repository {
	return &pgRepository{pool: pool}
}

func (r *pgRepository) Create(ctx context.Context, n *Notification) error {
	return r.pool.QueryRow(ctx, `
		INSERT INTO notification (user_id, depot_id, tip, baslik, mesaj)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, created_at
	`, n.UserID, n.DepotID, n.Tip, n.Baslik, n.Mesaj).Scan(&n.ID, &n.CreatedAt)
}

func (r *pgRepository) ListByUser(ctx context.Context, userID uuid.UUID, limit int) ([]Notification, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, user_id, depot_id, tip, baslik, mesaj, okundu, created_at
		FROM notification
		WHERE user_id = $1
		ORDER BY created_at DESC
		LIMIT $2
	`, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []Notification
	for rows.Next() {
		var n Notification
		if err := rows.Scan(&n.ID, &n.UserID, &n.DepotID, &n.Tip, &n.Baslik, &n.Mesaj, &n.Okundu, &n.CreatedAt); err != nil {
			return nil, err
		}
		results = append(results, n)
	}
	return results, rows.Err()
}

func (r *pgRepository) MarkRead(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `UPDATE notification SET okundu = true WHERE id = $1`, id)
	return err
}

func (r *pgRepository) SaveSubscription(ctx context.Context, sub *Subscription) error {
	return r.pool.QueryRow(ctx, `
		INSERT INTO webpush_subscription (user_id, endpoint, p256dh, auth)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (user_id, endpoint) DO UPDATE SET p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth
		RETURNING id, created_at
	`, sub.UserID, sub.Endpoint, sub.P256dh, sub.Auth).Scan(&sub.ID, &sub.CreatedAt)
}

func (r *pgRepository) UsersForDepot(ctx context.Context, depotID uuid.UUID) ([]uuid.UUID, error) {
	rows, err := r.pool.Query(ctx, `SELECT user_id FROM user_depot_access WHERE depot_id = $1`, depotID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var ids []uuid.UUID
	for rows.Next() {
		var id uuid.UUID
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

func (r *pgRepository) SubscriptionsForUser(ctx context.Context, userID uuid.UUID) ([]Subscription, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, user_id, endpoint, p256dh, auth, created_at
		FROM webpush_subscription
		WHERE user_id = $1
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []Subscription
	for rows.Next() {
		var s Subscription
		if err := rows.Scan(&s.ID, &s.UserID, &s.Endpoint, &s.P256dh, &s.Auth, &s.CreatedAt); err != nil {
			return nil, err
		}
		results = append(results, s)
	}
	return results, rows.Err()
}
