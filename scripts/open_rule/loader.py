"""Cluster config loader for the rule opener."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


FULL_L3_VENDORS = {"palo-alto", "fortinet"}
MANUAL_VENDORS = {"f5-waf"}


class ClusterNotFoundError(ValueError):
    pass


class UnsupportedVendorError(ValueError):
    pass


@dataclass(frozen=True)
class Cluster:
    name: str
    path: Path
    vendor: str
    position: dict[str, Any]
    addresses: tuple[dict[str, Any], ...]
    services: tuple[dict[str, Any], ...]
    rules: tuple[dict[str, Any], ...]
    rule_sources: tuple[str, ...]
    ip_lists: dict[str, Any]
    manual: bool = False

    def sources_for_rule_name(self, rule_name: str) -> tuple[str, ...]:
        return tuple(
            source
            for rule, source in zip(self.rules, self.rule_sources, strict=True)
            if rule.get("name") == rule_name
        )


def load_cluster(clusters_dir: str | Path, cluster_name: str) -> Cluster:
    cluster_path = Path(clusters_dir) / cluster_name
    if not cluster_path.is_dir():
        raise ClusterNotFoundError(f"cluster not found: {cluster_name}")

    cluster_data = _read_yaml(cluster_path / "cluster.yaml")
    firewall = cluster_data.get("firewall") or {}
    vendor = firewall.get("type")
    if vendor not in FULL_L3_VENDORS | MANUAL_VENDORS | {"checkpoint"}:
        raise UnsupportedVendorError(f"unsupported firewall vendor: {vendor}")
    if vendor == "checkpoint":
        raise UnsupportedVendorError("checkpoint clusters are out of scope")

    merged = _merge_objects(cluster_path)
    position = cluster_data.get("position") or {"where": "last"}

    if vendor in MANUAL_VENDORS:
        return Cluster(
            name=cluster_name,
            path=cluster_path,
            vendor=vendor,
            position=position,
            addresses=(),
            services=(),
            rules=(),
            rule_sources=(),
            ip_lists=merged["ip_lists"],
            manual=True,
        )

    return Cluster(
        name=cluster_name,
        path=cluster_path,
        vendor=vendor,
        position=position,
        addresses=tuple(merged["addresses"]),
        services=tuple(merged["services"]),
        rules=tuple(_normalize_rule(rule) for rule in merged["rules"]),
        rule_sources=tuple(merged["rule_sources"]),
        ip_lists={},
        manual=False,
    )


def load_cluster_data_for_merge_test(cluster_dir: str | Path) -> dict[str, list[Any]]:
    return _merge_objects(Path(cluster_dir))


def _merge_objects(cluster_path: Path) -> dict[str, Any]:
    addresses: list[dict[str, Any]] = []
    services: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []
    rule_sources: list[str] = []
    ip_lists: dict[str, Any] = {}

    for path, data in _object_documents(cluster_path):
        addresses.extend(_items(data, "addresses"))
        services.extend(_items(data, "services"))
        source_rules = _items(data, "rules")
        rules.extend(source_rules)
        rule_sources.extend(str(path) for _ in source_rules)
        if isinstance(data.get("ip_lists"), dict):
            ip_lists = _deep_merge(ip_lists, data["ip_lists"])

    return {
        "addresses": addresses,
        "services": services,
        "rules": rules,
        "rule_sources": rule_sources,
        "ip_lists": ip_lists,
    }


def _object_documents(cluster_path: Path):
    single = cluster_path / "objects.yaml"
    if single.exists():
        yield single, _read_yaml(single)

    objects_dir = cluster_path / "objects"
    if objects_dir.is_dir():
        for path in sorted(objects_dir.glob("*.yaml")):
            yield path, _read_yaml(path)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML object: {path}")
    return data


def _items(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key) or []
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return [dict(item) for item in value]


def _normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(rule)
    normalized.setdefault("applications", ["any"])
    normalized.setdefault("source_users", [])
    normalized.setdefault("disabled", False)
    normalized.setdefault("negate_source", False)
    normalized.setdefault("negate_destination", False)
    normalized.setdefault("action", "allow")
    return normalized


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
