#!/bin/sh
set -eu
umask 077

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
TOFU_DIR="$PROJECT_ROOT/terraform"
CLUSTER_NAME=""
ACTION="plan"
STATE_GENERATION="v1"
PLAN_FILE=""

usage() {
    echo "Usage: $0 -c CLUSTER [-a init|fmt|validate|plan|apply|state-list|import] [--state-generation v1|v2] [--plan-file FILE]"
    exit "${1:-1}"
}

error() { echo "[ERROR] $*" >&2; }
log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2; }

while [ "$#" -gt 0 ]; do
    case "$1" in
        -c|--cluster) CLUSTER_NAME=${2-}; shift 2 ;;
        -a|--action) ACTION=${2-}; shift 2 ;;
        --state-generation) STATE_GENERATION=${2-}; shift 2 ;;
        --plan-file) PLAN_FILE=${2-}; shift 2 ;;
        -h|--help) usage 0 ;;
        *) error "Unknown option: $1"; usage ;;
    esac
done

[ -n "$CLUSTER_NAME" ] || { error "Cluster name is required"; usage; }
case "$CLUSTER_NAME" in *[!a-zA-Z0-9_-]*) error "Invalid cluster name"; exit 1 ;; esac
case "$ACTION" in init|fmt|validate|plan|apply|state-list|import) ;; *) error "Invalid action: $ACTION"; usage ;; esac
case "$STATE_GENERATION" in v1|v2) ;; *) error "State generation must be v1 or v2"; exit 1 ;; esac

CLUSTER_DIR="$PROJECT_ROOT/clusters/$CLUSTER_NAME"
[ -f "$CLUSTER_DIR/cluster.yaml" ] || { error "Cluster configuration not found: $CLUSTER_DIR/cluster.yaml"; exit 1; }
if [ ! -f "$CLUSTER_DIR/objects.yaml" ] && ! find "$CLUSTER_DIR/objects" -maxdepth 1 -type f -name '*.yaml' -print -quit 2>/dev/null | grep -q .; then
    error "Firewall objects not found: expected objects.yaml or objects/*.yaml"
    exit 1
fi
command -v tofu >/dev/null 2>&1 || { error "OpenTofu 1.12.6 is required"; exit 1; }
[ "$(tofu version -json | python3 -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])')" = "1.12.6" ] || { error "OpenTofu 1.12.6 is required"; exit 1; }

# Separate cached backend metadata for every cluster and state generation.
export TF_DATA_DIR="$TOFU_DIR/.terraform/$CLUSTER_NAME-$STATE_GENERATION"

STATE_NAME="firewall-$CLUSTER_NAME"
[ "$STATE_GENERATION" = "v1" ] || STATE_NAME="$STATE_NAME-v2"
PLAN_FILE=${PLAN_FILE:-"plan-$CLUSTER_NAME-$STATE_GENERATION.tfplan"}
PLAN_JSON=${PLAN_FILE%.tfplan}.json

init_backend() {
    : "${GITLAB_API_URL:?GITLAB_API_URL is required}"
    : "${GITLAB_PROJECT_ID:?GITLAB_PROJECT_ID is required}"
    : "${GITLAB_USERNAME:?GITLAB_USERNAME is required}"
    : "${GITLAB_PASSWORD:?GITLAB_PASSWORD is required}"
    export TF_HTTP_USERNAME="$GITLAB_USERNAME" TF_HTTP_PASSWORD="$GITLAB_PASSWORD"
    tofu init -input=false -lockfile=readonly -reconfigure \
        -backend-config="address=${GITLAB_API_URL}/projects/${GITLAB_PROJECT_ID}/terraform/state/${STATE_NAME}" \
        -backend-config="lock_address=${GITLAB_API_URL}/projects/${GITLAB_PROJECT_ID}/terraform/state/${STATE_NAME}/lock" \
        -backend-config="unlock_address=${GITLAB_API_URL}/projects/${GITLAB_PROJECT_ID}/terraform/state/${STATE_NAME}/lock" \
        -backend-config="lock_method=POST" -backend-config="unlock_method=DELETE" -backend-config="retry_wait_min=5"
}

case "$ACTION" in
    init|plan|apply) python3 "$SCRIPT_DIR/validate_yaml.py" --cluster "$CLUSTER_NAME" >&2 ;;
esac
cd "$TOFU_DIR"
log "Cluster=$CLUSTER_NAME state=$STATE_NAME timezone=$(python3 -c 'import sys,yaml; print((yaml.safe_load(open(sys.argv[1])) or {}).get("global",{}).get("timezone","Asia/Bangkok"))' "$CLUSTER_DIR/cluster.yaml")"
case "$ACTION" in
    init) init_backend ;;
    fmt) tofu fmt -check -recursive "$PROJECT_ROOT" ;;
    validate) tofu validate ;;
    plan)
        init_backend >&2
        tofu plan -input=false -var="cluster_name=$CLUSTER_NAME" -out="$PLAN_FILE"
        tofu show -json "$PLAN_FILE" > "$PLAN_JSON"
        [ "$STATE_GENERATION" = "v1" ] || python3 "$PROJECT_ROOT/scripts/check-plan-json.py" "$PLAN_JSON" --cluster "$CLUSTER_NAME"
        ;;
    apply)
        [ -f "$PLAN_FILE" ] || { error "Reviewed plan file not found: $PLAN_FILE"; exit 1; }
        init_backend >&2
        tofu show -json "$PLAN_FILE" > "$PLAN_JSON"
        python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); sys.exit(0 if p.get("variables",{}).get("cluster_name",{}).get("value")==sys.argv[2] else "Saved plan targets a different cluster")' "$PLAN_JSON" "$CLUSTER_NAME"
        [ "$STATE_GENERATION" = "v1" ] || python3 "$PROJECT_ROOT/scripts/check-plan-json.py" "$PLAN_JSON" --cluster "$CLUSTER_NAME"
        tofu apply "$PLAN_FILE"
        ;;
    state-list) init_backend >&2; tofu state list ;;
    import) error "Use scripts/import-v2-state.sh with a reviewed manifest"; exit 1 ;;
esac
