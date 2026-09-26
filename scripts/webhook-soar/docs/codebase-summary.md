# SOAR Webhook Service: Codebase Summary

The SOAR webhook service automates firewall blocklist updates by processing incoming security alerts, updating YAML configuration files in a GitLab repository, and creating merge requests.

## Package Structure and Responsibilities

### 1. `cmd/webhook/main.go`
- **Responsibility**: Application entry point.
- **Description**: Initializes configuration, sets up core components (GitLab repository client, YAML processor, alert processor, HTTP handler), starts the HTTP server, and manages graceful shutdown.

### 2. `internal/config/config.go`
- **Responsibility**: Configuration management and validation.
- **Description**: Defines the `Config` struct (containing GitLab URL, token, project ID, branch, YAML file path, object path, server port) and provides `Load()` and `Validate()` functions to load settings from environment variables and ensure their correctness.

### 3. `internal/repository/gitlab.go`
- **Responsibility**: Git and GitLab API operations.
- **Description**: Implements `GitLabRepository` to encapsulate functionalities such as cloning repositories to a temporary location (`CloneToTemp`), creating new Git branches (`CreateBranch`), committing changes (`CommitChanges`), pushing branches to remote (`PushBranch`), creating GitLab Merge Requests (`CreateMergeRequest`), and cleaning up temporary directories (`Cleanup`).

### 4. `internal/service/processor.go`
- **Responsibility**: End-to-end alert processing workflow.
- **Description**: Defines the `Processor` struct that orchestrates the overall workflow by utilizing `GitLabRepository` and `YAMLProcessor`. The `ProcessAlert()` function executes the main workflow, including `ValidateTicketID()`.

### 5. `internal/service/yaml_processor.go`
- **Responsibility**: YAML file manipulation.
- **Description**: Manages updates to YAML files. The `YAMLProcessor` struct, configured with a file path and an object path, offers an `AddIP()` method to append IP addresses to a nested YAML list while preserving file structure, comments, and indentation.

### 6. `internal/handler/webhook.go`
- **Responsibility**: HTTP request handling.
- **Description**: Contains the `WebhookHandler` struct which defines HTTP endpoints. `HandleWebhook()` processes incoming SOAR alerts, and `HandleHealth()` provides a health check endpoint. It also defines `SOARWebhookRequest` and `WebhookResponse` structs for request/response payloads.

## Key Types and Interfaces

-   `Config`: Stores all application configuration.
-   `GitLabRepository`: Interface/struct for Git and GitLab operations.
-   `YAMLProcessor`: Interface/struct for YAML file modifications.
-   `Processor`: Orchestrates the alert processing flow.
-   `SOARWebhookRequest`, `WebhookResponse`: Data structures for HTTP communication.

## Dependency Flow Diagram (Text-based)

```
+-------------------+       +-------------------+       +-------------------+
| cmd/webhook/main  |       | internal/config   |       | internal/repository |
| (Application Entry)|       | (Configuration)   |       | (GitLab Operations) |
+---------+---------+       +---------+---------+       +---------+---------+
          |                             ^                           ^
          |                             |                           |
          |           Loads             |           Uses            |
          +-----------------------------+                           |
          |                                                         |
          |                             +---------------------------+
          | Uses                        |
          |                             |
          v                             v
+---------+---------+       +---------+---------+       +---------+---------+
| internal/handler  | <---->| internal/service/ | <---->| internal/service/ |
| (HTTP Handlers)   |       |   processor       |       |  yaml_processor   |
+-------------------+       | (Alert Processing)|       | (YAML Processing) |
                            +-------------------+       +-------------------+
```

## Deployment Architecture

-   **Dockerfile**: Multi-stage build (golang:1.23-alpine → alpine:latest). Runs as non-root user (UID 1001). Includes a healthcheck on `/health`.
-   **Helm Chart**: Configured for 2 replicas, exposes a `ClusterIP` service. Applies resource limits (100m CPU, 128Mi memory) and security context (non-root, drops ALL capabilities) for pods.
-   **Environment Variables**: The service relies heavily on environment variables for configuration: `GITLAB_URL`, `GITLAB_TOKEN`, `GITLAB_PROJECT_ID`, `GITLAB_BRANCH`, `YAML_FILE_PATH`, `OBJECT_PATH`, `SERVER_PORT`.

## Test Coverage

-   **Overall**: Approximately 70% test coverage.
-   **Unit Tests**: Present for all individual packages.
-   **Integration Tests**: Located in `tests/integration/webhook_test.go`.
-   **Missing Tests**: Specifically noted for `CloneToTemp` and `PushBranch` functions within `internal/repository/gitlab.go`.

## Known Issues (from code review)

-   **GitLab Token Security**: Potential exposure due to embedding in URLs.
-   **Input Validation for Git Commands**: Insufficient validation could lead to command injection vulnerabilities.
-   **Resource Leaks**: Possible issues with temporary directories not being cleaned up effectively.
