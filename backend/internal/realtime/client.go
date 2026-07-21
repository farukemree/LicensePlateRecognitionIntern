// client.go, tek bir WebSocket baglantisini (bir tarayici sekmesi) temsil eder.
package realtime

import (
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/websocket"
)

const (
	writeWait  = 10 * time.Second
	pongWait   = 60 * time.Second
	pingPeriod = (pongWait * 9) / 10
)

// Client, depot bazli bir "oda"ya bagli tek bir WebSocket baglantisidir.
type Client struct {
	hub     *Hub
	conn    *websocket.Conn
	send    chan []byte
	UserID  uuid.UUID
	DepotID uuid.UUID
}

// NewClient, verilen baglanti ve kullanici/depo bilgisiyle bir Client olusturur.
func NewClient(hub *Hub, conn *websocket.Conn, userID, depotID uuid.UUID) *Client {
	return &Client{
		hub:     hub,
		conn:    conn,
		send:    make(chan []byte, 32),
		UserID:  userID,
		DepotID: depotID,
	}
}

// ReadPump, istemciden gelen mesajlari okur (yalnizca baglanti canliligi icin kullanilir).
func (c *Client) ReadPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()
	c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})
	for {
		if _, _, err := c.conn.ReadMessage(); err != nil {
			break
		}
	}
}

// WritePump, hub'dan gelen event'leri istemciye yazar ve periyodik ping atar.
func (c *Client) WritePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()
	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := c.conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}
