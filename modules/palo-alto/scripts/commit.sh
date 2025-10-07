#!/bin/sh
# PAN-OS commit script
# Commits pending changes to PAN-OS firewall via latest XML API
#
# This script uses partial commit to commit only the config user's changes,
# which is the recommended approach for automation to avoid committing
# unintended changes from other administrators.
#
# Environment Variables:
#   PANOS_HOSTNAME - Firewall hostname or IP (required)
#   PANOS_API_KEY - API key for authentication (required if no username/password)
#   PANOS_USERNAME - Username for authentication (required if no API key)
#   PANOS_PASSWORD - Password for authentication (required with username)
#   PANOS_PROTOCOL - Protocol (http/https), default: https
#   PANOS_SKIP_VERIFY_CERTIFICATE - Skip SSL verification, default: true
#   COMMIT_DESCRIPTION - Commit description, default: "Committed by Terraform"
#   COMMIT_ADMIN - Admin user whose changes to commit, default: PANOS_USERNAME

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[PAN-OS COMMIT]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Validate required variables
if [ -z "$PANOS_HOSTNAME" ]; then
    error "PANOS_HOSTNAME is required"
    exit 1
fi

# Check if we have credentials
if [ -z "$PANOS_API_KEY" ] && [ -z "$PANOS_USERNAME" ]; then
    error "Either PANOS_API_KEY or PANOS_USERNAME/PANOS_PASSWORD is required"
    exit 1
fi

# Set defaults
PROTOCOL="${PANOS_PROTOCOL:-https}"
SKIP_VERIFY="${PANOS_SKIP_VERIFY_CERTIFICATE:-true}"
DESCRIPTION="${COMMIT_DESCRIPTION:-Committed by Terraform}"

# Configure curl options
CURL_OPTS=""
if [ "$SKIP_VERIFY" = "true" ]; then
    CURL_OPTS="-k"
fi

BASE_URL="${PROTOCOL}://${PANOS_HOSTNAME}/api"

log "Connecting to PAN-OS: ${PANOS_HOSTNAME}"

# Get API key if not provided
if [ -z "$PANOS_API_KEY" ]; then
    log "Generating API key..."
    if [ -z "$PANOS_PASSWORD" ]; then
        error "PANOS_PASSWORD is required when PANOS_API_KEY is not provided"
        exit 1
    fi

    API_KEY_RESPONSE=$(curl -s $CURL_OPTS -X GET "${BASE_URL}/?type=keygen&user=${PANOS_USERNAME}&password=${PANOS_PASSWORD}")
    PANOS_API_KEY=$(echo "$API_KEY_RESPONSE" | grep -oPm1 "(?<=<key>)[^<]+")

    if [ -z "$PANOS_API_KEY" ]; then
        error "Failed to generate API key"
        error "Response: $API_KEY_RESPONSE"
        exit 1
    fi
    success "API key generated successfully"
fi

# Build commit command XML using latest PAN-OS API syntax
# Use partial commit to commit only specific admin's changes
COMMIT_ADMIN="${COMMIT_ADMIN:-$PANOS_USERNAME}"

if [ -n "$COMMIT_ADMIN" ]; then
    # Partial commit for specific admin user (recommended for automation)
    COMMIT_CMD="<commit><partial><description>${DESCRIPTION}</description><admin><member>${COMMIT_ADMIN}</member></admin></partial></commit>"
    log "Committing changes for admin: ${COMMIT_ADMIN}"
else
    # Full commit (commits all pending changes from all admins)
    COMMIT_CMD="<commit><description>${DESCRIPTION}</description></commit>"
    log "Committing all pending changes (full commit)"
fi

log "Committing changes to PAN-OS..."
log "Description: ${DESCRIPTION}"

# URL encode the commit command
COMMIT_CMD_ENCODED=$(echo -n "$COMMIT_CMD" | jq -sRr @uri)

# Execute commit using latest PAN-OS XML API
COMMIT_RESPONSE=$(curl -s $CURL_OPTS -X POST "${BASE_URL}/" \
    -d "type=commit" \
    -d "cmd=${COMMIT_CMD_ENCODED}" \
    -d "key=${PANOS_API_KEY}")

# Check if commit was successful
if echo "$COMMIT_RESPONSE" | grep -q "<status>success</status>"; then
    JOB_ID=$(echo "$COMMIT_RESPONSE" | grep -oPm1 "(?<=<job>)[^<]+")
    success "Commit initiated successfully (Job ID: ${JOB_ID})"

    # Wait for commit to complete
    log "Waiting for commit to complete..."
    MAX_WAIT=300  # 5 minutes
    WAIT_TIME=0
    SLEEP_INTERVAL=5

    while [ $WAIT_TIME -lt $MAX_WAIT ]; do
        sleep $SLEEP_INTERVAL
        WAIT_TIME=$((WAIT_TIME + SLEEP_INTERVAL))

        JOB_STATUS=$(curl -s $CURL_OPTS -X GET "${BASE_URL}/?type=op&cmd=<show><jobs><id>${JOB_ID}</id></jobs></show>&key=${PANOS_API_KEY}")

        STATUS=$(echo "$JOB_STATUS" | grep -oPm1 "(?<=<status>)[^<]+")
        RESULT=$(echo "$JOB_STATUS" | grep -oPm1 "(?<=<result>)[^<]+")
        PROGRESS=$(echo "$JOB_STATUS" | grep -oPm1 "(?<=<progress>)[^<]+")

        log "Commit progress: ${PROGRESS}% - Status: ${STATUS}"

        if [ "$STATUS" = "FIN" ]; then
            if [ "$RESULT" = "OK" ]; then
                success "Commit completed successfully!"
                exit 0
            else
                error "Commit failed with result: ${RESULT}"
                error "Job status response: ${JOB_STATUS}"
                exit 1
            fi
        fi
    done

    warning "Commit job is still running after ${MAX_WAIT} seconds"
    warning "Job ID: ${JOB_ID} - You may want to check the firewall manually"
    exit 0
else
    error "Failed to initiate commit"
    error "Response: ${COMMIT_RESPONSE}"
    exit 1
fi
