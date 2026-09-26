"""IPv4 endpoint and port normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, collapse_addresses
from ipaddress import ip_address, ip_network, summarize_address_range
from typing import Iterable

MAX_ENDPOINT_PREFIXES = 256
PORT_MIN = 0
PORT_MAX = 65535


@dataclass(frozen=True)
class Endpoint:
    nets: tuple[IPv4Network, ...]
    range_bounds: tuple[IPv4Address, IPv4Address] | None = None


NetInput = Endpoint | str | IPv4Network | Iterable[IPv4Network]
PortRange = tuple[int, int]


def parse_endpoint(value: str) -> Endpoint:
    text = value.strip()
    if not text:
        raise ValueError("endpoint is empty")

    if text.lower() == "any":
        return Endpoint((IPv4Network("0.0.0.0/0"),))

    if "-" in text:
        first_text, last_text = _split_range(text)
        first = _parse_ipv4_address(first_text)
        last = _parse_ipv4_address(last_text)
        if int(first) > int(last):
            raise ValueError("range start is after range end")
        nets = _canonical(summarize_address_range(first, last))
        return Endpoint(nets, (first, last))

    try:
        net = ip_network(text, strict=True)
    except ValueError as exc:
        raise ValueError(f"invalid endpoint: {value}") from exc
    if not isinstance(net, IPv4Network):
        raise ValueError("only IPv4 endpoints are supported")
    return Endpoint(_canonical((net,)))


def as_nets(value: NetInput) -> tuple[IPv4Network, ...]:
    if isinstance(value, Endpoint):
        return value.nets
    if isinstance(value, str):
        return parse_endpoint(value).nets
    if isinstance(value, IPv4Network):
        return (value,)
    return _canonical(value)


def contains(outer: NetInput, inner: NetInput) -> bool:
    outer_nets = as_nets(outer)
    return all(
        any(inner_net.subnet_of(outer_net) for outer_net in outer_nets)
        for inner_net in as_nets(inner)
    )


def overlaps(a: NetInput, b: NetInput) -> bool:
    return any(left.overlaps(right) for left in as_nets(a) for right in as_nets(b))


def nets_equal(a: NetInput, b: NetInput) -> bool:
    return as_nets(a) == as_nets(b)


def endpoint_minmax(value: NetInput) -> tuple[IPv4Address, IPv4Address]:
    nets = as_nets(value)
    return (
        min(net.network_address for net in nets),
        max(net.broadcast_address for net in nets),
    )


def format_ip_range(value: NetInput) -> str:
    first, last = endpoint_minmax(value)
    text = f"{first}-{last}"
    if not nets_equal(parse_endpoint(text), value):
        raise ValueError("ip_range would widen sparse endpoint nets")
    return text


def parse_port(value: str | int) -> PortRange:
    text = str(value).strip().lower()
    if text == "any":
        return (PORT_MIN, PORT_MAX)
    if "-" in text:
        lo_text, hi_text = _split_range(text)
        lo = _parse_port_number(lo_text)
        hi = _parse_port_number(hi_text)
    else:
        lo = hi = _parse_port_number(text)
    if lo > hi:
        raise ValueError("port range start is after range end")
    return (lo, hi)


def port_contains(outer: PortRange, inner: PortRange) -> bool:
    return outer[0] <= inner[0] and outer[1] >= inner[1]


def port_equal(a: PortRange, b: PortRange) -> bool:
    return a == b


def _canonical(nets: Iterable[IPv4Network]) -> tuple[IPv4Network, ...]:
    collapsed = tuple(
        sorted(
            collapse_addresses(tuple(nets)),
            key=lambda net: (int(net.network_address), net.prefixlen),
        )
    )
    if len(collapsed) > MAX_ENDPOINT_PREFIXES:
        raise ValueError("endpoint expands to too many prefixes")
    return collapsed


def _parse_ipv4_address(value: str) -> IPv4Address:
    try:
        address = ip_address(value.strip())
    except ValueError as exc:
        raise ValueError(f"invalid IPv4 address: {value}") from exc
    if not isinstance(address, IPv4Address):
        raise ValueError("only IPv4 addresses are supported")
    return address


def _parse_port_number(value: str) -> int:
    if not value.isdigit():
        raise ValueError(f"invalid port: {value}")
    port = int(value)
    if port < PORT_MIN or port > PORT_MAX:
        raise ValueError(f"port out of range: {value}")
    return port


def _split_range(value: str) -> tuple[str, str]:
    parts = value.split("-")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError(f"invalid range: {value}")
    return parts[0].strip(), parts[1].strip()
