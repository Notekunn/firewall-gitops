# Phase 04: HTTP Webhook Handler

**Priority:** High
**Status:** Pending
**Dependencies:** Phase 01, 02, 03

## Overview

HTTP server receiving SOAR webhook POSTs, orchestrating end-to-end flow: parse body → clone repo → update YAML → commit → push → create MR.

## Key Insights

- Webhook body format from body.txt: JSON with attacker.type and attacker.value
- Support only ip_v4 type initially (reject others)
- Generate unique branch names per request (timestamp-based)
- Return HTTP 200 on success, 4xx/5xx on errors
- Add timeout per request (prevent hanging)

## Requirements

### Functional
- Accept POST /webhook endpoint
- Parse JSON body matching SOAR format
- Validate attacker.type = "ip_v4"
- Extract attacker.value (IP address)
- Clone repo → update YAML → commit → push → create MR
- Return success/failure response
- Log all operations with request ID

### Non-Functional
- Handle concurrent requests (goroutine-safe)
- 30s timeout per webhook processing
- Structured JSON logging
- Graceful shutdown on SIGTERM
- Health check endpoint (GET /health)

## Architecture

```
POST /webhook → Handler → Service.ProcessAlert() → [Repo + YAML] → MR
                   ↓
              Request ID → Structured Logs
```

**Service Layer:**
Orchestrates: GitLabRepository + YAMLProcessor

## Related Code Files

**Create:**
- `internal/handler/webhook.go` - HTTP handlers
- `internal/handler/webhook_test.go` - Handler tests
- `internal/service/processor.go` - Business logic orchestration
- `internal/service/processor_test.go` - Service tests

**Modify:**
- `cmd/webhook/main.go` - Add HTTP server setup

## Implementation Steps

### 1. Define Request/Response Types
**File:** `internal/handler/webhook.go`

```go
package handler

import (
    "context"
    "encoding/json"
    "fmt"
    "log/slog"
    "net/http"
    "time"

    "firewall-gitops/webhook-soar/internal/service"
)

type WebhookHandler struct {
    processor *service.Processor
}

func NewWebhookHandler(processor *service.Processor) *WebhookHandler {
    return &WebhookHandler{processor: processor}
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

    // Parse request body
    var req SOARWebhookRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        h.respondError(w, http.StatusBadRequest, fmt.Sprintf("invalid json: %v", err), logger)
        return
    }

    // Validate attacker type
    if req.Attacker.Type != "ip_v4" {
        h.respondError(w, http.StatusBadRequest,
            fmt.Sprintf("unsupported attacker type: %s", req.Attacker.Type), logger)
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
```

### 2. Implement Service Processor
**File:** `internal/service/processor.go`

```go
package service

import (
    "context"
    "fmt"
    "log/slog"
    "time"

    "firewall-gitops/webhook-soar/internal/repository"
)

type Processor struct {
    repo          *repository.GitLabRepository
    yamlProcessor *YAMLProcessor
}

func NewProcessor(repo *repository.GitLabRepository, yamlProc *YAMLProcessor) *Processor {
    return &Processor{
        repo:          repo,
        yamlProcessor: yamlProc,
    }
}

// ProcessAlert orchestrates full workflow
func (p *Processor) ProcessAlert(ctx context.Context, ip, ticketID, reason string) (int, error) {
    slog.Info("processing alert", "ip", ip, "ticket_id", ticketID)

    // 1. Clone repository
    repoPath, err := p.repo.CloneToTemp(ctx)
    if err != nil {
        return 0, fmt.Errorf("clone failed: %w", err)
    }
    defer p.repo.Cleanup(repoPath)

    // 2. Create feature branch
    branchName := fmt.Sprintf("soar-block-%s-%d", ticketID, time.Now().Unix())
    if err := p.repo.CreateBranch(ctx, repoPath, branchName); err != nil {
        return 0, fmt.Errorf("create branch failed: %w", err)
    }

    // 3. Update YAML
    added, err := p.yamlProcessor.AddIP(repoPath, ip)
    if err != nil {
        return 0, fmt.Errorf("yaml update failed: %w", err)
    }

    if !added {
        slog.Info("ip already in blocklist", "ip", ip)
        // IP already exists - still success, no MR needed
        return 0, nil
    }

    // 4. Commit changes
    commitMsg := fmt.Sprintf("feat: block IP %s from SOAR ticket %s\n\nReason: %s", ip, ticketID, reason)
    if err := p.repo.CommitChanges(ctx, repoPath, commitMsg); err != nil {
        return 0, fmt.Errorf("commit failed: %w", err)
    }

    // 5. Push branch
    if err := p.repo.PushBranch(ctx, repoPath, branchName); err != nil {
        return 0, fmt.Errorf("push failed: %w", err)
    }

    // 6. Create merge request
    mrTitle := fmt.Sprintf("Block IP %s (SOAR: %s)", ip, ticketID)
    mrDesc := fmt.Sprintf(`## SOAR Alert

**Ticket ID:** %s
**Blocked IP:** %s
**Reason:** %s

This MR was automatically generated by the SOAR webhook service.
`, ticketID, ip, reason)

    mrID, err := p.repo.CreateMergeRequest(ctx, branchName, mrTitle, mrDesc)
    if err != nil {
        return 0, fmt.Errorf("create MR failed: %w", err)
    }

    slog.Info("alert processed successfully",
        "ip", ip,
        "branch", branchName,
        "merge_request_id", mrID)

    return mrID, nil
}
```

### 3. Update Main with HTTP Server
**File:** `cmd/webhook/main.go`

```go
package main

import (
    "context"
    "log/slog"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"

    "firewall-gitops/webhook-soar/internal/config"
    "firewall-gitops/webhook-soar/internal/handler"
    "firewall-gitops/webhook-soar/internal/repository"
    "firewall-gitops/webhook-soar/internal/service"
)

func main() {
    logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
    slog.SetDefault(logger)

    cfg, err := config.Load()
    if err != nil {
        slog.Error("failed to load config", "error", err)
        os.Exit(1)
    }

    repo, err := repository.NewGitLabRepository(
        cfg.GitLabURL,
        cfg.GitLabToken,
        cfg.GitLabProjectID,
        cfg.GitLabBranch,
    )
    if err != nil {
        slog.Error("failed to initialize gitlab repository", "error", err)
        os.Exit(1)
    }

    yamlProc := service.NewYAMLProcessor(cfg.YAMLFilePath, cfg.ObjectPath)
    processor := service.NewProcessor(repo, yamlProc)
    webhookHandler := handler.NewWebhookHandler(processor)

    mux := http.NewServeMux()
    mux.HandleFunc("/webhook", webhookHandler.HandleWebhook)
    mux.HandleFunc("/health", webhookHandler.HandleHealth)

    server := &http.Server{
        Addr:         ":" + cfg.ServerPort,
        Handler:      mux,
        ReadTimeout:  10 * time.Second,
        WriteTimeout: 40 * time.Second,
    }

    // Graceful shutdown
    go func() {
        slog.Info("webhook service started", "port", cfg.ServerPort)
        if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            slog.Error("server error", "error", err)
            os.Exit(1)
        }
    }()

    // Wait for interrupt
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
    <-sigChan

    slog.Info("shutting down gracefully...")
    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()

    if err := server.Shutdown(ctx); err != nil {
        slog.Error("shutdown error", "error", err)
    }

    slog.Info("server stopped")
}
```

### 4. Write Tests
**File:** `internal/handler/webhook_test.go`

Test cases:
- Successful webhook processing
- Invalid JSON body
- Unsupported attacker type
- Method not allowed (GET)
- Health endpoint returns 200

**File:** `internal/service/processor_test.go`

Mock repository and YAML processor, test:
- End-to-end alert processing
- Duplicate IP handling (no MR)
- Error propagation from components

## Todo List

- [ ] Implement WebhookHandler with POST /webhook
- [ ] Implement HandleHealth for health checks
- [ ] Implement Processor.ProcessAlert() orchestration
- [ ] Generate unique branch names (timestamp-based)
- [ ] Add 30s context timeout per request
- [ ] Write handler unit tests
- [ ] Write processor unit tests
- [ ] Update main.go with HTTP server
- [ ] Implement graceful shutdown (SIGTERM)
- [ ] Add request ID logging
- [ ] Test concurrent webhook requests

## Success Criteria

- POST /webhook accepts SOAR body format
- Validates attacker.type = "ip_v4"
- Orchestrates full workflow (clone → update → commit → MR)
- Returns MR ID on success
- Health endpoint responds 200
- Graceful shutdown on SIGTERM
- Structured logging with request IDs

## Risk Assessment

**Medium risk** - HTTP server, concurrent requests, error handling.

**Mitigations:**
- Context timeouts prevent hanging requests
- Defer cleanup for temp directories
- Structured error responses
- Extensive error logging with context
- Idempotency (duplicate IPs don't create MRs)

## Security Considerations

- Validate Content-Type (application/json)
- Limit request body size (prevent DoS)
- Rate limiting (optional: consider per IP)
- Input validation before processing
- No sensitive data in logs (token, passwords)
- HTTPS in production (TLS termination at proxy)

## Next Steps

After phase 04:
- Phase 05: Testing and deployment
- Integration tests with real GitLab instance
- Dockerfile and deployment docs
