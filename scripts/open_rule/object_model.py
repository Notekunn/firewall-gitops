"""Object resolver shared model."""

from __future__ import annotations

from ipaddress import IPv4Network
import re

from scripts.open_rule import netutils


NAME_RE = re.compile(r"^[a-z0-9-]+$")


class ObjectResolutionError(ValueError):
    pass


class Sentinel:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


UNRESOLVABLE = Sentinel("UNRESOLVABLE")
ANY_SERVICE = Sentinel("ANY_SERVICE")

RuleAddress = tuple[IPv4Network, ...] | Sentinel
RuleService = tuple[tuple[str, netutils.PortRange], ...] | Sentinel
