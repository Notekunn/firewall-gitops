---
date: 2026-06-26
topic: phase-01-open-rule
---

# Phase 01 Open Rule

## Context
Executed Phase 1 of `open_rule`: pure IPv4 endpoint utilities, topology graph load/resolve, and directed firewall pathfinding.

## What Happened
- Added `scripts/open_rule` package with `netutils`, topology model/load/resolve, and directed path logic.
- Added repo-root `topology.yaml` for 4-FW hub.
- Added focused pytest coverage for endpoint parsing, straddle handling, per-FW zones, default-route behavior, and fail-closed path errors.
- Fixed review findings: runtime dev deps include `requirements.txt`; default-route-only path tested; multi-net segment specificity uses matching parent nets only; duplicate firewall interface segment fails closed.

## Decisions
- Kept Phase 1 pure/read-only except `load_topology`.
- Split topology dataclasses into `topology_model.py` to keep implementation files under 200 lines while preserving imports via `topology.py`.

## Next
- Phase 2: cluster loader and object staging.
