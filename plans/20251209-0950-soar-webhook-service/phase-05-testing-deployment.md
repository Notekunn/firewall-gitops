# Phase 05: Testing & Deployment

**Priority:** High
**Status:** Pending
**Dependencies:** Phase 01-04

## Overview

Integration testing, Dockerfile, deployment documentation, GitLab CI/CD integration.

## Key Insights

- Integration test against real GitLab project (test environment)
- Container-based deployment (follows project patterns)
- Environment variable configuration (12-factor app)
- Optional: GitLab CI job to deploy webhook service

## Requirements

### Functional
- Integration tests with real GitLab API
- Docker container for deployment
- Deployment documentation
- Example systemd service file
- Health check integration

### Non-Functional
- Container image size optimization
- Multi-stage Docker build
- Security: non-root user, minimal base image
- Clear deployment runbook

## Architecture

**Deployment Options:**
1. **Docker Compose** - Standalone deployment
2. **Kubernetes** - Production-grade (optional)
3. **Systemd Service** - Direct binary deployment

## Related Code Files

**Create:**
- `scripts/webhook-soar/Dockerfile` - Container image
- `scripts/webhook-soar/docker-compose.yml` - Local testing
- `scripts/webhook-soar/.env.example` - Example configuration
- `scripts/webhook-soar/deployments/webhook-service.service` - Systemd unit
- `scripts/webhook-soar/test/integration_test.go` - Integration tests

**Modify:**
- `scripts/webhook-soar/README.md` - Add deployment docs

## Implementation Steps

### 1. Create Integration Tests
**File:** `test/integration_test.go`

```go
//go:build integration
// +build integration

package test

import (
    "bytes"
    "context"
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "os"
    "testing"

    "firewall-gitops/webhook-soar/internal/config"
    "firewall-gitops/webhook-soar/internal/handler"
    "firewall-gitops/webhook-soar/internal/repository"
    "firewall-gitops/webhook-soar/internal/service"
)

func TestWebhookIntegration(t *testing.T) {
    // Requires real GitLab credentials
    if os.Getenv("INTEGRATION_TEST") != "true" {
        t.Skip("Skipping integration test")
    }

    cfg, err := config.Load()
    if err != nil {
        t.Fatalf("config load failed: %v", err)
    }

    repo, err := repository.NewGitLabRepository(
        cfg.GitLabURL,
        cfg.GitLabToken,
        cfg.GitLabProjectID,
        cfg.GitLabBranch,
    )
    if err != nil {
        t.Fatalf("repo init failed: %v", err)
    }

    yamlProc := service.NewYAMLProcessor(cfg.YAMLFilePath, cfg.ObjectPath)
    processor := service.NewProcessor(repo, yamlProc)
    webhookHandler := handler.NewWebhookHandler(processor)

    // Create test request
    reqBody := map[string]interface{}{
        "ticket_id":     "TEST-123",
        "source_system": "test-soar",
        "target": map[string]string{
            "domain": "example.com",
        },
        "attacker": map[string]string{
            "type":  "ip_v4",
            "value": "203.0.113.42", // TEST-NET-3
        },
        "reason": "Integration test - SQL injection attempts",
    }

    body, _ := json.Marshal(reqBody)
    req := httptest.NewRequest(http.MethodPost, "/webhook", bytes.NewReader(body))
    req.Header.Set("Content-Type", "application/json")

    w := httptest.NewRecorder()
    webhookHandler.HandleWebhook(w, req)

    if w.Code != http.StatusOK {
        t.Errorf("expected 200, got %d: %s", w.Code, w.Body.String())
    }

    var resp handler.WebhookResponse
    json.NewDecoder(w.Body).Decode(&resp)

    if !resp.Success {
        t.Errorf("expected success, got: %s", resp.Message)
    }

    if resp.MergeRequest == 0 {
        t.Log("IP already existed (no MR created)")
    } else {
        t.Logf("Created MR: %d", resp.MergeRequest)
    }
}
```

**Run integration tests:**
```bash
INTEGRATION_TEST=true go test -tags=integration ./test/...
```

### 2. Create Dockerfile
**File:** `Dockerfile`

```dockerfile
# Multi-stage build
FROM golang:1.21-alpine AS builder

WORKDIR /build

# Install git (required for go get with private repos)
RUN apk add --no-cache git ca-certificates

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source
COPY . .

# Build binary
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o webhook ./cmd/webhook

# Runtime image
FROM alpine:latest

# Install ca-certificates and git (for git operations)
RUN apk --no-cache add ca-certificates git

# Create non-root user
RUN addgroup -g 1000 webhook && \
    adduser -D -u 1000 -G webhook webhook

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/webhook .

# Change ownership
RUN chown -R webhook:webhook /app

USER webhook

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/webhook"]
```

### 3. Create Docker Compose
**File:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  webhook:
    build: .
    ports:
      - "8080:8080"
    environment:
      - GITLAB_URL=${GITLAB_URL}
      - GITLAB_TOKEN=${GITLAB_TOKEN}
      - GITLAB_PROJECT_ID=${GITLAB_PROJECT_ID}
      - GITLAB_BRANCH=${GITLAB_BRANCH:-main}
      - YAML_FILE_PATH=${YAML_FILE_PATH}
      - OBJECT_PATH=${OBJECT_PATH:-ip_lists.global.blocklist}
      - SERVER_PORT=8080
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 3s
      start_period: 5s
      retries: 3
```

### 4. Create Environment Example
**File:** `.env.example`

```bash
# GitLab Configuration
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your-personal-access-token-here
GITLAB_PROJECT_ID=12345678
GITLAB_BRANCH=main

# YAML Configuration
YAML_FILE_PATH=clusters/production/objects/blocklist.yaml
OBJECT_PATH=ip_lists.global.blocklist

# Server Configuration
SERVER_PORT=8080
```

### 5. Create Systemd Service
**File:** `deployments/webhook-service.service`

```ini
[Unit]
Description=SOAR Webhook Service
After=network.target

[Service]
Type=simple
User=webhook
Group=webhook
WorkingDirectory=/opt/webhook-soar
ExecStart=/opt/webhook-soar/webhook
Restart=always
RestartSec=10

# Environment variables
Environment="GITLAB_URL=https://gitlab.com"
EnvironmentFile=/etc/webhook-soar/config.env

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/tmp

[Install]
WantedBy=multi-user.target
```

### 6. Update README
**File:** `README.md`

Add sections:
- Architecture diagram
- Configuration reference
- Docker deployment
- Systemd deployment
- Testing instructions
- Troubleshooting

**Example deployment:**
```markdown
## Docker Deployment

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your GitLab credentials

3. Build and run:
   ```bash
   docker-compose up -d
   ```

4. Check logs:
   ```bash
   docker-compose logs -f webhook
   ```

## Testing

Send test webhook:
```bash
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d @../body.txt
```

## Systemd Deployment

1. Build binary:
   ```bash
   go build -o webhook ./cmd/webhook
   ```

2. Install:
   ```bash
   sudo cp webhook /opt/webhook-soar/
   sudo cp deployments/webhook-service.service /etc/systemd/system/
   sudo cp .env /etc/webhook-soar/config.env
   ```

3. Enable and start:
   ```bash
   sudo systemctl enable webhook-service
   sudo systemctl start webhook-service
   ```
```

### 7. Create Makefile (Optional)
**File:** `Makefile`

```makefile
.PHONY: build test lint docker-build docker-run clean

build:
	go build -o bin/webhook ./cmd/webhook

test:
	go test ./...

test-integration:
	INTEGRATION_TEST=true go test -tags=integration ./test/...

lint:
	golangci-lint run ./...

docker-build:
	docker build -t webhook-soar:latest .

docker-run:
	docker-compose up -d

clean:
	rm -rf bin/
	docker-compose down
```

## Todo List

- [ ] Write integration test with real GitLab
- [ ] Create multi-stage Dockerfile
- [ ] Create docker-compose.yml
- [ ] Create .env.example with all vars
- [ ] Create systemd service unit file
- [ ] Update README with deployment docs
- [ ] Create Makefile for common tasks
- [ ] Test Docker build and run
- [ ] Test systemd deployment
- [ ] Document troubleshooting steps
- [ ] Add architecture diagram to README

## Success Criteria

- Integration test passes with real GitLab
- Docker image builds successfully (<50MB)
- docker-compose starts service with health check
- Systemd service runs and restarts on failure
- README provides clear deployment instructions
- All environment variables documented

## Risk Assessment

**Low risk** - Standard deployment patterns.

**Mitigations:**
- Multi-stage build reduces image size
- Non-root user improves security
- Health checks enable monitoring
- Graceful shutdown prevents data loss

## Security Considerations

- Run as non-root user in container
- Mount secrets via environment/files (not in image)
- Use read-only root filesystem (optional)
- Enable TLS via reverse proxy (nginx/traefik)
- Rate limiting via proxy or middleware
- Monitor for suspicious webhook patterns

## Next Steps

After phase 05:
- Monitor MR creation in GitLab
- Consider: Auto-merge if tests pass
- Consider: Slack/email notifications on block
- Consider: Metrics/monitoring (Prometheus)
