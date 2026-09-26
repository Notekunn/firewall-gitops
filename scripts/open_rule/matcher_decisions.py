"""Decision builders for matcher."""

from __future__ import annotations

from typing import Any

from scripts.open_rule.loader import Cluster
from scripts.open_rule.matcher_dims import values
from scripts.open_rule.matcher_model import Decision, Flow
from scripts.open_rule.matcher_rules import is_reset_action, new_rule_name, port_text
from scripts.open_rule.objects import (
    UNRESOLVABLE,
    StagedObjects,
    resolve_address,
    resolve_service,
)


def extend_decision(
    flow: Flow,
    cluster: Cluster,
    staged: StagedObjects,
    rule: dict[str, Any],
    dim: str,
) -> Decision:
    new_addresses: list[dict[str, Any]] = []
    new_services: list[dict[str, Any]] = []
    if dim == "src_addr":
        name, obj = resolve_address(cluster, flow.src_nets, staged)  # type: ignore[arg-type]
        field_name = "source_addresses"
        if obj:
            new_addresses.append(obj)
    elif dim == "dst_addr":
        name, obj = resolve_address(cluster, flow.dst_nets, staged)  # type: ignore[arg-type]
        field_name = "destination_addresses"
        if obj:
            new_addresses.append(obj)
    else:
        name, obj = resolve_service(cluster, flow.proto, port_text(flow.port), staged)
        field_name = "services"
        if obj:
            new_services.append(obj)

    proposed = dict(rule)
    proposed[field_name] = [*values(rule, field_name), name]
    return rule_decision(
        "EXTEND",
        cluster,
        rule,
        dim=dim,
        proposed_rule=proposed,
        new_addresses=tuple(new_addresses),
        new_services=tuple(new_services),
    )


def create_decision(flow: Flow, cluster: Cluster, staged: StagedObjects) -> Decision:
    new_addresses: list[dict[str, Any]] = []
    new_services: list[dict[str, Any]] = []
    caveats = ["shadow_unverified"]

    if flow.src_nets is UNRESOLVABLE:
        src_name = "verify-src-after-f5"
        caveats.append("src_after_f5_unverified")
    else:
        src_name, src_obj = resolve_address(cluster, flow.src_nets, staged)  # type: ignore[arg-type]
        if src_obj:
            new_addresses.append(src_obj)

    if flow.dst_nets is UNRESOLVABLE:
        return Decision(
            "ERROR",
            caveats=tuple(caveats),
            message="destination address is unresolvable",
        )
    dst_name, dst_obj = resolve_address(cluster, flow.dst_nets, staged)  # type: ignore[arg-type]
    if dst_obj:
        new_addresses.append(dst_obj)

    svc_name, svc_obj = resolve_service(cluster, flow.proto, port_text(flow.port), staged)
    if svc_obj:
        new_services.append(svc_obj)

    rule = {
        "name": new_rule_name(flow),
        "source_zones": [flow.src_zone],
        "destination_zones": [flow.dst_zone],
        "source_addresses": [src_name],
        "destination_addresses": [dst_name],
        "applications": ["any"],
        "services": [svc_name],
        "action": "Accept" if cluster.vendor == "fortinet" else "allow",
        "log_end": True,
    }
    if flow.src_zone == flow.dst_zone:
        caveats.append("intrazone_likely_permitted")
    return Decision(
        "CREATE",
        new_addresses=tuple(new_addresses),
        new_services=tuple(new_services),
        proposed_rule=rule,
        caveats=tuple(caveats),
        file_hint=f"clusters/{cluster.name}/objects/{flow.dst_zone}-zone.yaml",
        position=cluster.position,
    )


def rule_decision(
    verdict: str,
    cluster: Cluster,
    rule: dict[str, Any],
    dim: str | None = None,
    proposed_rule: dict[str, Any] | None = None,
    new_addresses: tuple[dict[str, Any], ...] = (),
    new_services: tuple[dict[str, Any], ...] = (),
    message: str | None = None,
) -> Decision:
    rule_name = str(rule.get("name", ""))
    caveats = ["shadow_unverified"]
    if cluster.vendor == "fortinet" and is_reset_action(rule):
        caveats.append("fortinet_reset_deploys_accept")
    return Decision(
        verdict,
        rule_name=rule_name,
        rule_sources=cluster.sources_for_rule_name(rule_name),
        dim=dim,
        new_addresses=new_addresses,
        new_services=new_services,
        proposed_rule=proposed_rule,
        caveats=tuple(caveats),
        message=message,
        position=cluster.position,
    )
