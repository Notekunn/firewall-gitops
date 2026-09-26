"""Hop processing helpers for orchestrator."""

from __future__ import annotations

from typing import Any

from scripts.open_rule import netutils
from scripts.open_rule.loader import ClusterNotFoundError, UnsupportedVendorError
from scripts.open_rule.loader import load_cluster
from scripts.open_rule.matcher import Decision, Flow, decide
from scripts.open_rule.objects import UNRESOLVABLE, StagedObjects
from scripts.open_rule.orchestrator_model import ClusterCache, HopVerdict, SEVERITY
from scripts.open_rule.path import Hop


def process_hop(
    hop: Hop,
    clusters_dir: str,
    cache: ClusterCache,
    src_nets: tuple[Any, ...],
    dst_nets: tuple[Any, ...],
    proto: str,
    port_range: netutils.PortRange,
    src_after_f5_unverified: bool,
) -> HopVerdict:
    try:
        cluster, staged = cluster_with_stage(hop.cluster, clusters_dir, cache)
        if cluster.manual or hop.vendor == "f5-waf":
            decision = Decision(
                "MANUAL_F5",
                caveats=("assumed_path",),
                message=(
                    "F5 WAF has no L3 GitOps rule model; verify manually via "
                    "SOAR blocklist workflow"
                ),
            )
        else:
            request = Flow(
                src_zone=hop.in_zone,
                dst_zone=hop.out_zone,
                src_nets=UNRESOLVABLE if src_after_f5_unverified else src_nets,
                dst_nets=dst_nets,
                proto=proto,
                port=port_range,
                src_after_f5_unverified=src_after_f5_unverified,
            )
            decision = with_assumed_path_caveat(decide(request, cluster, staged))
    except (ClusterNotFoundError, UnsupportedVendorError, ValueError) as exc:
        decision = Decision("ERROR", caveats=("assumed_path",), message=str(exc))

    return HopVerdict(
        firewall=hop.firewall,
        vendor=hop.vendor,
        cluster=hop.cluster,
        in_segment=hop.in_segment,
        out_segment=hop.out_segment,
        in_zone=hop.in_zone,
        out_zone=hop.out_zone,
        decision=decision,
    )


def cluster_with_stage(
    cluster_name: str,
    clusters_dir: str,
    cache: ClusterCache,
):
    if cluster_name not in cache:
        cluster = load_cluster(clusters_dir, cluster_name)
        cache[cluster_name] = (cluster, StagedObjects.for_cluster(cluster))
    return cache[cluster_name]


def with_assumed_path_caveat(decision: Decision) -> Decision:
    if "assumed_path" in decision.caveats:
        return decision
    return Decision(
        verdict=decision.verdict,
        rule_name=decision.rule_name,
        rule_sources=decision.rule_sources,
        dim=decision.dim,
        new_addresses=decision.new_addresses,
        new_services=decision.new_services,
        proposed_rule=decision.proposed_rule,
        caveats=(*decision.caveats, "assumed_path"),
        message=decision.message,
        file_hint=decision.file_hint,
        position=decision.position,
    )


def worst_status(hops: list[HopVerdict]) -> str:
    return max(
        (hop.decision.verdict for hop in hops),
        key=lambda verdict: SEVERITY.get(verdict, 0),
    )
