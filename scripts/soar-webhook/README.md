# SOAR Webhook Service

## Overview

The SOAR (Security Orchestration, Automation and Response) Webhook Service is a Go-based microservice that integrates with the Firewall GitOps system to enable automated security responses and orchestration workflows. This service acts as a webhook receiver that processes security events, triggers automated responses, and updates firewall configurations through the GitOps pipeline.

## Architecture

```
┌─────────────────┐    HTTP     ┌─────────────────┐    Git    ┌──────────────────┐
│   SOAR Platform │ ────────> │  SOAR Webhook   │ ──────> │ Firewall GitOps  │
│                 │  Webhook   │     Service     │  Push   │   Repository    │
└─────────────────┘            └─────────────────┘          └──────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │  GitLab API     │
                               │  (Triggers CI)  │
                               └─────────────────┘
```

## Features

### Phase 01: Project Setup & Configuration (Current)

- ✅ **Configuration Management**: Environment-based configuration with validation
- ✅ **Structured Logging**: JSON-formatted logs with multiple levels
- ✅ **Modular Architecture**: Clean separation of concerns with internal packages
- ✅ **Unit Testing**: Comprehensive test coverage for core components

### Planned Features

- 🚧 **Webhook Endpoints**: REST API endpoints for receiving security events
- 🚧 **Event Processing**: Parse and validate incoming webhook payloads
- 🚧 **Git Integration**: Clone, modify, and push firewall rule changes
- 🚧 **Security Response**: Automated rule updates based on threat intelligence
- 🚧 **Rate Limiting**: Prevent abuse and manage request throughput
- 🚧 **Authentication**: Verify webhook signature authenticity

## Project Structure

```
soar-webhook/
├── cmd/
│   └── server/
│       ├── main.go          # Application entry point
│       └── main_test.go     # Main function tests
├── internal/
│   └── config/
│       ├── config.go        # Configuration management
│       └── config_test.go   # Configuration tests
├── go.mod                   # Go module definition
└── README.md               # This file
```

## Quick Start

### Prerequisites

- Go 1.23.1 or later
- GitLab instance with API access
- Git repository with firewall configurations

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/your-org/firewall-gitops.git
cd firewall-gitops/scripts/soar-webhook
```

2. **Install dependencies**:
```bash
go mod download
```

3. **Set environment variables**:
```bash
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="your-access-token"
export GITLAB_PROJECT_ID="123"
export REPO_CLONE_URL="https://gitlab.example.com/your-org/firewall-configs.git"
export WEBHOOK_SECRET="your-webhook-secret"
export SERVER_PORT="8080"  # Optional, defaults to 8080
export TARGET_CLUSTER="production"  # Optional, defaults to f5-example
```

4. **Run the service**:
```bash
go run cmd/server/main.go
```

### Docker Deployment

1. **Build the image**:
```bash
docker build -t soar-webhook .
```

2. **Run with Docker**:
```bash
docker run -p 8080:8080 \
  -e GITLAB_URL="https://gitlab.example.com" \
  -e GITLAB_TOKEN="your-token" \
  -e GITLAB_PROJECT_ID="123" \
  -e REPO_CLONE_URL="https://gitlab.example.com/repo.git" \
  -e WEBHOOK_SECRET="secret" \
  soar-webhook
```

### Docker Compose

```yaml
version: '3.8'
services:
  soar-webhook:
    build: .
    ports:
      - "8080:8080"
    environment:
      - GITLAB_URL=${GITLAB_URL}
      - GITLAB_TOKEN=${GITLAB_TOKEN}
      - GITLAB_PROJECT_ID=${GITLAB_PROJECT_ID}
      - REPO_CLONE_URL=${REPO_CLONE_URL}
      - WEBHOOK_SECRET=${WEBHOOK_SECRET}
      - TARGET_CLUSTER=${TARGET_CLUSTER:-f5-example}
      - SERVER_PORT=${SERVER_PORT:-8080}
    restart: unless-stopped
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITLAB_URL` | Yes | - | GitLab instance URL (e.g., `https://gitlab.com`) |
| `GITLAB_TOKEN` | Yes | - | GitLab personal access token with `api` scope |
| `GITLAB_PROJECT_ID` | Yes | - | GitLab project ID (numeric string) |
| `REPO_CLONE_URL` | Yes | - | HTTPS URL to clone the firewall config repository |
| `WEBHOOK_SECRET` | Yes | - | Secret for validating webhook signatures |
| `TARGET_CLUSTER` | No | `f5-example` | Default cluster name for rule updates |
| `SERVER_PORT` | No | `8080` | Port for the HTTP server to listen on |

### GitLab Token Setup

1. Go to GitLab → User Settings → Access Tokens
2. Create a new personal access token
3. Grant the following scopes:
   - `api` - Full API access
   - `write_repository` - Push to repository
4. Securely store the token for use with the service

## Development

### Running Tests

```bash
# Run all tests
go test ./...

# Run tests with coverage
go test -cover ./...

# Run tests with coverage report
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

### Code Quality

```bash
# Format code
go fmt ./...

# Run linter
golangci-lint run

# Run security check
gosec ./...
```

### Adding New Features

1. Create a new package under `internal/` for your feature
2. Follow the existing code structure and naming conventions
3. Write comprehensive unit tests
4. Update documentation as needed

## API Reference

### Health Check (Planned)

```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-05T10:00:00Z"
}
```

### Webhook Endpoint (Planned)

```http
POST /webhook/security-event
Content-Type: application/json
X-Webhook-Signature: sha256=<signature>
```

Request body varies by SOAR platform. See documentation for specific integrations.

## Logging

The service uses structured JSON logging for better observability:

```json
{
  "time": "2025-01-05T10:00:00Z",
  "level": "INFO",
  "msg": "starting server",
  "port": "8080"
}
```

Log levels:
- `DEBUG` - Detailed debugging information
- `INFO` - General information messages
- `WARN` - Warning messages for potential issues
- `ERROR` - Error messages for failures

## Security Considerations

### Webhook Security

- **Signature Validation**: All incoming webhooks are validated using `WEBHOOK_SECRET`
- **Rate Limiting**: Prevents abuse by limiting request frequency
- **TLS Encryption**: Always use HTTPS in production

### GitLab Security

- **Token Scopes**: Use minimum required scopes for GitLab token
- **Token Rotation**: Regularly rotate GitLab access tokens
- **IP Whitelisting**: Restrict GitLab API access to known IPs

### Operational Security

- **Environment Variables**: Store secrets as environment variables, never in code
- **Container Security**: Run as non-root user in production containers
- **Network Isolation**: Deploy in dedicated network segment

## Troubleshooting

### Common Issues

1. **Configuration Validation Errors**:
   ```
   Error: missing required env var: GITLAB_TOKEN
   ```
   Solution: Ensure all required environment variables are set

2. **GitLab API Authentication**:
   ```
   Error: 401 Unauthorized
   ```
   Solution: Verify GitLab token has correct scopes and is not expired

3. **Repository Clone Issues**:
   ```
   Error: repository not found
   ```
   Solution: Check `REPO_CLONE_URL` and ensure GitLab token has repository access

### Debug Mode

Enable debug logging by setting the log level:
```go
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelDebug,
}))
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Submit a merge request

### Development Workflow

- Follow Conventional Commits specification
- Write unit tests for new functionality
- Update documentation for API changes
- Ensure all tests pass before submitting MR

## Roadmap

### Phase 02: Web API Implementation (Next)
- HTTP server setup with routing
- Webhook endpoint implementation
- Request validation and parsing
- Response formatting

### Phase 03: Git Integration
- Git repository cloning and management
- Branch creation and management
- File modification and commit operations
- Push changes and trigger CI/CD

### Phase 04: Event Processing
- Event parsing and validation
- Threat intelligence integration
- Automated rule generation
- Security policy enforcement

### Phase 05: Advanced Features
- Multi-platform SOAR integration
- Custom workflow engine
- Advanced analytics and reporting
- Performance optimizations

## License

This project is part of the Firewall GitOps system. See the main project license for details.

## Support

For support and questions:
- Create an issue in the GitLab repository
- Join our Slack channel
- Check the documentation at `/docs`