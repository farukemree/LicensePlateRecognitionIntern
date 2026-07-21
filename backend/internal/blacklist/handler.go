package blacklist

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/example/plaka-takip-backend/internal/auth"
	"github.com/example/plaka-takip-backend/pkg/httpresponse"
	"github.com/example/plaka-takip-backend/pkg/validator"
)

// Handler, blacklist HTTP endpoint'lerini Gin'e baglar.
type Handler struct {
	service *Service
}

// NewHandler, verilen Service ile bir Handler olusturur.
func NewHandler(service *Service) *Handler {
	return &Handler{service: service}
}

// Register, blacklist route'larini verilen gruba ekler.
// GEREKSINIM 5: rol kisitlamasi YOK, sadece genel auth middleware (gecerli JWT) yeterli -
// bu grup zaten router.go'da genel auth.Handle() ile korunuyor, burada ek RequireRoles YOK.
func (h *Handler) Register(rg *gin.RouterGroup) {
	rg.GET("", h.list)
	rg.POST("", h.create)
	rg.DELETE("/:id", h.remove)
}

func (h *Handler) list(c *gin.Context) {
	items, err := h.service.List(c.Request.Context())
	if err != nil {
		httpresponse.Internal(c, "kara liste listelenemedi")
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
	b, err := h.service.Add(c.Request.Context(), u.ID, req)
	if err != nil {
		httpresponse.Internal(c, "kara listeye eklenemedi")
		return
	}
	httpresponse.Created(c, b)
}

func (h *Handler) remove(c *gin.Context) {
	u, err := auth.MustCurrentUser(c)
	if err != nil {
		return
	}
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		httpresponse.BadRequest(c, "gecersiz id")
		return
	}
	if err := h.service.Remove(c.Request.Context(), u.ID, id); err != nil {
		httpresponse.Internal(c, "kara listeden kaldirilamadi")
		return
	}
	httpresponse.OK(c, http.StatusOK, gin.H{"removed": true})
}
