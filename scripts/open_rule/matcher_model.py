"""Matcher data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Network
from typing import Any

from scripts.open_rule import netutils


SUPPORTED_MATCH_VENDORS = {"palo-alto", "fortinet"}


@dataclass(frozen=True)
class Flow:
    src_zone: str
    dst_zone: str
    src_nets: tuple[IPv4Network, ...] | object
    dst_nets: tuple[IPv4Network, ...] | object
    proto: str
    port: netutils.PortRange
    src_after_f5_unverified: bool = False


@dataclass(frozen=True)
class Decision:
    verdict: str
    rule_name: str | None = None
    rule_sources: tuple[str, ...] = ()
    dim: str | None = None
    new_addresses: tuple[dict[str, Any], ...] = ()
    new_services: tuple[dict[str, Any], ...] = ()
    proposed_rule: dict[str, Any] | None = None
    caveats: tuple[str, ...] = field(default_factory=tuple)
    message: str | None = None
    file_hint: str | None = None
    position: dict[str, Any] | None = None
