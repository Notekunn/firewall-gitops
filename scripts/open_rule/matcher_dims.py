"""Dimension classification helpers for matcher."""

from __future__ import annotations

from ipaddress import IPv4Network

from scripts.open_rule import netutils
from scripts.open_rule.loader import Cluster
from scripts.open_rule.matcher_model import Flow
from scripts.open_rule.objects import (
    ANY_SERVICE,
    UNRESOLVABLE,
    resolve_rule_address,
    resolve_rule_service,
)


def dims_cover(flow: Flow, cluster: Cluster, rule: dict) -> bool:
    return all(
        (
            zone_covered(flow.src_zone, values(rule, "source_zones")),
            zone_covered(flow.dst_zone, values(rule, "destination_zones")),
            applications_covered(cluster.vendor, rule),
            address_state(flow.src_nets, cluster, rule, "source_addresses")[0],
            address_state(flow.dst_nets, cluster, rule, "destination_addresses")[0],
            service_state(flow, cluster, rule)[0],
        )
    )


def dims_potentially_cover(flow: Flow, cluster: Cluster, rule: dict) -> bool:
    if not all(
        (
            zone_covered(flow.src_zone, values(rule, "source_zones")),
            zone_covered(flow.dst_zone, values(rule, "destination_zones")),
            applications_covered(cluster.vendor, rule),
        )
    ):
        return False
    states = (
        address_state(flow.src_nets, cluster, rule, "source_addresses"),
        address_state(flow.dst_nets, cluster, rule, "destination_addresses"),
        service_state(flow, cluster, rule),
    )
    return all(covered or unresolved for covered, _exact, unresolved in states) and any(
        unresolved for _covered, _exact, unresolved in states
    )


def address_state(
    request_nets: tuple[IPv4Network, ...] | object,
    cluster: Cluster,
    rule: dict,
    field_name: str,
) -> tuple[bool, bool, bool]:
    rule_nets = resolve_rule_address(cluster, values(rule, field_name))
    if request_nets is UNRESOLVABLE or rule_nets is UNRESOLVABLE:
        return False, False, True
    return (
        netutils.contains(rule_nets, request_nets),  # type: ignore[arg-type]
        netutils.nets_equal(rule_nets, request_nets),  # type: ignore[arg-type]
        False,
    )


def service_state(flow: Flow, cluster: Cluster, rule: dict) -> tuple[bool, bool, bool]:
    rule_service = resolve_rule_service(cluster, values(rule, "services"))
    if rule_service is UNRESOLVABLE:
        return False, False, True
    if rule_service is ANY_SERVICE:
        return True, False, False
    concrete = rule_service  # type: ignore[assignment]
    covered = any(
        proto == flow.proto and netutils.port_contains(port, flow.port)
        for proto, port in concrete
    )
    exact = len(concrete) == 1 and concrete[0][0] == flow.proto and netutils.port_equal(
        concrete[0][1],
        flow.port,
    )
    return covered, exact, False


def zone_covered(request_zone: str, rule_zones: tuple[str, ...]) -> bool:
    return any(is_any(value) or value == request_zone for value in rule_zones)


def zone_exact(request_zone: str, rule_zones: tuple[str, ...]) -> bool:
    return len(rule_zones) == 1 and rule_zones[0] == request_zone


def applications_covered(vendor: str, rule: dict) -> bool:
    if vendor == "fortinet":
        return True
    return any(value.lower() == "any" for value in values(rule, "applications"))


def applications_exact(vendor: str, rule: dict) -> bool:
    if vendor == "fortinet":
        return True
    apps = values(rule, "applications")
    return len(apps) == 1 and apps[0].lower() == "any"


def values(rule: dict, field_name: str) -> tuple[str, ...]:
    value = rule.get(field_name) or []
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def is_any(value: str) -> bool:
    return value.lower() in {"any", "all"}
