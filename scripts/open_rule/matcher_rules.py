"""Rule/action helpers for matcher."""

from __future__ import annotations

from scripts.open_rule import netutils
from scripts.open_rule.loader import Cluster
from scripts.open_rule.matcher_model import Flow, SUPPORTED_MATCH_VENDORS
from scripts.open_rule.objects import UNRESOLVABLE


def append_would_overopen(flow: Flow, dim: str) -> bool:
    if dim == "src_addr":
        return flow.src_nets is UNRESOLVABLE or netutils.nets_equal(
            flow.src_nets,  # type: ignore[arg-type]
            "0.0.0.0/0",
        )
    if dim == "dst_addr":
        return flow.dst_nets is UNRESOLVABLE or netutils.nets_equal(
            flow.dst_nets,  # type: ignore[arg-type]
            "0.0.0.0/0",
        )
    return flow.port == (0, 65535)


def is_matchable(rule: dict) -> bool:
    return not (
        bool(rule.get("disabled"))
        or bool(rule.get("negate_source"))
        or bool(rule.get("negate_destination"))
        or bool(rule.get("source_users"))
    )


def is_permit(vendor: str, rule: dict) -> bool:
    action = str(rule.get("action", "allow")).lower()
    return action in {"allow", "accept"} or (
        vendor == "fortinet" and is_reset_action(rule)
    )


def is_blocker(vendor: str, rule: dict) -> bool:
    action = str(rule.get("action", "")).lower()
    return action in {"deny", "drop"} or (
        vendor == "palo-alto" and is_reset_action(rule)
    )


def is_reset_action(rule: dict) -> bool:
    return str(rule.get("action", "")).lower().startswith("reset-")


def assert_vendor(cluster: Cluster) -> None:
    if cluster.vendor not in SUPPORTED_MATCH_VENDORS:
        raise ValueError(f"matcher does not support vendor: {cluster.vendor}")


def port_text(port: netutils.PortRange) -> str:
    return str(port[0]) if port[0] == port[1] else f"{port[0]}-{port[1]}"


def new_rule_name(flow: Flow) -> str:
    return (
        f"allow-{flow.src_zone}-to-{flow.dst_zone}-{flow.proto}-"
        f"{port_text(flow.port)}"
    ).lower().replace("_", "-")
