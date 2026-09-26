"""Per-ticket path orchestration."""

from __future__ import annotations

from typing import Any

from scripts.open_rule import netutils
from scripts.open_rule.matcher import Decision
from scripts.open_rule.orchestrator_hops import process_hop, worst_status
from scripts.open_rule.orchestrator_model import ClusterCache, FlowResult, HopVerdict
from scripts.open_rule.orchestrator_model import TICKET_RE
from scripts.open_rule.path import PathError, compute_path
from scripts.open_rule.topology import (
    AmbiguousSegmentError,
    SegmentNotFoundError,
    Topology,
    resolve_segment,
)


def process_flow(
    flow: dict[str, Any],
    topo: Topology,
    clusters_dir: str,
    cache: ClusterCache | None = None,
) -> FlowResult:
    cache = cache if cache is not None else {}
    ticket = str(flow.get("ticket") or "unticketed")
    src = str(flow.get("src") or "")
    dst = str(flow.get("dst") or "")
    proto = str(flow.get("proto") or "").lower()
    port = str(flow.get("port") or "")

    if not TICKET_RE.match(ticket):
        return _flow_error(
            ticket="invalid-ticket",
            src=src,
            dst=dst,
            proto=proto,
            port=port,
            error="invalid ticket",
        )

    try:
        if proto not in {"tcp", "udp"}:
            raise ValueError(f"unsupported proto: {proto}")
        src_endpoint = netutils.parse_endpoint(src)
        dst_endpoint = netutils.parse_endpoint(dst)
        port_range = netutils.parse_port(port)
        src_seg = resolve_segment(topo, src_endpoint)
        dst_seg = resolve_segment(topo, dst_endpoint)
        hops = compute_path(topo, src_seg, dst_seg)
    except (ValueError, AmbiguousSegmentError, SegmentNotFoundError, PathError) as exc:
        return _flow_error(ticket, src, dst, proto, port, str(exc))

    if not hops:
        hop = HopVerdict(
            firewall="",
            vendor="",
            cluster="",
            in_segment=src_seg.name,
            out_segment=dst_seg.name,
            in_zone="",
            out_zone="",
            decision=Decision(
                "INTRA_SEGMENT",
                caveats=("intrazone_likely_permitted", "assumed_path"),
                message="source and destination resolve to the same segment",
            ),
        )
        return FlowResult(
            ticket,
            src,
            dst,
            proto,
            port,
            src_seg.name,
            dst_seg.name,
            (),
            (hop,),
            "INTRA_SEGMENT",
        )

    hop_results: list[HopVerdict] = []
    previous_was_f5 = False
    for hop in hops:
        hop_results.append(
            process_hop(
                hop,
                clusters_dir,
                cache,
                src_endpoint.nets,
                dst_endpoint.nets,
                proto,
                port_range,
                previous_was_f5,
            )
        )
        previous_was_f5 = hop_results[-1].decision.verdict == "MANUAL_F5"

    return FlowResult(
        ticket,
        src,
        dst,
        proto,
        port,
        src_seg.name,
        dst_seg.name,
        tuple(hop.firewall for hop in hops),
        tuple(hop_results),
        worst_status(hop_results),
    )


def _flow_error(
    ticket: str,
    src: str,
    dst: str,
    proto: str,
    port: str,
    error: str,
) -> FlowResult:
    return FlowResult(
        ticket=ticket,
        src=src,
        dst=dst,
        proto=proto,
        port=port,
        src_segment=None,
        dst_segment=None,
        path=(),
        hops=(),
        status="ERROR",
        error=error,
    )
