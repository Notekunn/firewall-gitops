"""Rule matching and verdict generation."""

from __future__ import annotations

from typing import Any

from scripts.open_rule.loader import Cluster
from scripts.open_rule.matcher_decisions import (
    create_decision,
    extend_decision,
    rule_decision,
)
from scripts.open_rule.matcher_dims import (
    address_state,
    applications_exact,
    dims_cover,
    dims_potentially_cover,
    service_state,
    values,
    zone_exact,
)
from scripts.open_rule.matcher_model import Decision, Flow
from scripts.open_rule.matcher_rules import append_would_overopen, assert_vendor
from scripts.open_rule.matcher_rules import is_blocker, is_matchable, is_permit
from scripts.open_rule.objects import StagedObjects


def covers(flow: Flow, cluster: Cluster, rule: dict[str, Any]) -> bool:
    assert_vendor(cluster)
    return is_matchable(rule) and is_permit(cluster.vendor, rule) and dims_cover(
        flow,
        cluster,
        rule,
    )


def extendable(flow: Flow, cluster: Cluster, rule: dict[str, Any]) -> str | None:
    assert_vendor(cluster)
    if not is_matchable(rule) or not is_permit(cluster.vendor, rule):
        return None
    if not zone_exact(flow.src_zone, values(rule, "source_zones")):
        return None
    if not zone_exact(flow.dst_zone, values(rule, "destination_zones")):
        return None
    if not applications_exact(cluster.vendor, rule):
        return None

    states = {
        "src_addr": address_state(flow.src_nets, cluster, rule, "source_addresses"),
        "dst_addr": address_state(
            flow.dst_nets,
            cluster,
            rule,
            "destination_addresses",
        ),
        "svc": service_state(flow, cluster, rule),
    }
    not_covered = [name for name, state in states.items() if not state[0]]
    if len(not_covered) != 1:
        return None

    target = not_covered[0]
    if any(not states[name][1] for name in states if name != target):
        return None
    if append_would_overopen(flow, target):
        return None
    return target


def decide(
    flow: Flow,
    cluster: Cluster,
    staged: StagedObjects | None = None,
) -> Decision:
    assert_vendor(cluster)
    staged = staged or StagedObjects.for_cluster(cluster)
    unresolved_blocker: dict[str, Any] | None = None

    for rule in cluster.rules:
        if not is_matchable(rule):
            continue
        if is_blocker(cluster.vendor, rule):
            if dims_cover(flow, cluster, rule):
                return rule_decision(
                    "SHADOWED",
                    cluster,
                    rule,
                    message="preceding blocker covers this flow",
                )
            if unresolved_blocker is None and dims_potentially_cover(
                flow,
                cluster,
                rule,
            ):
                unresolved_blocker = rule
            continue
        if is_permit(cluster.vendor, rule) and dims_cover(flow, cluster, rule):
            if unresolved_blocker is not None:
                return rule_decision(
                    "SHADOW_UNKNOWN",
                    cluster,
                    unresolved_blocker,
                    message="unresolved preceding blocker may shadow this flow",
                )
            return rule_decision("ALREADY_OPEN", cluster, rule)

    for rule in cluster.rules:
        dim = extendable(flow, cluster, rule)
        if dim:
            return extend_decision(flow, cluster, staged, rule, dim)

    return create_decision(flow, cluster, staged)
