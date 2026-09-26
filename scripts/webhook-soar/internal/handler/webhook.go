package handler

import (
	"context"
	"crypto/subtle"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"time"

	"firewall-gitops/webhook-soar/internal/service"
)

// Processor interface enables mocking for testing
type Processor interface {
	ProcessAlert(ctx context.Context, ip, ticketID, reason string) (int, error)
}

type WebhookHandler struct {
	processor Processor
	apiKey    string
}

func NewWebhookHandler(processor *service.Processor, apiKey string) *WebhookHandler {
	return &WebhookHandler{processor: processor, apiKey: apiKey}
}

// SOAR webhook request body
type SOARWebhookRequest struct {
	TicketID     string `json:"ticket_id"`
	SourceSystem string `json:"source_system"`
	Target       struct {
		Domain string `json:"domain"`
	} `json:"target"`
	Attacker struct {
		Type  string `json:"type"`
		Value string `json:"value"`
	} `json:"attacker"`
	Reason string `json:"reason"`
}

// Response body
type WebhookResponse struct {
	Success      bool   `json:"success"`
	Message      string `json:"message"`
	MergeRequest int    `json:"merge_request,omitempty"`
}

func (h *WebhookHandler) HandleWebhook(w http.ResponseWriter, r *http.Request) {
	requestID := fmt.Sprintf("%d", time.Now().UnixNano())
	logger := slog.With("request_id", requestID)

	logger.Info("received webhook request",
		"method", r.Method,
		"remote_addr", r.RemoteAddr)

	// Only accept POST
	if r.Method != http.MethodPost {
		h.respondError(w, http.StatusMethodNotAllowed, "method not allowed", logger)
		return
	}

	// Validate content type
	if r.Header.Get("Content-Type") != "application/json" {
		h.respondError(w, http.StatusUnsupportedMediaType, "content-type must be application/json", logger)
		return
	}

	// Validate API key if configured
	if h.apiKey != "" {
		providedKey := r.Header.Get("X-API-Key")
		if subtle.ConstantTimeCompare([]byte(providedKey), []byte(h.apiKey)) != 1 {
			h.respondError(w, http.StatusUnauthorized, "invalid or missing API key", logger)
			return
		}
	}

	// Limit request body size (1MB)
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)

	// Parse request body
	var req SOARWebhookRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		// Check if body too large
		if err.Error() == "http: request body too large" {
			h.respondError(w, http.StatusRequestEntityTooLarge, "request body too large", logger)
			return
		}
		h.respondError(w, http.StatusBadRequest, fmt.Sprintf("invalid json: %v", err), logger)
		return
	}

	// Validate required fields
	if req.TicketID == "" {
		h.respondError(w, http.StatusBadRequest, "ticket_id is required", logger)
		return
	}

	// Validate attacker type
	if req.Attacker.Type != "ip_v4" {
		h.respondError(w, http.StatusBadRequest,
			fmt.Sprintf("unsupported attacker type: %s", req.Attacker.Type), logger)
		return
	}

	// Validate attacker value
	if req.Attacker.Value == "" {
		h.respondError(w, http.StatusBadRequest, "attacker.value is required", logger)
		return
	}

	logger.Info("processing webhook",
		"ticket_id", req.TicketID,
		"source_system", req.SourceSystem,
		"attacker_ip", req.Attacker.Value,
		"reason", req.Reason)

	// Process with timeout
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	mrID, err := h.processor.ProcessAlert(ctx, req.Attacker.Value, req.TicketID, req.Reason)
	if err != nil {
		h.respondError(w, http.StatusInternalServerError,
			fmt.Sprintf("processing failed: %v", err), logger)
		return
	}

	// Success response
	resp := WebhookResponse{
		Success:      true,
		Message:      "IP added to blocklist",
		MergeRequest: mrID,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(resp)

	logger.Info("webhook processed successfully",
		"merge_request_id", mrID,
		"ip", req.Attacker.Value)
}

func (h *WebhookHandler) HandleHealth(w http.ResponseWriter, r *http.Request) {
	logger := slog.With("request_id", fmt.Sprintf("%d", time.Now().UnixNano()))

	logger.Info("health check", "remote_addr", r.RemoteAddr)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy"})
}

func (h *WebhookHandler) respondError(w http.ResponseWriter, status int, message string, logger *slog.Logger) {
	logger.Error("webhook error", "status", status, "message", message)

	resp := WebhookResponse{
		Success: false,
		Message: message,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(resp)
}
