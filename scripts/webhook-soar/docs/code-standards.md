# SOAR Webhook Service: Code Standards

This document outlines the coding standards and conventions for the SOAR Webhook Service, developed in Go. Adhering to these standards ensures consistency, readability, maintainability, and facilitates collaborative development.

## 1. Go Coding Conventions

The project largely follows official Go best practices and `go fmt` standards.

-   **Formatting**: All Go code must be formatted using `go fmt`. This ensures consistent indentation (tabs), spacing, and brace placement.
-   **Naming Conventions**:
    *   **Packages**: Lowercase, single-word names (e.g., `config`, `repository`, `service`, `handler`). Avoid underscores or hyphens.
    *   **Variables**:
        *   Local variables: `camelCase`.
        *   Exported variables (start with uppercase): `CamelCase`.
        *   Acronyms (e.g., HTTP, API, ID, URL) should be all uppercase when used consecutively, and follow `CamelCase` otherwise (e.g., `gitlabURL`, `projectID`, `httpHandler`).
    *   **Functions**:
        *   Unexported functions: `camelCase`.
        *   Exported functions: `CamelCase`.
    *   **Structs**: `CamelCase` (e.g., `Config`, `GitLabRepository`, `YAMLProcessor`).
    *   **Interfaces**: `CamelCase`, often ending with `er` for single-method interfaces (e.g., `Reader`, `Writer`).
-   **Comments**:
    *   Use `//` for single-line comments.
    *   Document all exported types, functions, and methods with clear, concise comments. Start comments with the name of the documented entity.
    *   Explain complex logic or non-obvious design decisions.
-   **Modularity**: Keep functions and methods small and focused, adhering to the Single Responsibility Principle.

## 2. Error Handling Patterns

Error handling in Go is explicit and critical for robust applications.

-   **Return Errors Explicitly**: Functions that can fail must return an `error` as the last return value.
-   **Check Errors Immediately**: Always check returned errors immediately after a function call.
    ```go
    if err != nil {
        // Handle error, e.g., log, return, or wrap
        return fmt.Errorf("failed to do something: %w", err)
    }
    ```
-   **Error Wrapping**: Use `fmt.Errorf` with `%w` to wrap errors. This preserves the original error and provides a stack trace for debugging.
    ```go
    // In service layer
    if err := repo.CloneToTemp(); err != nil {
        return fmt.Errorf("could not clone repository: %w", err)
    }

    // In handler layer
    if err := processor.ProcessAlert(); err != nil {
        log.Printf("error processing alert: %v", err) // Log the wrapped error
        http.Error(w, "internal server error", http.StatusInternalServerError)
        return
    }
    ```
-   **Custom Error Types**: For specific error conditions, define custom error types (structs implementing the `error` interface) to allow for type-assertion and targeted error handling.
-   **Context**: Pass `context.Context` to functions that perform I/O operations or long-running tasks, especially across API boundaries, to allow for cancellation and deadlines.
-   **Panic/Recover**: Avoid `panic` for recoverable errors. Reserve `panic` for truly unrecoverable program states (e.g., critical initialization failures).

## 3. Testing Patterns

Comprehensive testing is crucial for reliability and confidence in deployments.

-   **Unit Tests**:
    *   Each package should have an associated `_test.go` file (e.g., `config_test.go`).
    *   Tests should cover individual functions and methods.
    *   Use `testify/assert` or standard library `testing` package for assertions.
    *   Mock external dependencies (e.g., Git operations, YAML file system) to isolate unit logic.
    *   Naming convention: `TestFunctionName`.
-   **Integration Tests**:
    *   Located in a dedicated `tests/integration/` directory.
    *   Test the interaction between multiple components or with external services (e.g., actual GitLab API calls).
    *   Require setting up a test environment (e.g., dummy GitLab project, local Git repository).
    *   May involve temporary files and directories, which must be cleaned up (`t.Cleanup()`).
-   **Test Coverage**: Aim for high test coverage (e.g., 70%+), with critical paths and error conditions thoroughly tested.
-   **Table-Driven Tests**: Use table-driven tests for multiple test cases of the same function.

## 4. Directory Structure Conventions

The project adheres to a standard Go project layout.

```
/scripts/webhook-soar/
├── cmd/
│   └── webhook/
│       └── main.go              // Application entry point
├── internal/                    // Private application code
│   ├── config/
│   │   ├── config.go            // Configuration loading/validation
│   │   └── config_test.go
│   ├── handler/
│   │   ├── webhook.go           // HTTP handlers
│   │   └── webhook_test.go
│   ├── repository/
│   │   ├── gitlab.go            // Git and GitLab API interactions
│   │   └── gitlab_test.go
│   ├── service/
│   │   ├── processor.go         // Core alert processing logic
│   │   ├── processor_test.go
│   │   ├── yaml_processor.go    // YAML manipulation
│   │   └── yaml_processor_test.go
├── tests/                       // Integration and end-to-end tests
│   └── integration/
│       └── webhook_test.go
├── go.mod                       // Go module definition
├── go.sum                       // Go module checksums
└── README.md                    // Project overview
```

-   **`cmd/`**: Contains the main applications. Each subdirectory corresponds to a standalone executable.
-   **`internal/`**: Contains private application and library code that cannot be imported by other repositories.
    *   Organized by functional domains (e.g., `config`, `handler`, `repository`, `service`).
-   **`tests/`**: Contains external test apps and additional test data.
-   **`go.mod`**, **`go.sum`**: Go module files for dependency management.

## 5. Logging

-   Use the standard library `log` package or a structured logging library (e.g., `sirupsen/logrus`, `uber-go/zap`) for outputting operational information, debugging details, and errors.
-   Ensure log messages are informative and include relevant context (e.g., request IDs, affected resources).
-   Avoid logging sensitive information directly.
