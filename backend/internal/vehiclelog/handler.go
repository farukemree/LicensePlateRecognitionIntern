package vehiclelog

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

// Handler, vehicle-logs HTTP endpoint'lerini Gin'e baglar.
type Handler struct {
	service *Service
}

// NewHandler, verilen Service ile bir Handler olusturur.
func NewHandler(service *Service) *Handler {
	return &Handler{service: service}
}

// Register, vehicle-logs route'larini verilen gruba ekler.
func (h *Handler) Register(rg *gin.RouterGroup) {
	rg.GET("", h.list)
	rg.GET("/:id", h.get)
	rg.POST("", h.create)
}

func (h *Handler) list(c *gin.Context) {
	u, err := auth.MustCurrentUser(c)
	if err != nil {
		return
	}
	logs, err := h.service.List(c.Request.Context(), auth.AccessibleDepotIDs(u))
	if err != nil {
		httpresponse.Internal(c, "kayitlar listelenemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, logs)
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
	log, err := h.service.Get(c.Request.Context(), id)
	if errors.Is(err, pgx.ErrNoRows) {
		httpresponse.NotFound(c, "kayit bulunamadi")
		return
	}
	if err != nil {
		httpresponse.Internal(c, "kayit getirilemedi")
		return
	}
	if !u.HasDepotAccess(log.DepotID) {
		httpresponse.Forbidden(c, "bu depoya erisim yetkiniz yok")
		return
	}
	httpresponse.OK(c, http.StatusOK, log)
}

func (h *Handler) create(c *gin.Context) {
	u, err := auth.MustCurrentUser(c)
	if err != nil {
		return
	}
	var req CreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		httpresponse.BadRequest(c, "gecersiz istek govdesi")
		return
	}
	if err := validator.Validate(req); err != nil {
		httpresponse.BadRequest(c, err.Error())
		return
	}
	if !u.HasDepotAccess(req.DepotID) {
		httpresponse.Forbidden(c, "bu depoya erisim yetkiniz yok")
		return
	}

	log, err := h.service.Create(c.Request.Context(), u.ID, req)
	if err != nil {
		httpresponse.Internal(c, "kayit olusturulamadi")
		return
	}
	httpresponse.Created(c, log)
}
