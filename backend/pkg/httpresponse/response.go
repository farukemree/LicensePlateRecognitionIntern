// Package httpresponse, tum handler'larin kullandigi tutarli JSON basari/hata formatidir.
package httpresponse

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// Envelope, tum API yanitlarinin ortak zarfidir.
type Envelope struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   *ErrorBody  `json:"error,omitempty"`
}

// ErrorBody, hata durumunda dondurulen bilgidir.
type ErrorBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

// OK, basarili bir yaniti verilen HTTP durum koduyla doner.
func OK(c *gin.Context, status int, data interface{}) {
	c.JSON(status, Envelope{Success: true, Data: data})
}

// Created, 201 Created yaniti icin kisayoldur.
func Created(c *gin.Context, data interface{}) {
	OK(c, http.StatusCreated, data)
}

// Error, standart hata zarfini verilen HTTP durum koduyla doner.
func Error(c *gin.Context, status int, code, message string) {
	c.JSON(status, Envelope{Success: false, Error: &ErrorBody{Code: code, Message: message}})
}

// BadRequest, 400 icin kisayoldur.
func BadRequest(c *gin.Context, message string) {
	Error(c, http.StatusBadRequest, "bad_request", message)
}

// Unauthorized, 401 icin kisayoldur.
func Unauthorized(c *gin.Context, message string) {
	Error(c, http.StatusUnauthorized, "unauthorized", message)
}

// Forbidden, 403 icin kisayoldur.
func Forbidden(c *gin.Context, message string) {
	Error(c, http.StatusForbidden, "forbidden", message)
}

// NotFound, 404 icin kisayoldur.
func NotFound(c *gin.Context, message string) {
	Error(c, http.StatusNotFound, "not_found", message)
}

// Internal, 500 icin kisayoldur.
func Internal(c *gin.Context, message string) {
	Error(c, http.StatusInternalServerError, "internal_error", message)
}
