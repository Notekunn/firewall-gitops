#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

[ "$#" -eq 2 ] || { echo "Usage: $0 CLUSTER manifest.tsv" >&2; exit 1; }
CLUSTER=$1
MANIFEST=$2
[ -f "$MANIFEST" ] || { echo "Manifest not found: $MANIFEST" >&2; exit 1; }
case "$CLUSTER" in *[!a-zA-Z0-9_-]*) echo "Invalid cluster name" >&2; exit 1 ;; esac

python3 "$SCRIPT_DIR/migration_inventory.py" \
    --cluster-dir "$PROJECT_ROOT/clusters/$CLUSTER" \
    --manifest "$MANIFEST"

# Keep init and import on the same isolated v2 backend metadata.
export TF_DATA_DIR="$PROJECT_ROOT/terraform/.terraform/$CLUSTER-v2"
export TF_HTTP_USERNAME="${GITLAB_USERNAME:?GITLAB_USERNAME is required}"
export TF_HTTP_PASSWORD="${GITLAB_PASSWORD:?GITLAB_PASSWORD is required}"

"$SCRIPT_DIR/deploy.sh" -c "$CLUSTER" -a init --state-generation v2
if "$SCRIPT_DIR/deploy.sh" -c "$CLUSTER" -a state-list --state-generation v2 | grep -q .; then
    echo "Refusing import: firewall-$CLUSTER-v2 is not empty" >&2
    exit 1
fi

while IFS="$(printf '\t')" read -r address import_id; do
    case "$address" in ''|'#'*) continue ;; esac
    [ -n "$import_id" ] || { echo "Missing import ID for $address" >&2; exit 1; }
    (cd "$PROJECT_ROOT/terraform" && tofu import -input=false -var="cluster_name=$CLUSTER" "$address" "$import_id")
done < "$MANIFEST"

"$SCRIPT_DIR/deploy.sh" -c "$CLUSTER" -a plan --state-generation v2
