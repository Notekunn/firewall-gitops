package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestWebhookHandler_HandleHealth(t *testing.T) {
	handler := &WebhookHandler{}

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	handler.HandleHealth(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "healthy", resp["status"])
}

func TestWebhookHandler_MethodNotAllowed(t *testing.T) {
	handler := &WebhookHandler{}

	req := httptest.NewRequest("GET", "/webhook", nil)
	w := httptest.NewRecorder()

	handler.HandleWebhook(w, req)

	assert.Equal(t, http.StatusMethodNotAllowed, w.Code)

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, false, resp["success"])
	assert.Equal(t, "method not allowed", resp["message"])
}

func TestWebhookHandler_InvalidContentType(t *testing.T) {
	handler := &WebhookHandler{}

	body, _ := json.Marshal(map[string]interface{}{})
	req := httptest.NewRequest("POST", "/webhook", bytes.NewReader(body))
	req.Header.Set("Content-Type", "text/plain")
	w := httptest.NewRecorder()

	handler.HandleWebhook(w, req)

	assert.Equal(t, http.StatusUnsupportedMediaType, w.Code)
}

func TestWebhookHandler_InvalidJSON(t *testing.T) {
	handler := &WebhookHandler{}

	req := httptest.NewRequest("POST", "/webhook", strings.NewReader("invalid json"))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	handler.HandleWebhook(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestWebhookHandler_MissingTicketID(t *testing.T) {
	handler := &WebhookHandler{}

	body, _ := json.Marshal(map[string]interface{}{
		"attacker": map[string]interface{}{
			"type":  "ip_v4",
			"value": "10.0.0.100",
		},
	})
	req := httptest.NewRequest("POST", "/webhook", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	handler.HandleWebhook(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestWebhookHandler_UnsupportedAttackerType(t *testing.T) {
	handler := &WebhookHandler{}

	body, _ := json.Marshal(map[string]interface{}{
		"ticket_id": "TICKET-123",
		"attacker": map[string]interface{}{
			"type":  "domain",
			"value": "evil.com",
		},
	})
	req := httptest.NewRequest("POST", "/webhook", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	handler.HandleWebhook(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestWebhookHandler_MissingAttackerValue(t *testing.T) {
	handler := &WebhookHandler{}

	body, _ := json.Marshal(map[string]interface{}{
		"ticket_id": "TICKET-123",
		"attacker": map[string]interface{}{
			"type": "ip_v4",
		},
	})
	req := httptest.NewRequest("POST", "/webhook", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	handler.HandleWebhook(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestWebhookHandler_BodySizeLimit(t *testing.T) {
	handler := &WebhookHandler{}

	// Create a very large JSON body (over 1MB)
	largeBody := strings.Repeat("a", 2<<20) // 2MB
	body, _ := json.Marshal(map[string]interface{}{
		"ticket_id": "TICKET-123",
		"attacker": map[string]interface{}{
			"type":  "ip_v4",
			"value": largeBody,
		},
	})

	req := httptest.NewRequest("POST", "/webhook", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	handler.HandleWebhook(w, req)

	assert.Equal(t, http.StatusRequestEntityTooLarge, w.Code)
}

func TestWebhookHandler_APIKeyValidation(t *testing.T) {
	tests := []struct {
		name        string
		apiKey      string
		providedKey string
		wantStatus  int
	}{
		{
			name:        "no api key required - accepts request",
			apiKey:      "",
			providedKey: "",
			wantStatus:  http.StatusBadRequest, // passes auth, fails on missing fields
		},
		{
			name:        "no api key required - ignores provided key",
			apiKey:      "",
			providedKey: "some-key",
			wantStatus:  http.StatusBadRequest, // passes auth, fails on missing fields
		},
		{
			name:        "api key required - correct key",
			apiKey:      "secret-key",
			providedKey: "secret-key",
			wantStatus:  http.StatusBadRequest, // passes auth, fails on missing fields
		},
		{
			name:        "api key required - wrong key",
			apiKey:      "secret-key",
			providedKey: "wrong-key",
			wantStatus:  http.StatusUnauthorized,
		},
		{
			name:        "api key required - missing key",
			apiKey:      "secret-key",
			providedKey: "",
			wantStatus:  http.StatusUnauthorized,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			h := &WebhookHandler{processor: nil, apiKey: tt.apiKey}

			req := httptest.NewRequest("POST", "/webhook", strings.NewReader("{}"))
			req.Header.Set("Content-Type", "application/json")
			if tt.providedKey != "" {
				req.Header.Set("X-API-Key", tt.providedKey)
			}

			w := httptest.NewRecorder()
			h.HandleWebhook(w, req)

			assert.Equal(t, tt.wantStatus, w.Code)

			if tt.wantStatus == http.StatusUnauthorized {
				var resp map[string]interface{}
				err := json.Unmarshal(w.Body.Bytes(), &resp)
				assert.NoError(t, err)
				assert.Equal(t, false, resp["success"])
				assert.Equal(t, "invalid or missing API key", resp["message"])
			}
		})
	}
}