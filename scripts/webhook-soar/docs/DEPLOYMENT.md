# SOAR Webhook Service - Deployment Guide

## Overview

The SOAR Webhook Service is a Go application that receives security alerts from SOAR platforms, validates IP addresses, and automatically creates GitLab merge requests to block malicious IPs in firewall configurations.

## Prerequisites

### GitLab Requirements

1. **GitLab Project**: A GitLab project with firewall configuration YAML files
2. **Personal Access Token**: GitLab token with `api` scope
3. **Project ID**: Numeric GitLab project ID (found in project settings)
4. **Branch**: Target branch for merge requests (typically `main` or `master`)

### YAML Structure

The service expects YAML files with the following structure:

```yaml
# clusters/your-cluster/objects.yaml
addresses:
  - name: existing-ip
    ip_netmask: 192.168.1.100/32
    description: "Existing blocked IP"
```

The `ObjectPath` configuration specifies the YAML path to the addresses list (e.g., `addresses`).

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITLAB_URL` | Yes | - | GitLab server URL (e.g., `https://gitlab.com`) |
| `GITLAB_TOKEN` | Yes | - | GitLab personal access token with `api` scope |
| `GITLAB_PROJECT_ID` | Yes | - | Numeric ID of GitLab project |
| `GITLAB_BRANCH` | No | `main` | Target branch for merge requests |
| `YAML_FILE_PATH` | Yes | - | Relative path to YAML file in repo (e.g., `clusters/prod/objects.yaml`) |
| `OBJECT_PATH` | Yes | - | YAML path to addresses list (e.g., `addresses`) |
| `SERVER_PORT` | No | `8080` | HTTP server port |

### Example Configuration

```bash
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
export GITLAB_PROJECT_ID="123"
export GITLAB_BRANCH="main"
export YAML_FILE_PATH="clusters/prod/objects.yaml"
export OBJECT_PATH="addresses"
export SERVER_PORT="8080"
```

## Deployment Options

### 1. Direct Binary Deployment

#### Build

```bash
cd scripts/webhook-soar
go build -o webhook-soar ./cmd/webhook
```

#### Run

```bash
./webhook-soar
```

### 2. Docker Deployment

#### Build Image

```bash
cd scripts/webhook-soar
docker build -t soar-webhook-service:latest .
```

#### Run Container

```bash
docker run -d \
  --name soar-webhook \
  -p 8080:8080 \
  -e GITLAB_URL="https://gitlab.example.com" \
  -e GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx" \
  -e GITLAB_PROJECT_ID="123" \
  -e YAML_FILE_PATH="clusters/prod/objects.yaml" \
  -e OBJECT_PATH="addresses" \
  soar-webhook-service:latest
```

#### Docker Compose

Create `docker-compose.yml`:

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
      - GITLAB_BRANCH=${GITLAB_BRANCH:-main}
      - YAML_FILE_PATH=${YAML_FILE_PATH}
      - OBJECT_PATH=${OBJECT_PATH}
      - SERVER_PORT=${SERVER_PORT:-8080}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

Run with:

```bash
docker-compose up -d
```

### 3. Kubernetes Deployment

#### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: soar-webhook
```

#### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: soar-webhook-config
  namespace: soar-webhook
data:
  GITLAB_URL: "https://gitlab.example.com"
  GITLAB_PROJECT_ID: "123"
  GITLAB_BRANCH: "main"
  YAML_FILE_PATH: "clusters/prod/objects.yaml"
  OBJECT_PATH: "addresses"
  SERVER_PORT: "8080"
```

#### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: soar-webhook-secret
  namespace: soar-webhook
type: Opaque
data:
  GITLAB_TOKEN: Z2xwYXQteHh4eHh4eHh4eHh4eHh4eHh4eHg=  # base64 encoded
```

#### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: soar-webhook
  namespace: soar-webhook
spec:
  replicas: 2
  selector:
    matchLabels:
      app: soar-webhook
  template:
    metadata:
      labels:
        app: soar-webhook
    spec:
      containers:
      - name: soar-webhook
        image: soar-webhook-service:latest
        ports:
        - containerPort: 8080
        envFrom:
        - configMapRef:
            name: soar-webhook-config
        - secretRef:
            name: soar-webhook-secret
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"
```

#### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: soar-webhook-service
  namespace: soar-webhook
spec:
  selector:
    app: soar-webhook
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: ClusterIP
```

#### Ingress (Optional)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: soar-webhook-ingress
  namespace: soar-webhook
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: webhook.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: soar-webhook-service
            port:
              number: 80
```

## API Usage

### Webhook Endpoint

**POST** `/webhook`

#### Request Body

```json
{
  "ticket_id": "TICKET-123",
  "source_system": "Splunk SOAR",
  "attacker": {
    "type": "ip_v4",
    "value": "10.0.0.100"
  },
  "reason": "Malicious activity detected"
}
```

#### Response

Success (200):
```json
{
  "success": true,
  "message": "IP added to blocklist",
  "merge_request": 456
}
```

Error (4xx/5xx):
```json
{
  "success": false,
  "message": "error description"
}
```

### Health Check

**GET** `/health`

#### Response
```json
{
  "status": "healthy"
}
```

## Testing

### Unit Tests

```bash
go test ./...
```

### Integration Tests

Set environment variables and run:

```bash
export INTEGRATION_TESTS=true
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="your-token"
export GITLAB_PROJECT_ID="123"

go test -tags=integration ./tests/integration/...
```

### Manual Testing

```bash
# Test webhook endpoint
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TEST-001",
    "attacker": {
      "type": "ip_v4",
      "value": "10.0.0.100"
    },
    "reason": "Test request"
  }'

# Test health endpoint
curl http://localhost:8080/health
```

## Monitoring

### Logs

The application uses structured JSON logging via `slog`. Example log entry:

```json
{
  "time": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "msg": "received webhook request",
  "request_id": "1234567890",
  "method": "POST",
  "remote_addr": "10.0.0.1:12345"
}
```

### Metrics

Consider adding Prometheus metrics for monitoring:

- Request count by status code
- Request duration histogram
- Active goroutines count
- GitLab operation durations

### Alerting

Set up alerts for:

- High error rate (>5%)
- Slow requests (>30s)
- Service down (health check failures)
- GitLab API failures

## Security Considerations

1. **Token Security**: Never expose GitLab tokens in logs or code
2. **Network Access**: Restrict inbound traffic to SOAR platforms
3. **Input Validation**: Service validates all input before processing
4. **TLS**: Use TLS in production for all communications
5. **Rate Limiting**: Consider adding rate limiting for abuse prevention

## Troubleshooting

### Common Issues

1. **"clone failed" error**
   - Check GitLab URL and token
   - Verify project ID
   - Ensure token has `api` scope

2. **"yaml update failed" error**
   - Verify YAML_FILE_PATH is correct
   - Check OBJECT_PATH matches YAML structure
   - Ensure file exists in repository

3. **"create MR failed" error**
   - Check branch permissions
   - Verify merge request settings
   - Ensure target branch exists

### Debug Mode

Enable debug logging by setting log level:

```bash
export LOG_LEVEL=debug
./webhook-soar
```

## Maintenance

### Updates

1. Update dependencies: `go get -u ./...`
2. Rebuild: `go build -o webhook-soar ./cmd/webhook`
3. Redeploy with zero downtime

### Backup

Regular backups of:
- GitLab configurations
- Environment variables
- Deployment manifests

## Scaling

### Horizontal Scaling

- Deploy multiple instances behind a load balancer
- Each instance handles requests independently
- GitLab operations are atomic

### Performance Tuning

- Monitor memory usage (temporary git clones)
- Adjust timeouts for large repositories
- Consider persistent storage for git operations