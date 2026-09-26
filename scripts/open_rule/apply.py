"""Apply safe rule opener decisions to YAML files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.open_rule.matcher import Decision
from scripts.open_rule.orchestrator import process_flow
from scripts.open_rule.orchestrator_model import FlowResult, HopVerdict
from scripts.open_rule.topology import load_topology


class ApplyError(ValueError):
    pass


def apply_results(
    results: list[FlowResult],
    clusters_dir: str | Path,
    allow_unverified_f5: bool = False,
) -> set[Path]:
    changed: set[Path] = set()
    clusters_path = Path(clusters_dir)
    for result in results:
        if result.status == "ERROR":
            raise ApplyError(f"{result.ticket}: {result.error}")
        for hop in result.hops:
            if _should_skip(hop, allow_unverified_f5):
                continue
            path = _target_path(hop, clusters_path)
            if _apply_decision(path, hop.decision):
                changed.add(path)
    return changed


def apply_batch(
    flows: list[dict[str, Any]],
    topology_path: str | Path = "topology.yaml",
    clusters_dir: str | Path = "clusters",
    allow_unverified_f5: bool = False,
) -> set[Path]:
    topo = load_topology(topology_path)
    cache = {}
    results = [process_flow(flow, topo, str(clusters_dir), cache) for flow in flows]
    return apply_results(results, clusters_dir, allow_unverified_f5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="open_rule_apply")
    parser.add_argument("input")
    parser.add_argument("--topology", default="topology.yaml")
    parser.add_argument("--clusters-dir", default="clusters")
    parser.add_argument("--allow-unverified-f5", action="store_true")
    parser.add_argument("--changed-files", action="store_true")
    args = parser.parse_args(argv)

    try:
        flows = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(flows, list) or not all(isinstance(flow, dict) for flow in flows):
            raise ApplyError("top-level JSON must be a list of objects")
        changed = apply_batch(
            flows,
            topology_path=args.topology,
            clusters_dir=args.clusters_dir,
            allow_unverified_f5=args.allow_unverified_f5,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 1

    for path in sorted(changed):
        print(path)
    if not changed and not args.changed_files:
        print("no YAML changes")
    return 0


def _should_skip(hop: HopVerdict, allow_unverified_f5: bool) -> bool:
    decision = hop.decision
    if decision.verdict not in {"CREATE", "EXTEND"}:
        return True
    return (
        "src_after_f5_unverified" in decision.caveats
        and not allow_unverified_f5
    )


def _target_path(hop: HopVerdict, clusters_dir: Path) -> Path:
    decision = hop.decision
    if decision.verdict == "EXTEND":
        sources = decision.rule_sources
        if len(sources) != 1:
            raise ApplyError(f"{hop.cluster}: cannot choose rule source")
        return Path(sources[0])
    zone = hop.out_zone or "rules"
    return clusters_dir / hop.cluster / "objects" / f"{zone}-zone.yaml"


def _apply_decision(path: Path, decision: Decision) -> bool:
    before = _read_yaml(path)
    after = {
        key: list(value) if isinstance(value, list) else value
        for key, value in before.items()
    }
    _append_named(after, "addresses", decision.new_addresses)
    _append_named(after, "services", decision.new_services)
    if decision.proposed_rule:
        _apply_rule(after, decision)
    if after == before:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(after, sort_keys=False), encoding="utf-8")
    return True


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ApplyError(f"expected YAML object: {path}")
    return data


def _append_named(
    doc: dict[str, Any],
    key: str,
    items: tuple[dict[str, Any], ...],
) -> None:
    if not items:
        return
    values = doc.setdefault(key, [])
    if not isinstance(values, list):
        raise ApplyError(f"{key} must be a list")
    existing = {str(item.get("name")): item for item in values if isinstance(item, dict)}
    for item in items:
        name = str(item.get("name") or "")
        if name in existing:
            if existing[name] != item:
                raise ApplyError(f"conflicting {key} object: {name}")
            continue
        values.append(dict(item))


def _apply_rule(doc: dict[str, Any], decision: Decision) -> None:
    rules = doc.setdefault("rules", [])
    if not isinstance(rules, list):
        raise ApplyError("rules must be a list")
    rule = dict(decision.proposed_rule or {})
    name = str(rule.get("name") or "")
    matches = [index for index, item in enumerate(rules) if item.get("name") == name]
    if decision.verdict == "EXTEND":
        if len(matches) != 1:
            raise ApplyError(f"expected one existing rule: {name}")
        rules[matches[0]] = rule
        return
    if matches:
        raise ApplyError(f"rule already exists: {name}")
    _insert_rule(rules, rule, decision.position or {})


def _insert_rule(rules: list[dict[str, Any]], rule: dict[str, Any], position: dict[str, Any]) -> None:
    where = str(position.get("where") or "last")
    pivot = position.get("pivot")
    if where == "first":
        rules.insert(0, rule)
    elif where == "last":
        rules.append(rule)
    elif where in {"before", "after"} and pivot:
        indexes = [index for index, item in enumerate(rules) if item.get("name") == pivot]
        if len(indexes) != 1:
            raise ApplyError(f"pivot rule not found: {pivot}")
        rules.insert(indexes[0] + (1 if where == "after" else 0), rule)
    else:
        raise ApplyError(f"unsupported position: {where}")


if __name__ == "__main__":
    raise SystemExit(main())
