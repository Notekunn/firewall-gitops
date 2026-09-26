# Build stage
FROM golang:1.23-alpine AS builder

# Install git and ca-certificates for cloning repositories
RUN apk add --no-cache git ca-certificates

# Set the working directory
WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
# -w -s flags reduce binary size by removing debug information
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -a -installsuffix cgo -o webhook-soar ./cmd/webhook

# Final stage
FROM alpine:latest

# Install git and ca-certificates for runtime
RUN apk --no-cache add git ca-certificates tzdata

# Set timezone to UTC
ENV TZ=UTC

# Create non-root user
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Set the working directory
WORKDIR /app

# Copy binary from builder stage
COPY --from=builder /app/webhook-soar .

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Run the binary
CMD ["./webhook-soar"]