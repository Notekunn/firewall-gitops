#!/usr/bin/env python3
"""Reject migration plans that delete or replace managed resources."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan_json", type=Path)
    parser.add_argument("--allow", action="append", default=[], help="Reviewed resource address allowed to delete/replace")
    args = parser.parse_args()

    with args.plan_json.open(encoding="utf-8") as stream:
        plan = json.load(stream)

    blocked = []
    allowed = set(args.allow)
    for change in plan.get("resource_changes", []):
        address = change.get("address", "<unknown>")
        actions = change.get("change", {}).get("actions", [])
        destructive = "delete" in actions
        if destructive and address not in allowed:
            blocked.append((address, actions))

    if blocked:
        print("Migration plan contains unapproved delete/replace actions:")
        for address, actions in blocked:
            print(f"  - {address}: {','.join(actions)}")
        return 1

    print("Migration plan safety gate passed: no unapproved delete/replace actions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
