#!/usr/bin/env python3
"""Fail closed on destructive actions or ownership changes during adoption."""

import argparse
import json
from pathlib import Path

from migration_inventory import ownership


def check_plan(plan, expected=None):
    errors = []
    if not isinstance(plan, dict) or not isinstance(plan.get("resource_changes"), list):
        return ["Missing resource_changes in plan JSON"]
    if plan.get("errored") or plan.get("complete") is False or plan.get("deferred_changes"):
        errors.append("Plan is errored, incomplete, or deferred")
    seen = set()
    for resource in plan["resource_changes"]:
        if resource.get("mode", "managed") != "managed":
            continue
        address = resource.get("address", "<unknown>")
        change = resource.get("change", {})
        actions = change.get("actions", [])
        if actions not in (["no-op"], ["update"], ["read"]):
            errors.append(f"{address}: adoption forbids actions {actions}")
        if expected is None:
            continue
        if address not in expected or address in seen:
            errors.append(f"Unexpected or duplicate resource: {address}")
            continue
        seen.add(address)
        spec = expected[address]
        for side in ("before", "after"):
            value = change.get(side) or {}
            member_key = spec.get("members")
            if member_key:
                members = value.get(member_key)
                names = list(members) if isinstance(members, dict) else [item.get("name") for item in (members or [])]
                if len(names) != len(set(names)) or set(names) != set(spec["names"]):
                    errors.append(f"{address}: {side} members differ from YAML ownership")
                if member_key == "rules" and side == "after" and names != spec["names"]:
                    errors.append(f"{address}: planned rule order differs from YAML")
            elif value.get("name") != spec["name"]:
                errors.append(f"{address}: {side} name differs from YAML")
        if spec.get("kind") == "rules" and resource.get("type") == "fortios_firewall_policy":
            before, after = change.get("before") or {}, change.get("after") or {}
            if not before.get("policyid") or before.get("policyid") != after.get("policyid"):
                errors.append(f"{address}: policy identity changed or is unknown")
    if expected is not None and seen != set(expected):
        errors.append("Plan resource addresses do not match YAML ownership")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan_json", type=Path)
    parser.add_argument("--cluster")
    args = parser.parse_args()
    try:
        expected = ownership(Path(__file__).resolve().parents[1] / "clusters" / args.cluster) if args.cluster else None
        plan = json.loads(args.plan_json.read_text())
        errors = check_plan(plan, expected)
        if args.cluster and plan.get("variables", {}).get("cluster_name", {}).get("value") != args.cluster:
            errors.append("Plan cluster does not match selected cluster")
    except (ValueError, OSError, KeyError, TypeError) as error:
        errors = [f"Cannot validate plan: {error}"]
    for error in errors:
        print(error)
    if errors:
        return 1
    print("Migration plan gate passed: no creates/deletes/replacements or ownership expansion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
