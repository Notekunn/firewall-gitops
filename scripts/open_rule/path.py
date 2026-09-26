"""Directed firewall path calculation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from scripts.open_rule.topology import Firewall, Segment, Topology, interface_zone


class PathError(ValueError):
    pass


@dataclass(frozen=True)
class Hop:
    firewall: str
    vendor: str
    cluster: str
    in_segment: str
    out_segment: str
    in_zone: str
    out_zone: str


def compute_path(
    topo: Topology,
    src_seg: Segment | str,
    dst_seg: Segment | str,
) -> list[Hop]:
    src_name = src_seg.name if isinstance(src_seg, Segment) else src_seg
    dst_name = dst_seg.name if isinstance(dst_seg, Segment) else dst_seg
    src = topo.segment(src_name)
    dst = topo.segment(dst_name)

    if src.name == dst.name:
        if src.terminal:
            raise PathError("terminal-to-terminal flow has no firewall path")
        return []

    queue = deque([(src.name, [])])
    visited = {src.name}

    while queue:
        current, path = queue.popleft()
        for next_segment, fw in _adjacent(topo, current, dst.terminal):
            if next_segment in visited:
                continue
            if next_segment != dst.name and not topo.segment(next_segment).transit:
                continue
            hop = _build_hop(fw, current, next_segment)
            next_path = [*path, hop]
            if next_segment == dst.name:
                return next_path
            visited.add(next_segment)
            queue.append((next_segment, next_path))

    raise PathError(f"no directed path from {src.name} to {dst.name}")


def _adjacent(
    topo: Topology,
    segment: str,
    allow_default_route: bool,
) -> list[tuple[str, Firewall]]:
    edges: list[tuple[str, Firewall]] = []
    seen: set[tuple[str, str]] = set()
    for fw in topo.firewalls:
        for edge in fw.edges:
            if edge.from_segment == segment:
                key = (edge.to_segment, fw.name)
                if key not in seen:
                    seen.add(key)
                    edges.append((edge.to_segment, fw))
        if allow_default_route and fw.default_route and fw.default_route != segment:
            if interface_zone(fw, segment) and interface_zone(fw, fw.default_route):
                key = (fw.default_route, fw.name)
                if key not in seen:
                    seen.add(key)
                    edges.append((fw.default_route, fw))
    return sorted(edges, key=lambda item: (item[1].name, item[0]))


def _build_hop(fw: Firewall, in_segment: str, out_segment: str) -> Hop:
    in_zone = interface_zone(fw, in_segment)
    out_zone = interface_zone(fw, out_segment)
    if in_zone is None or out_zone is None:
        raise PathError(
            f"firewall {fw.name} lacks zones for {in_segment}->{out_segment}"
        )
    return Hop(
        firewall=fw.name,
        vendor=fw.vendor,
        cluster=fw.cluster,
        in_segment=in_segment,
        out_segment=out_segment,
        in_zone=in_zone,
        out_zone=out_zone,
    )
