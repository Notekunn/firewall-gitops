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

ensure_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "Required command not found: $1"
        exit 1
    fi
}

normalize_xml() {
    printf '%s' "$1" | tr -d '\n\r'
}

extract_response_attr() {
    local xml="$1"
    local attr="$2"
    printf '%s\n' "$xml" | sed -n "s/.*<response[^>]*${attr}=\"\\([^\"]*\\)\".*/\\1/p"
}

extract_first_tag() {
    local xml="$1"
    local tag="$2"
    printf '%s\n' "$xml" | sed -n "s/.*<${tag}>\\([^<]*\\)<\\/${tag}>.*/\\1/p"
}

extract_job_block() {
    local xml="$1"
    printf '%s\n' "$xml" | sed -n 's/.*<job>\(.*\)<\/job>.*/\1/p'
}

extract_lines() {
    local xml="$1"
    printf '%s\n' "$xml" | awk -F'<line>|</line>' '{for (i=2; i<NF; i+=2) if ($i != "") print $i}'
}

extract_msg_text() {
    local xml="$1"
    local msg
    msg=$(printf '%s\n' "$xml" | sed -n 's/.*<msg>\(.*\)<\/msg>.*/\1/p')
    if [ -n "$msg" ]; then
        printf '%s\n' "$msg" | sed 's/<[^>]*>//g'
    fi
}

join_with_semicolons() {
    local first=1
    local line
    local output=""
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        if [ $first -eq 1 ]; then
            output="$line"
            first=0
        else
            output="${output}; ${line}"
        fi
    done
    printf '%s' "$output"
}

describe_response_code() {
    case "$1" in
        1|20) echo "Command succeeded" ;;
        19) echo "Commit job enqueued" ;;
        13) echo "No changes to commit" ;;
        2|3|4) echo "Internal error" ;;
        5) echo "Authentication failed" ;;
        6) echo "Invalid XPath or element" ;;
        7) echo "Object not present" ;;
        8) echo "Object not unique" ;;
        9) echo "Referenced object not present" ;;
        10) echo "Invalid object state" ;;
        11) echo "Malformed request" ;;
        12) echo "Device not ready" ;;
        14) echo "Commit or configuration lock active" ;;
        15) echo "Validation error" ;;
        16) echo "Job ID not found" ;;
        17) echo "Command not permitted" ;;
        18) echo "Client cancelled request" ;;
        *) echo "" ;;
    esac
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

    API_KEY_RESPONSE=$(wget -q ${CURL_OPTS} -O - "${BASE_URL}/?type=keygen&user=${PANOS_USERNAME}&password=${PANOS_PASSWORD}")
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

# Require external tools
ensure_command wget

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
COMMIT_RESPONSE=$(wget -q ${CURL_OPTS} --method=POST --body-data="type=commit&cmd=${COMMIT_CMD_ENCODED}&key=${PANOS_API_KEY}" -O - "${BASE_URL}/")

# Parse commit response
COMMIT_XML=$(normalize_xml "$COMMIT_RESPONSE")

if [ -z "$COMMIT_XML" ]; then
    error "Empty response from PAN-OS commit API"
    exit 1
fi

RESPONSE_STATUS=$(extract_response_attr "$COMMIT_XML" "status")
RESPONSE_CODE=$(extract_response_attr "$COMMIT_XML" "code")
RESPONSE_CODE_DESC=$(describe_response_code "$RESPONSE_CODE")
JOB_ID=$(extract_first_tag "$COMMIT_XML" "job")
COMMIT_LINES=$(extract_lines "$COMMIT_XML")
COMMIT_MESSAGE=$(printf '%s\n' "$COMMIT_LINES" | head -n1)
RAW_MESSAGE=$(extract_msg_text "$COMMIT_XML")

if [ -z "$COMMIT_MESSAGE" ] && [ -n "$RAW_MESSAGE" ]; then
    COMMIT_MESSAGE="$RAW_MESSAGE"
fi

RESPONSE_LINES="$COMMIT_LINES"
if [ -z "$RESPONSE_LINES" ] && [ -n "$RAW_MESSAGE" ]; then
    RESPONSE_LINES="$RAW_MESSAGE"
fi

SHOULD_MONITOR="false"

case "$RESPONSE_STATUS" in
    success)
        if [ "$RESPONSE_CODE" = "13" ]; then
            MESSAGE="${COMMIT_MESSAGE:-No changes detected; commit skipped by PAN-OS}"
            success "${MESSAGE}"
            if [ -n "$RESPONSE_CODE_DESC" ]; then
                log "PAN-OS API code ${RESPONSE_CODE}: ${RESPONSE_CODE_DESC}"
            elif [ -n "$RESPONSE_CODE" ]; then
                log "PAN-OS API code: ${RESPONSE_CODE}"
            fi
            exit 0
        elif [ -n "$JOB_ID" ]; then
            if [ -n "$COMMIT_MESSAGE" ]; then
                success "${COMMIT_MESSAGE}"
            else
                success "Commit initiated successfully (Job ID: ${JOB_ID})"
            fi
            if [ -n "$RESPONSE_CODE" ]; then
                if [ -n "$RESPONSE_CODE_DESC" ]; then
                    log "PAN-OS API code ${RESPONSE_CODE}: ${RESPONSE_CODE_DESC}"
                else
                    log "PAN-OS API code: ${RESPONSE_CODE}"
                fi
            fi
            log "Commit job ID: ${JOB_ID}"
            SHOULD_MONITOR="true"
        else
            error "PAN-OS commit response did not include a job ID"
            error "Response: ${COMMIT_RESPONSE}"
            exit 1
        fi
        ;;
    warning)
        WARNING_MESSAGE="${RESPONSE_LINES:-PAN-OS commit returned a warning}"
        warning "${WARNING_MESSAGE}"
        if [ -n "$RESPONSE_CODE" ]; then
            if [ -n "$RESPONSE_CODE_DESC" ]; then
                log "PAN-OS API code ${RESPONSE_CODE}: ${RESPONSE_CODE_DESC}"
            else
                log "PAN-OS API code: ${RESPONSE_CODE}"
            fi
        fi
        if [ -n "$JOB_ID" ]; then
            log "Proceeding to monitor commit job ${JOB_ID}"
            SHOULD_MONITOR="true"
        else
            exit 0
        fi
        ;;
    error)
        ERROR_MESSAGE="${RESPONSE_LINES:-PAN-OS commit returned an error}"
        if [ -n "$RESPONSE_CODE" ]; then
            if [ -n "$RESPONSE_CODE_DESC" ]; then
                error "Commit API returned error (code ${RESPONSE_CODE}: ${RESPONSE_CODE_DESC}): ${ERROR_MESSAGE}"
            else
                error "Commit API returned error (code ${RESPONSE_CODE}): ${ERROR_MESSAGE}"
            fi
        else
            error "Commit API returned error: ${ERROR_MESSAGE}"
        fi
        exit 1
        ;;
    *)
        error "Unexpected commit response status: ${RESPONSE_STATUS:-unknown}"
        if [ -n "$RESPONSE_CODE" ]; then
            if [ -n "$RESPONSE_CODE_DESC" ]; then
                error "PAN-OS API code ${RESPONSE_CODE}: ${RESPONSE_CODE_DESC}"
            else
                error "PAN-OS API code: ${RESPONSE_CODE}"
            fi
        fi
        error "Response: ${COMMIT_RESPONSE}"
        exit 1
        ;;
esac

if [ "$SHOULD_MONITOR" != "true" ]; then
    exit 0
fi

# Wait for commit to complete
log "Waiting for commit to complete..."
MAX_WAIT=300  # 5 minutes
WAIT_TIME=0
SLEEP_INTERVAL=5

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    sleep $SLEEP_INTERVAL
    WAIT_TIME=$((WAIT_TIME + SLEEP_INTERVAL))

        JOB_STATUS=$(wget -q ${CURL_OPTS} -O - "${BASE_URL}/?type=op&cmd=<show><jobs><id>${JOB_ID}</id></jobs></show>&key=${PANOS_API_KEY}")
    JOB_XML=$(normalize_xml "$JOB_STATUS")

    if [ -z "$JOB_XML" ]; then
        error "Empty job status response from PAN-OS"
        exit 1
    fi

    JOB_BLOCK=$(extract_job_block "$JOB_XML")
    if [ -z "$JOB_BLOCK" ]; then
        error "Unable to locate job details in PAN-OS response"
        error "Job status response: ${JOB_STATUS}"
        exit 1
    fi

    STATUS=$(extract_first_tag "$JOB_BLOCK" "status")
    RESULT=$(extract_first_tag "$JOB_BLOCK" "result")
    PROGRESS=$(extract_first_tag "$JOB_BLOCK" "progress")
    DETAIL_LINES_RAW=$(extract_lines "$JOB_BLOCK")
    DETAIL_MESSAGE=$(printf '%s\n' "$DETAIL_LINES_RAW" | join_with_semicolons)
    if [ -z "$DETAIL_MESSAGE" ]; then
        RAW_DETAIL_MSG=$(extract_msg_text "$JOB_BLOCK")
        if [ -n "$RAW_DETAIL_MSG" ]; then
            DETAIL_MESSAGE="$RAW_DETAIL_MSG"
        fi
    fi

    DISPLAY_PROGRESS="unknown"
    if [ -n "$PROGRESS" ]; then
        DISPLAY_PROGRESS="${PROGRESS}%"
    fi

    DISPLAY_STATUS="${STATUS:-unknown}"
    DISPLAY_RESULT="${RESULT:-pending}"
    log "Commit progress: ${DISPLAY_PROGRESS} - Status: ${DISPLAY_STATUS} - Result: ${DISPLAY_RESULT}"

    if [ "$STATUS" = "FIN" ] || [ "$STATUS" = "FAIL" ]; then
        if [ "$RESULT" = "OK" ]; then
            if [ -n "$DETAIL_MESSAGE" ]; then
                success "Commit completed successfully: ${DETAIL_MESSAGE}"
            else
                success "Commit completed successfully!"
            fi
            exit 0
        else
            if [ -n "$DETAIL_MESSAGE" ]; then
                error "Commit failed (${RESULT:-unknown}): ${DETAIL_MESSAGE}"
            else
                error "Commit failed with result: ${RESULT:-unknown}"
            fi
            exit 1
        fi
    fi
done

warning "Commit job is still running after ${MAX_WAIT} seconds"
warning "Job ID: ${JOB_ID} - You may want to check the firewall manually"
exit 0
