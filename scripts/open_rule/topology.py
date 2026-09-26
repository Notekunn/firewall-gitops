"""Topology loader and endpoint-to-segment resolution."""
from __future__ import annotations
from ipaddress import IPv4Network
from pathlib import Path
from typing import Any
import yaml
from scripts.open_rule import netutils
from scripts.open_rule.topology_model import (
    AmbiguousSegmentError,
    Edge,
    Firewall,
    Interface,
    Segment,
    SegmentNotFoundError,
    Topology,
)
RFC1918_NETS = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)
def load_topology(path: str | Path) -> Topology:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    segments = _load_segments(data.get("segments") or [])
    firewalls = _load_firewalls(data.get("firewalls") or [], segments)
    return Topology(segments=segments, firewalls=firewalls)
def resolve_segment(topo: Topology, endpoint_nets: netutils.NetInput) -> Segment:
    nets = netutils.as_nets(endpoint_nets)
    non_terminal = [seg for seg in topo.segments.values() if not seg.terminal]
    overlapping = [seg for seg in non_terminal if netutils.overlaps(seg.nets, nets)]
    containing = [seg for seg in overlapping if netutils.contains(seg.nets, nets)]
    partial = [seg for seg in overlapping if seg not in containing]
    if partial:
        raise AmbiguousSegmentError(_straddle_message(overlapping))
    if containing:
        return _single_most_specific(containing, nets)
    if overlapping:
        raise AmbiguousSegmentError(_straddle_message(overlapping))
    if _is_rfc1918(nets) and not netutils.nets_equal(nets, "0.0.0.0/0"):
        raise SegmentNotFoundError("private endpoint has no matching segment")
    terminals = [
        seg for seg in topo.segments.values()
        if seg.terminal and netutils.contains(seg.nets, nets)
    ]
    if terminals:
        return _single_most_specific(terminals, nets)
    raise SegmentNotFoundError("endpoint has no matching segment")
def interface_zone(fw: Firewall, segment: Segment | str) -> str | None:
    segment_name = segment.name if isinstance(segment, Segment) else segment
    matches = [
        interface.zone
        for interface in fw.interfaces
        if interface.segment == segment_name
    ]
    if len(matches) > 1:
        raise ValueError(f"duplicate interface segment on {fw.name}")
    return matches[0] if matches else None
def _load_segments(items: list[dict[str, Any]]) -> dict[str, Segment]:
    segments: dict[str, Segment] = {}
    for item in items:
        name = _required_str(item, "name")
        if name in segments:
            raise ValueError(f"duplicate segment: {name}")
        nets = netutils.as_nets(
            net
            for raw in item.get("nets") or []
            for net in netutils.parse_endpoint(str(raw)).nets
        )
        segments[name] = Segment(
            name=name,
            nets=nets,
            terminal=bool(item.get("terminal", False)),
            transit=bool(item.get("transit", False)),
        )
    if not segments:
        raise ValueError("topology has no segments")
    return segments
def _load_firewalls(
    items: list[dict[str, Any]],
    segments: dict[str, Segment],
) -> tuple[Firewall, ...]:
    firewalls: list[Firewall] = []
    seen: set[str] = set()
    for item in items:
        name = _required_str(item, "name")
        if name in seen:
            raise ValueError(f"duplicate firewall: {name}")
        seen.add(name)
        interfaces = _load_interfaces(item.get("interfaces") or [], segments, name)
        interface_segments = {interface.segment for interface in interfaces}
        edges = _load_edges(item.get("edges") or [], segments)
        for edge in edges:
            if not {edge.from_segment, edge.to_segment}.issubset(interface_segments):
                raise ValueError(f"edge references non-interface segment on {name}")
        default_route = _load_default_route(item, segments, interface_segments, name)
        firewalls.append(
            Firewall(
                name=name,
                cluster=_required_str(item, "cluster"),
                vendor=_required_str(item, "vendor"),
                interfaces=interfaces,
                edges=edges,
                default_route=default_route,
            )
        )
    return tuple(sorted(firewalls, key=lambda fw: fw.name))
def _load_interfaces(
    items: list[dict[str, Any]],
    segments: dict[str, Segment],
    firewall_name: str,
) -> tuple[Interface, ...]:
    interfaces = tuple(
        Interface(
            zone=_required_str(item, "zone"),
            segment=_required_segment(item, "segment", segments),
        )
        for item in items
    )
    if len({interface.segment for interface in interfaces}) != len(interfaces):
        raise ValueError(f"duplicate interface segment on {firewall_name}")
    return interfaces
def _load_edges(
    items: list[dict[str, Any]],
    segments: dict[str, Segment],
) -> tuple[Edge, ...]:
    return tuple(
        Edge(
            from_segment=_required_segment(item, "from", segments),
            to_segment=_required_segment(item, "to", segments),
        )
        for item in items
    )
def _load_default_route(
    item: dict[str, Any],
    segments: dict[str, Segment],
    interface_segments: set[str],
    firewall_name: str,
) -> str | None:
    if item.get("default_route") is None:
        return None
    default_route = _required_segment(item, "default_route", segments)
    if default_route not in interface_segments:
        raise ValueError(f"default_route is not an interface on {firewall_name}")
    return default_route
def _single_most_specific(
    segments: list[Segment],
    endpoint_nets: tuple[IPv4Network, ...],
) -> Segment:
    ranked = sorted(
        segments,
        key=lambda seg: (*_segment_specificity(seg, endpoint_nets), seg.name),
        reverse=True,
    )
    if len(ranked) > 1:
        if _segment_specificity(ranked[0], endpoint_nets) == _segment_specificity(
            ranked[1],
            endpoint_nets,
        ):
            raise AmbiguousSegmentError("endpoint matches multiple equal segments")
    return ranked[0]
def _segment_specificity(
    segment: Segment,
    endpoint_nets: tuple[IPv4Network, ...],
) -> tuple[int, int]:
    matching = [
        parent
        for endpoint_net in endpoint_nets
        for parent in segment.nets
        if endpoint_net.subnet_of(parent)
    ]
    return min(net.prefixlen for net in matching), -sum(
        net.num_addresses for net in matching
    )
def _straddle_message(segments: list[Segment]) -> str:
    names = ", ".join(sorted(seg.name for seg in segments))
    return f"endpoint straddles segments: {names}"
def _is_rfc1918(nets: tuple[IPv4Network, ...]) -> bool:
    return any(
        net.overlaps(private_net)
        for net in nets
        for private_net in RFC1918_NETS
    )
def _required_str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string: {key}")
    return value
def _required_segment(
    item: dict[str, Any],
    key: str,
    segments: dict[str, Segment],
) -> str:
    value = _required_str(item, key)
    if value not in segments:
        raise ValueError(f"unknown segment in {key}: {value}")
    return value
