// hub.go, depo bazli "oda" mantigiyla calisan WebSocket baglanti merkezidir.
// Bir kullanici sadece yetkili oldugu depolarin event'lerini alir.
package realtime

import (
	"encoding/json"
	"log"
	"net/http"
	"sync"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"

	"github.com/example/plaka-takip-backend/internal/auth"
	"github.com/example/plaka-takip-backend/pkg/httpresponse"
)

// Hub, tum depo odalarini ve bu odalardaki istemcileri yonetir.
type Hub struct {
	mu         sync.RWMutex
	rooms      map[uuid.UUID]map[*Client]bool
	register   chan *Client
	unregister chan *Client
}

// NewHub, bos bir Hub olusturur. Calismasi icin Run() goroutine olarak baslatilmalidir.
func NewHub() *Hub {
	return &Hub{
		rooms:      make(map[uuid.UUID]map[*Client]bool),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

// Run, register/unregister kanallarini dinleyen ana dongudur; main.go icinde `go hub.Run()` ile baslatilir.
func (h *Hub) Run() {
	for {
		select {
		case c := <-h.register:
			h.mu.Lock()
			if h.rooms[c.DepotID] == nil {
				h.rooms[c.DepotID] = make(map[*Client]bool)
			}
			h.rooms[c.DepotID][c] = true
			h.mu.Unlock()
		case c := <-h.unregister:
			h.mu.Lock()
			if clients, ok := h.rooms[c.DepotID]; ok {
				if _, ok := clients[c]; ok {
					delete(clients, c)
					close(c.send)
					if len(clients) == 0 {
						delete(h.rooms, c.DepotID)
					}
				}
			}
			h.mu.Unlock()
		}
	}
}

// Broadcast, verilen depodaki tum baglantida olan istemcilere event'i JSON olarak yayinlar.
func (h *Hub) Broadcast(event Event) {
	data, err := json.Marshal(event)
	if err != nil {
		log.Printf("realtime: event serialize edilemedi: %v", err)
		return
	}

	h.mu.RLock()
	defer h.mu.RUnlock()
	for c := range h.rooms[event.DepotID] {
		select {
		case c.send <- data:
		default:
			// Gonderim kanali dolu (yavas/olu istemci); mesaji atla, baglantiyi Run() dongusu temizleyecek.
		}
	}
}

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	// LAN-ici kullanim senaryosu: tarayici istemcileri ayni agdaki farkli host/portlardan
	// (kiosk, saha bilgisayari) baglanabildigi icin origin kontrolu gevsek tutulmustur.
	CheckOrigin: func(r *http.Request) bool { return true },
}

// ServeWS, Gin route'una baglanan WebSocket upgrade handler'idir.
// Depo erisimi auth.User.HasDepotAccess ile dogrulanir.
func (h *Hub) ServeWS(c *gin.Context) {
	user, err := auth.MustCurrentUser(c)
	if err != nil {
		return
	}

	depotIDRaw := c.Query("depot_id")
	depotID, err := uuid.Parse(depotIDRaw)
	if err != nil {
		httpresponse.BadRequest(c, "gecerli bir depot_id query parametresi gerekli")
		return
	}

	if !user.HasDepotAccess(depotID) {
		httpresponse.Forbidden(c, "bu depoya erisim yetkiniz yok")
		return
	}

	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("realtime: websocket upgrade basarisiz: %v", err)
		return
	}

	client := NewClient(h, conn, user.ID, depotID)
	h.register <- client

	go client.WritePump()
	go client.ReadPump()
}
