package expectedarrival

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/example/plaka-takip-backend/internal/auth"
	"github.com/example/plaka-takip-backend/pkg/httpresponse"
	"github.com/example/plaka-takip-backend/pkg/validator"
)

// Handler, expected_arrival HTTP endpoint'lerini Gin'e baglar.
type Handler struct {
	service *Service
}

// NewHandler, verilen Service ile bir Handler olusturur.
func NewHandler(service *Service) *Handler {
	return &Handler{service: service}
}

// Register, expected-arrivals route'larini verilen gruba ekler.
func (h *Handler) Register(rg *gin.RouterGroup) {
	rg.GET("", h.list)
	rg.POST("", h.create)
	rg.DELETE("/:id", h.delete)
}

func (h *Handler) list(c *gin.Context) {
	u, err := auth.MustCurrentUser(c)
	if err != nil {
		return
	}
	items, err := h.service.List(c.Request.Context(), auth.AccessibleDepotIDs(u))
	if err != nil {
		httpresponse.Internal(c, "beklenen araclar listelenemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, items)
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
	e, err := h.service.Create(c.Request.Context(), req)
	if err != nil {
		httpresponse.Internal(c, "beklenen arac olusturulamadi")
		return
	}
	httpresponse.Created(c, e)
}

func (h *Handler) delete(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		httpresponse.BadRequest(c, "gecersiz id")
		return
	}
	if err := h.service.Delete(c.Request.Context(), id); err != nil {
		httpresponse.Internal(c, "beklenen arac silinemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, gin.H{"deleted": true})
}
