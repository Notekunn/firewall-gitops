.PHONY: help build test clean lint docker-build docker-run docker-stop fmt vet

# Default target
help:
	@echo "Available commands:"
	@echo "  build        - Build the application"
	@echo "  test         - Run tests"
	@echo "  test-cover   - Run tests with coverage"
	@echo "  clean        - Clean build artifacts"
	@echo "  lint         - Run linter"
	@echo "  fmt          - Format Go code"
	@echo "  vet          - Run go vet"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
	@echo "  docker-stop  - Stop and remove Docker container"

# Variables
APP_NAME := soar-webhook
DOCKER_IMAGE := $(APP_NAME):latest
DOCKER_CONTAINER := $(APP_NAME)-container

# Build the application
build:
	@echo "Building $(APP_NAME)..."
	go build -o bin/$(APP_NAME) cmd/server/main.go

# Run tests
test:
	@echo "Running tests..."
	go test ./...

# Run tests with coverage
test-cover:
	@echo "Running tests with coverage..."
	go test -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html

# Clean build artifacts
clean:
	@echo "Cleaning..."
	rm -rf bin/
	rm -f coverage.out coverage.html

# Run linter
lint:
	@echo "Running linter..."
	golangci-lint run

# Format Go code
fmt:
	@echo "Formatting code..."
	go fmt ./...

# Run go vet
vet:
	@echo "Running go vet..."
	go vet ./...

# Build Docker image
docker-build:
	@echo "Building Docker image..."
	docker build -t $(DOCKER_IMAGE) .

# Run Docker container
docker-run:
	@echo "Starting Docker container..."
	docker run -d --name $(DOCKER_CONTAINER) -p 8080:8080 $(DOCKER_IMAGE)

# Stop and remove Docker container
docker-stop:
	@echo "Stopping and removing Docker container..."
	docker stop $(DOCKER_CONTAINER) || true
	docker rm $(DOCKER_CONTAINER) || true

# Development server with hot reload (requires air)
dev:
	@echo "Starting development server with hot reload..."
	air -c .air.toml

# Install dependencies
deps:
	@echo "Installing dependencies..."
	go mod download
	go mod tidy

# Update dependencies
deps-update:
	@echo "Updating dependencies..."
	go get -u ./...
	go mod tidy

# Security check
security:
	@echo "Running security check..."
	gosec ./...

# All checks before commit
pre-commit: fmt vet lint test security
	@echo "All pre-commit checks passed!"