# Phase 01: Project Setup & Configuration

**Priority:** High
**Status:** ✅ **COMPLETE** (2025-12-09)
**Dependencies:** None

## Overview

Initialize Go project structure, define configuration schema, implement environment-based config loading following project code standards.

## Key Insights

- Project uses Go standards: slog for logging, structured error handling, table-driven tests
- Config via env vars (GITLAB_*, YAML_FILE_PATH, OBJECT_PATH)
- Follow code-standards.md: package layout, error wrapping, validation

## Requirements

### Functional
- Load config from environment variables
- Validate required fields (gitlab_token, project_id, etc.)
- Support defaults (branch=main, object_path=ip_lists.global.blocklist)

### Non-Functional
- Type-safe configuration struct
- Clear error messages for missing vars
- Testable config loader

## Architecture

```
scripts/webhook-soar/
├── cmd/
│   └── webhook/
│       └── main.go          # Entry point
├── internal/
│   ├── config/
│   │   ├── config.go        # Config struct & loader
│   │   └── config_test.go   # Unit tests
│   ├── handler/             # (Phase 04)
│   ├── service/             # (Phase 02-03)
│   └── repository/          # (Phase 02)
├── go.mod
├── go.sum
└── README.md
```

## Related Code Files

**Create:**
- `scripts/webhook-soar/cmd/webhook/main.go`
- `scripts/webhook-soar/internal/config/config.go`
- `scripts/webhook-soar/internal/config/config_test.go`
- `scripts/webhook-soar/go.mod`
- `scripts/webhook-soar/README.md`

## Implementation Steps

### 1. Initialize Go Module
```bash
cd scripts/webhook-soar
go mod init firewall-gitops/webhook-soar
```

### 2. Create Config Struct
**File:** `internal/config/config.go`

```go
package config

import (
    "fmt"
    "os"
)

type Config struct {
    GitLabURL       string
    GitLabToken     string
    GitLabProjectID string
    GitLabBranch    string
    YAMLFilePath    string
    ObjectPath      string
    ServerPort      string
}

func Load() (*Config, error) {
    cfg := &Config{
        GitLabURL:       getEnv("GITLAB_URL", "https://gitlab.com"),
        GitLabToken:     os.Getenv("GITLAB_TOKEN"),
        GitLabProjectID: os.Getenv("GITLAB_PROJECT_ID"),
        GitLabBranch:    getEnv("GITLAB_BRANCH", "main"),
        YAMLFilePath:    os.Getenv("YAML_FILE_PATH"),
        ObjectPath:      getEnv("OBJECT_PATH", "ip_lists.global.blocklist"),
        ServerPort:      getEnv("SERVER_PORT", "8080"),
    }

    if err := cfg.Validate(); err != nil {
        return nil, fmt.Errorf("config validation failed: %w", err)
    }

    return cfg, nil
}

func (c *Config) Validate() error {
    if c.GitLabToken == "" {
        return fmt.Errorf("missing required env var: GITLAB_TOKEN")
    }
    if c.GitLabProjectID == "" {
        return fmt.Errorf("missing required env var: GITLAB_PROJECT_ID")
    }
    if c.YAMLFilePath == "" {
        return fmt.Errorf("missing required env var: YAML_FILE_PATH")
    }
    return nil
}

func getEnv(key, fallback string) string {
    if v := os.Getenv(key); v != "" {
        return v
    }
    return fallback
}
```

### 3. Write Config Tests
**File:** `internal/config/config_test.go`

Table-driven tests covering:
- Success with all env vars
- Missing required vars (GITLAB_TOKEN, GITLAB_PROJECT_ID, YAML_FILE_PATH)
- Default values applied correctly

### 4. Create Main Entry Point
**File:** `cmd/webhook/main.go`

```go
package main

import (
    "log/slog"
    "os"

    "firewall-gitops/webhook-soar/internal/config"
)

func main() {
    // Setup structured logging
    logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
    slog.SetDefault(logger)

    // Load configuration
    cfg, err := config.Load()
    if err != nil {
        slog.Error("failed to load config", "error", err)
        os.Exit(1)
    }

    slog.Info("webhook service starting",
        "gitlab_url", cfg.GitLabURL,
        "project_id", cfg.GitLabProjectID,
        "branch", cfg.GitLabBranch,
        "port", cfg.ServerPort)

    // TODO: Initialize HTTP server (Phase 04)
}
```

### 5. Create README
**File:** `scripts/webhook-soar/README.md`

Document:
- Purpose of webhook service
- Environment variables
- Build/run instructions
- Example SOAR webhook payload

## Completed Tasks

- [x] Initialize Go module
- [x] Create config.go with Config struct
- [x] Implement Load() with env var reading
- [x] Implement Validate() for required fields
- [x] Write config_test.go with table-driven tests
- [x] Create main.go entry point
- [x] Write README with setup instructions
- [x] Run `go mod tidy`
- [x] Run `go fmt ./...`
- [x] Verify tests pass: `go test ./...`

## Success Criteria

- `go mod init` creates valid go.mod
- Config loads from env vars with defaults
- Validation catches missing required vars
- All tests pass
- Code follows Go standards (fmt, lint)

## Risk Assessment

**Low risk** - Standard Go project setup.

**Mitigations:**
- Use proven patterns from code-standards.md
- Keep dependencies minimal (stdlib only for now)

## Security Considerations

- Never log GITLAB_TOKEN value
- Validate env var format (prevent injection)
- Use structured logging for auditability

## Next Steps

After phase 01:
- Phase 02: Implement GitLab API integration
- Need GitLab SDK dependency: `github.com/xanzy/go-gitlab`
