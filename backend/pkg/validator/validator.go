// Package validator, struct tag tabanli girdi dogrulamasi icin ince bir sarmalayicidir.
package validator

import (
	"fmt"
	"strings"

	"github.com/go-playground/validator/v10"
)

var instance = validator.New()

// Validate, verilen struct'i `validate` tag'lerine gore dogrular.
// Hata varsa okunabilir, alan bazli bir mesaj dondurur.
func Validate(s interface{}) error {
	if err := instance.Struct(s); err != nil {
		validationErrs, ok := err.(validator.ValidationErrors)
		if !ok {
			return err
		}
		var parts []string
		for _, fe := range validationErrs {
			parts = append(parts, fmt.Sprintf("%s: %s", fe.Field(), fe.Tag()))
		}
		return fmt.Errorf("dogrulama hatasi: %s", strings.Join(parts, ", "))
	}
	return nil
}
