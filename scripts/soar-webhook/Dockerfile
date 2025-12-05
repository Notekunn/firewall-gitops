# Build stage
FROM golang:1.23.1-alpine AS builder

# Install ca-certificates for SSL/TLS connections
RUN apk add --no-cache ca-certificates git

WORKDIR /app

# Copy go mod and sum files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o soar-webhook cmd/server/main.go

# Final stage
FROM alpine:latest

# Install ca-certificates for SSL/TLS and git for repository operations
RUN apk --no-cache add ca-certificates git

WORKDIR /root/

# Copy the binary from builder stage
COPY --from=builder /app/soar-webhook .

# Create non-root user
RUN addgroup -g 1001 -S soar && \
    adduser -u 1001 -S soar -G soar

# Change ownership of the binary
RUN chown soar:soar soar-webhook

# Switch to non-root user
USER soar

# Expose port
EXPOSE 8080

# Run the binary
CMD ["./soar-webhook"]