# SOAR Webhook Service

Lightweight Go webhook service for integrating SOAR (Security Orchestration, Automation and Response) alerts with firewall GitOps workflow.

## Purpose

Receives security alerts from SOAR platforms via HTTP webhooks, extracts attacker IP addresses, and automatically updates YAML firewall blocklists by creating merge requests in GitLab.

## Architecture

```
SOAR Alert → HTTP POST → Webhook Handler → Git Pull → YAML Update → Git Commit → Create MR
```

## Environment Variables

### Required
- `GITLAB_TOKEN` - Personal access token with `api` scope
- `GITLAB_PROJECT_ID` - GitLab project ID (numeric)
- `YAML_FILE_PATH` - Path to YAML file in repository (e.g., `clusters/production/objects.yaml`)

### Optional
- `GITLAB_URL` - GitLab instance URL (default: `https://gitlab.com`)
- `GITLAB_BRANCH` - Target branch for merge requests (default: `main`)
- `OBJECT_PATH` - YAML path to IP blocklist (default: `ip_lists.global.blocklist`)
- `SERVER_PORT` - HTTP server port (default: `8080`)

## Build and Run

```bash
# Build
cd scripts/webhook-soar
go build -o webhook ./cmd/webhook

# Run with environment variables
export GITLAB_TOKEN="your-token"
export GITLAB_PROJECT_ID="123"
export YAML_FILE_PATH="clusters/production/objects.yaml"
./webhook
```

## Example SOAR Webhook Payload

```json
{
  "alert": {
    "title": "Brute Force Attack Detected",
    "severity": "high",
    "source_ip": "192.0.2.100",
    "timestamp": "2025-01-09T10:30:00Z",
    "description": "Multiple failed login attempts from suspicious IP"
  }
}
```

## YAML Processor

Phase 03 introduced a powerful YAML processor for manipulating firewall blocklists:

### Features
- **Nested Object Navigation** - Support for dot-separated paths (e.g., `ip_lists.global.blocklist`)
- **IP Deduplication** - Intelligent duplicate prevention with normalization
- **Comment Preservation** - Maintains YAML comments during updates
- **Format Preservation** - 2-space indentation as per project standards
- **CIDR Handling** - Automatically adds `/32` suffix to bare IP addresses
- **Validation** - IPv4/IPv6 address format validation

### Usage Example
```go
import "firewall-gitops/webhook-soar/internal/service"

// Create processor
processor := service.NewYAMLProcessor("clusters/production/objects.yaml", "ip_lists.global.blocklist")

// Add IP to blocklist
added, err := processor.AddIP("/tmp/repo", "10.0.0.100")
if err != nil {
    log.Fatal(err)
}
if added {
    log.Println("IP added successfully")
}
```

### Testing
```bash
# Run all tests
go test ./...

# Run tests with coverage
go test -cover ./...

# Run specific package tests
go test ./internal/service/...
```

## Development

```bash
# Format code
go fmt ./...

# Tidy dependencies
go mod tidy
```

## Project Structure

```
scripts/webhook-soar/
├── cmd/
│   └── webhook/
│       └── main.go          # Entry point
├── internal/
│   ├── config/
│   │   ├── config.go        # Configuration struct and loader
│   │   └── config_test.go   # Unit tests
│   ├── handler/             # HTTP webhook handlers (Phase 04)
│   ├── service/
│   │   ├── yaml_processor.go        # YAML manipulation service (Phase 03)
│   │   └── yaml_processor_test.go   # Comprehensive test suite
│   └── repository/
│       ├── gitlab.go        # GitLab API client (Phase 02)
│       └── gitlab_test.go   # Unit tests
├── go.mod
├── go.sum
└── README.md
```