package depot

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/example/plaka-takip-backend/internal/auth"
	"github.com/example/plaka-takip-backend/pkg/httpresponse"
	"github.com/example/plaka-takip-backend/pkg/validator"
)

// Handler, depot HTTP endpoint'lerini Gin'e baglar.
type Handler struct {
	service *Service
}

// NewHandler, verilen Service ile bir Handler olusturur.
func NewHandler(service *Service) *Handler {
	return &Handler{service: service}
}

// Register, depot route'larini verilen gruba ekler.
// Olusturma/guncelleme/silme admin ve depo_yoneticisi ile sinirlidir; okuma tum rollere aciktir
// (kullanicinin erisebildigi depolarla otomatik filtrelenir).
func (h *Handler) Register(rg *gin.RouterGroup) {
	rg.GET("", h.list)
	rg.GET("/:id", h.get)
	rg.POST("", auth.RequireRoles(auth.RoleAdmin, auth.RoleDepoYoneticisi), h.create)
	rg.PUT("/:id", auth.RequireRoles(auth.RoleAdmin, auth.RoleDepoYoneticisi), h.update)
	rg.DELETE("/:id", auth.RequireRoles(auth.RoleAdmin), h.delete)
}

func (h *Handler) list(c *gin.Context) {
	u, err := auth.MustCurrentUser(c)
	if err != nil {
		return
	}
	depots, err := h.service.List(c.Request.Context(), auth.AccessibleDepotIDs(u))
	if err != nil {
		httpresponse.Internal(c, "depolar listelenemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, depots)
}

func (h *Handler) get(c *gin.Context) {
	u, err := auth.MustCurrentUser(c)
	if err != nil {
		return
	}
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		httpresponse.BadRequest(c, "gecersiz id")
		return
	}
	if !u.HasDepotAccess(id) {
		httpresponse.Forbidden(c, "bu depoya erisim yetkiniz yok")
		return
	}
	d, err := h.service.Get(c.Request.Context(), id)
	if errors.Is(err, pgx.ErrNoRows) {
		httpresponse.NotFound(c, "depo bulunamadi")
		return
	}
	if err != nil {
		httpresponse.Internal(c, "depo getirilemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, d)
}

func (h *Handler) create(c *gin.Context) {
	var req CreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		httpresponse.BadRequest(c, "gecersiz istek govdesi")
		return
	}
	if err := validator.Validate(req); err != nil {
		httpresponse.BadRequest(c, err.Error())
		return
	}
	d, err := h.service.Create(c.Request.Context(), req)
	if err != nil {
		httpresponse.Internal(c, "depo olusturulamadi")
		return
	}
	httpresponse.Created(c, d)
}

func (h *Handler) update(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		httpresponse.BadRequest(c, "gecersiz id")
		return
	}
	var req UpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		httpresponse.BadRequest(c, "gecersiz istek govdesi")
		return
	}
	if err := validator.Validate(req); err != nil {
		httpresponse.BadRequest(c, err.Error())
		return
	}
	d, err := h.service.Update(c.Request.Context(), id, req)
	if err != nil {
		httpresponse.Internal(c, "depo guncellenemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, d)
}

func (h *Handler) delete(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		httpresponse.BadRequest(c, "gecersiz id")
		return
	}
	if err := h.service.Delete(c.Request.Context(), id); err != nil {
		httpresponse.Internal(c, "depo silinemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, gin.H{"deleted": true})
}
