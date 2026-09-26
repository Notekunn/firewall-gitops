"""Topology data model."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network


class AmbiguousSegmentError(ValueError):
    pass


class SegmentNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class Segment:
    name: str
    nets: tuple[IPv4Network, ...]
    terminal: bool = False
    transit: bool = False


@dataclass(frozen=True)
class Interface:
    zone: str
    segment: str


@dataclass(frozen=True)
class Edge:
    from_segment: str
    to_segment: str


@dataclass(frozen=True)
class Firewall:
    name: str
    cluster: str
    vendor: str
    interfaces: tuple[Interface, ...]
    edges: tuple[Edge, ...]
    default_route: str | None = None


@dataclass(frozen=True)
class Topology:
    segments: dict[str, Segment]
    firewalls: tuple[Firewall, ...]

    def segment(self, name: str) -> Segment:
        try:
            return self.segments[name]
        except KeyError as exc:
            raise SegmentNotFoundError(f"unknown segment: {name}") from exc
