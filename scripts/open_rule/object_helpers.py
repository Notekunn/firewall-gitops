"""Private helpers for object resolution."""

from __future__ import annotations

from ipaddress import IPv4Network
import re
from typing import Any, Iterable

from scripts.open_rule import netutils
from scripts.open_rule.object_model import (
    NAME_RE,
    UNRESOLVABLE,
    ObjectResolutionError,
    RuleAddress,
    Sentinel,
)


def address_object(
    nets: tuple[IPv4Network, ...],
    base_name: str | None,
) -> dict[str, Any]:
    if len(nets) == 1:
        net = nets[0]
        if net.prefixlen == 32:
            name = base_name or f"host-{net.network_address}"
        else:
            name = base_name or f"net-{net.network_address}-{net.prefixlen}"
        return {"name": slug(name), "ip_netmask": str(net)}
    range_text = netutils.format_ip_range(nets)
    return {"name": slug(base_name or f"range-{range_text}"), "ip_range": range_text}


def address_nets(address: dict[str, Any]) -> RuleAddress:
    if address.get("ip_netmask"):
        return netutils.as_nets(str(address["ip_netmask"]))
    if address.get("ip_range"):
        return netutils.as_nets(str(address["ip_range"]))
    return UNRESOLVABLE


def service_value(service: dict[str, Any]) -> tuple[str, netutils.PortRange] | Sentinel:
    proto = str(service.get("type", "")).lower()
    destination_port = service.get("destination_port")
    if proto not in {"tcp", "udp"} or destination_port is None:
        return UNRESOLVABLE
    return proto, netutils.parse_port(destination_port)


def assert_no_duplicate_name_conflicts(addresses: Iterable[dict[str, Any]]) -> None:
    by_name = addresses_by_name(addresses)
    for name, matches in by_name.items():
        values = [address_nets(address) for address in matches]
        if len(values) > 1 and any(
            left is UNRESOLVABLE
            or right is UNRESOLVABLE
            or not netutils.nets_equal(left, right)
            for left in values
            for right in values
        ):
            raise ObjectResolutionError(f"duplicate address name differs: {name}")


def assert_no_duplicate_service_name_conflicts(
    services: Iterable[dict[str, Any]],
) -> None:
    by_name = services_by_name(services)
    for name, matches in by_name.items():
        values = [service_value(service) for service in matches]
        if len(set(map(repr, values))) > 1:
            raise ObjectResolutionError(f"duplicate service name differs: {name}")


def addresses_by_name(
    addresses: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for address in addresses:
        name = address.get("name")
        if name:
            by_name.setdefault(str(name), []).append(address)
    return by_name


def services_by_name(
    services: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for service in services:
        name = service.get("name")
        if name:
            by_name.setdefault(str(name), []).append(service)
    return by_name


def nets_key(nets: tuple[IPv4Network, ...]) -> tuple[str, ...]:
    return tuple(str(net) for net in nets)


def port_text(port: netutils.PortRange) -> str:
    return str(port[0]) if port[0] == port[1] else f"{port[0]}-{port[1]}"


def is_any(value: str) -> bool:
    return value.lower() in {"any", "all"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "object"


def assert_name(value: str) -> None:
    if not NAME_RE.match(value):
        raise ObjectResolutionError(f"invalid generated name: {value}")
