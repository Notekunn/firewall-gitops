# V2 State Migration

Migrate one cluster at a time in this order: `fw-core`, `fw-mgmt`, then `fw-out`. Freeze applies before starting and keep every v1 state read-only and available throughout the observation window.

1. Back up v1 with `tofu state pull` and record its lineage and serial outside the repository.
2. Export a read-only inventory of firewall rule/object IDs, names, and rule order.
3. Build a reviewed, non-secret tab-separated manifest containing OpenTofu resource addresses and provider import IDs.
4. Run `scripts/import-v2-state.sh <cluster> <manifest.tsv>`. The script refuses a non-empty v2 state and generates a saved plan guarded against delete/replace actions.
5. Confirm `tofu state list` exactly matches YAML ownership. Review refresh-only and normal plan output before applying the saved artifact.
6. Export the after-inventory and stop if any unmanaged name, ID, or order changed.

Never use destroy, `init -migrate-state`, or `state push` to build v2. Roll back by disabling the v2 CI route and restoring the approved device configuration through the vendor process; do not copy v1 state into v2.
