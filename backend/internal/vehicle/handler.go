package vehicle

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/example/plaka-takip-backend/pkg/httpresponse"
	"github.com/example/plaka-takip-backend/pkg/validator"
)

// Handler, vehicle HTTP endpoint'lerini Gin'e baglar. Tum roller okuyabilir/yazabilir;
// arac kaydi operasyonel bir veridir, depo bazli degildir.
type Handler struct {
	service *Service
}

// NewHandler, verilen Service ile bir Handler olusturur.
func NewHandler(service *Service) *Handler {
	return &Handler{service: service}
}

// Register, vehicle route'larini verilen gruba ekler.
func (h *Handler) Register(rg *gin.RouterGroup) {
	rg.GET("", h.list)
	rg.GET("/:id", h.get)
	rg.POST("", h.create)
	rg.PUT("/:id", h.update)
	rg.DELETE("/:id", h.delete)
}

func (h *Handler) list(c *gin.Context) {
	vehicles, err := h.service.List(c.Request.Context())
	if err != nil {
		httpresponse.Internal(c, "araclar listelenemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, vehicles)
}

func (h *Handler) get(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		httpresponse.BadRequest(c, "gecersiz id")
		return
	}
	v, err := h.service.Get(c.Request.Context(), id)
	if errors.Is(err, pgx.ErrNoRows) {
		httpresponse.NotFound(c, "arac bulunamadi")
		return
	}
	if err != nil {
		httpresponse.Internal(c, "arac getirilemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, v)
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
	v, err := h.service.Create(c.Request.Context(), req)
	if err != nil {
		httpresponse.Internal(c, "arac olusturulamadi")
		return
	}
	httpresponse.Created(c, v)
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
	v, err := h.service.Update(c.Request.Context(), id, req)
	if err != nil {
		httpresponse.Internal(c, "arac guncellenemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, v)
}

func (h *Handler) delete(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		httpresponse.BadRequest(c, "gecersiz id")
		return
	}
	if err := h.service.Delete(c.Request.Context(), id); err != nil {
		httpresponse.Internal(c, "arac silinemedi")
		return
	}
	httpresponse.OK(c, http.StatusOK, gin.H{"deleted": true})
}
