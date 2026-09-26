#!/bin/sh
set -eu

[ "$#" -eq 2 ] || { echo "Usage: $0 CLUSTER manifest.tsv" >&2; exit 1; }
CLUSTER=$1
MANIFEST=$2
[ -f "$MANIFEST" ] || { echo "Manifest not found: $MANIFEST" >&2; exit 1; }

./scripts/deploy.sh -c "$CLUSTER" -a init --state-generation v2
if ./scripts/deploy.sh -c "$CLUSTER" -a state-list --state-generation v2 | grep -q .; then
    echo "Refusing import: firewall-$CLUSTER-v2 is not empty" >&2
    exit 1
fi

while IFS="$(printf '\t')" read -r address import_id; do
    case "$address" in ''|'#'*) continue ;; esac
    [ -n "$import_id" ] || { echo "Missing import ID for $address" >&2; exit 1; }
    (cd terraform && tofu import -var="cluster_name=$CLUSTER" "$address" "$import_id")
done < "$MANIFEST"

./scripts/deploy.sh -c "$CLUSTER" -a plan --state-generation v2
