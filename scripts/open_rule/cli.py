"""CLI for ticket-driven rule opening decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.open_rule.orchestrator import process_flow
from scripts.open_rule.render import render_json, render_text
from scripts.open_rule.topology import load_topology


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="open_rule")
    parser.add_argument("input", nargs="?", default="-")
    parser.add_argument("--topology", default="topology.yaml")
    parser.add_argument("--clusters-dir", default="clusters")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    try:
        batch = _read_batch(args.input)
        if not isinstance(batch, list):
            raise ValueError("top-level JSON must be a list")
        topo = load_topology(args.topology)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 1

    cache = {}
    results = [
        process_flow(flow if isinstance(flow, dict) else {}, topo, args.clusters_dir, cache)
        for flow in batch
    ]

    if args.format == "json":
        print(json.dumps(render_json(results), indent=2))
    else:
        print(render_text(results))

    return 2 if any(result.status == "ERROR" for result in results) else 0


def _read_batch(path: str) -> Any:
    if path == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
