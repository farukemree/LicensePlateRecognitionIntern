// Package auth, Keycloak (OIDC) tarafindan uretilen JWT'leri JWKS ile dogrular
// ve dogrulanan token'in "sub" alanindan yerel kullaniciyi (rol + depo erisimi) yukler.
package auth

import (
	"context"
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/MicahParks/keyfunc/v3"
	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/example/plaka-takip-backend/pkg/httpresponse"
)

const contextUserKey = "auth.user"

// User, JWT dogrulandiktan sonra context'e konan, sistemdeki yerel kullaniciyi temsil eder.
type User struct {
	ID          uuid.UUID
	KeycloakSub string
	AdSoyad     string
	Rol         string
	DepotIDs    []uuid.UUID
}

// HasDepotAccess, kullanicinin verilen depoyu gorebilip goremeyecegini soyler.
// admin rolu her zaman tum depolara erisebilir.
func (u User) HasDepotAccess(depotID uuid.UUID) bool {
	if u.Rol == RoleAdmin {
		return true
	}
	for _, id := range u.DepotIDs {
		if id == depotID {
			return true
		}
	}
	return false
}

// claims, dogrulanan JWT'nin bizim icin onemli alanlaridir.
type claims struct {
	jwt.RegisteredClaims
}

// Middleware, JWKS tabanli JWT dogrulamasi yapan ve kullaniciyi yukleyen Gin middleware'idir.
type Middleware struct {
	jwks     keyfunc.Keyfunc
	issuer   string
	audience string
	pool     *pgxpool.Pool
}

// NewMiddleware, verilen JWKS URL'ini periyodik olarak yenileyerek bir Middleware olusturur.
func NewMiddleware(ctx context.Context, jwksURL, issuer, audience string, pool *pgxpool.Pool) (*Middleware, error) {
	jwks, err := keyfunc.NewDefaultCtx(ctx, []string{jwksURL})
	if err != nil {
		return nil, err
	}
	return &Middleware{jwks: jwks, issuer: issuer, audience: audience, pool: pool}, nil
}

// Handle, Authorization: Bearer <token> basligini dogrular ve kullaniciyi context'e ekler.
func (m *Middleware) Handle() gin.HandlerFunc {
	return func(c *gin.Context) {
		var tokenStr string
		if header := c.GetHeader("Authorization"); strings.HasPrefix(header, "Bearer ") {
			tokenStr = strings.TrimPrefix(header, "Bearer ")
		} else if q := c.Query("token"); q != "" {
			// Tarayici WebSocket handshake'inde ozel header gonderemedigi icin
			// query parametresi olarak token gonderilmesine de izin verilir (ws://.../ws?token=...).
			tokenStr = q
		} else {
			httpresponse.Unauthorized(c, "Authorization basligi veya token parametresi eksik")
			c.Abort()
			return
		}

		parserOpts := []jwt.ParserOption{jwt.WithIssuer(m.issuer)}
		if m.audience != "" {
			parserOpts = append(parserOpts, jwt.WithAudience(m.audience))
		}

		token, err := jwt.ParseWithClaims(tokenStr, &claims{}, m.jwks.Keyfunc, parserOpts...)
		if err != nil || !token.Valid {
			httpresponse.Unauthorized(c, "gecersiz veya suresi dolmus token")
			c.Abort()
			return
		}

		tc, ok := token.Claims.(*claims)
		if !ok || tc.Subject == "" {
			httpresponse.Unauthorized(c, "token icinde 'sub' bulunamadi")
			c.Abort()
			return
		}

		user, err := loadUser(c.Request.Context(), m.pool, tc.Subject)
		if err != nil {
			httpresponse.Forbidden(c, "kullanici sistemde taniml degil")
			c.Abort()
			return
		}

		c.Set(contextUserKey, *user)
		c.Next()
	}
}

// loadUser, "user" tablosundan keycloak_sub ile eslesen kullaniciyi ve depo erisimlerini ceker.
func loadUser(ctx context.Context, pool *pgxpool.Pool, keycloakSub string) (*User, error) {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	var u User
	row := pool.QueryRow(ctx, `SELECT id, ad_soyad, rol FROM "user" WHERE keycloak_sub = $1`, keycloakSub)
	if err := row.Scan(&u.ID, &u.AdSoyad, &u.Rol); err != nil {
		return nil, err
	}
	u.KeycloakSub = keycloakSub

	rows, err := pool.Query(ctx, `SELECT depot_id FROM user_depot_access WHERE user_id = $1`, u.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var depotID uuid.UUID
		if err := rows.Scan(&depotID); err != nil {
			return nil, err
		}
		u.DepotIDs = append(u.DepotIDs, depotID)
	}
	return &u, nil
}

// CurrentUser, gin context'ine daha once yerlestirilmis kullaniciyi getirir.
func CurrentUser(c *gin.Context) (User, bool) {
	v, ok := c.Get(contextUserKey)
	if !ok {
		return User{}, false
	}
	u, ok := v.(User)
	return u, ok
}

// MustCurrentUser, kullanici yoksa 401 doner ve handler'i sonlandirir; varsa kullaniciyi getirir.
func MustCurrentUser(c *gin.Context) (User, error) {
	u, ok := CurrentUser(c)
	if !ok {
		httpresponse.Error(c, http.StatusUnauthorized, "unauthorized", "kimlik dogrulanamadi")
		return User{}, errors.New("kullanici context'te yok")
	}
	return u, nil
}
