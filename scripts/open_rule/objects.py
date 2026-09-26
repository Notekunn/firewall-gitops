"""Address and service object resolution for the rule opener."""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Network
import warnings
from typing import Any, Iterable

from scripts.open_rule import netutils
from scripts.open_rule.loader import Cluster
from scripts.open_rule.object_helpers import (
    address_nets,
    address_object,
    addresses_by_name,
    assert_name,
    assert_no_duplicate_name_conflicts,
    assert_no_duplicate_service_name_conflicts,
    is_any,
    nets_key,
    port_text,
    service_value,
    services_by_name,
    slug,
)
from scripts.open_rule.object_model import (
    ANY_SERVICE,
    UNRESOLVABLE,
    ObjectResolutionError,
    RuleAddress,
    RuleService,
)


@dataclass
class StagedObjects:
    existing_names: set[str] = field(default_factory=set)
    address_by_key: dict[tuple[str, ...], dict[str, Any]] = field(default_factory=dict)
    service_by_key: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    addresses: list[dict[str, Any]] = field(default_factory=list)
    services: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def for_cluster(cls, cluster: Cluster) -> "StagedObjects":
        names = {
            str(item.get("name"))
            for item in (*cluster.addresses, *cluster.services, *cluster.rules)
            if item.get("name")
        }
        return cls(existing_names=names)

    def stage_address(
        self,
        endpoint: netutils.NetInput,
        base_name: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        nets = netutils.as_nets(endpoint)
        key = nets_key(nets)
        if key in self.address_by_key:
            obj = self.address_by_key[key]
            return str(obj["name"]), obj

        obj = address_object(nets, base_name)
        obj["name"] = self._unique_name(str(obj["name"]))
        assert_name(str(obj["name"]))
        self.address_by_key[key] = obj
        self.addresses.append(obj)
        return str(obj["name"]), obj

    def stage_service(
        self,
        proto: str,
        port: str | int,
        base_name: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        proto = proto.lower()
        port_label = port_text(netutils.parse_port(port))
        key = (proto, port_label)
        if key in self.service_by_key:
            obj = self.service_by_key[key]
            return str(obj["name"]), obj

        obj = {
            "name": base_name or f"{proto}-{port_label}",
            "type": proto,
            "destination_port": port_label,
            "source_port": "1024-65535",
        }
        obj["name"] = self._unique_name(str(obj["name"]))
        assert_name(str(obj["name"]))
        self.service_by_key[key] = obj
        self.services.append(obj)
        return str(obj["name"]), obj

    def _unique_name(self, base_name: str) -> str:
        candidate = slug(base_name)
        index = 2
        used = self.existing_names | {
            str(item["name"]) for item in (*self.addresses, *self.services)
        }
        while candidate in used:
            candidate = f"{slug(base_name)}-{index}"
            index += 1
        self.existing_names.add(candidate)
        return candidate


def resolve_address(
    cluster: Cluster,
    endpoint: netutils.NetInput,
    staged: StagedObjects | None = None,
) -> tuple[str, dict[str, Any] | None]:
    assert_no_duplicate_name_conflicts(cluster.addresses)
    nets = netutils.as_nets(endpoint)
    matches: list[dict[str, Any]] = []
    for address in cluster.addresses:
        value = address_nets(address)
        if value is not UNRESOLVABLE and netutils.nets_equal(value, nets):
            matches.append(address)

    if matches:
        if len(matches) > 1:
            warnings.warn(
                "duplicate address objects share the same value; using first",
                RuntimeWarning,
                stacklevel=2,
            )
        return str(matches[0]["name"]), None

    staged = staged or StagedObjects.for_cluster(cluster)
    return staged.stage_address(nets)


def resolve_service(
    cluster: Cluster,
    proto: str,
    port: str | int,
    staged: StagedObjects | None = None,
) -> tuple[str, dict[str, Any] | None]:
    assert_no_duplicate_service_name_conflicts(cluster.services)
    proto = proto.lower()
    request_port = netutils.parse_port(port)
    for service in cluster.services:
        if str(service.get("type", "")).lower() != proto:
            continue
        destination_port = service.get("destination_port")
        if destination_port is None:
            continue
        if netutils.port_equal(netutils.parse_port(destination_port), request_port):
            return str(service["name"]), None

    staged = staged or StagedObjects.for_cluster(cluster)
    return staged.stage_service(proto, port)


def resolve_rule_address(cluster: Cluster, names: Iterable[str]) -> RuleAddress:
    resolved: list[IPv4Network] = []
    by_name = addresses_by_name(cluster.addresses)
    for raw_name in names or []:
        name = str(raw_name)
        if is_any(name):
            return netutils.as_nets("0.0.0.0/0")
        matches = by_name.get(name)
        if not matches:
            return UNRESOLVABLE
        values = [address_nets(address) for address in matches]
        if any(value is UNRESOLVABLE for value in values):
            return UNRESOLVABLE
        first = values[0]
        if any(not netutils.nets_equal(first, value) for value in values[1:]):
            return UNRESOLVABLE
        resolved.extend(first)
    if not resolved:
        return UNRESOLVABLE
    return netutils.as_nets(resolved)


def resolve_rule_service(cluster: Cluster, names: Iterable[str]) -> RuleService:
    resolved: list[tuple[str, netutils.PortRange]] = []
    by_name = services_by_name(cluster.services)
    for raw_name in names or []:
        name = str(raw_name)
        if is_any(name):
            return ANY_SERVICE
        if name.lower() == "application-default":
            return UNRESOLVABLE
        matches = by_name.get(name)
        if not matches:
            return UNRESOLVABLE
        values = [service_value(service) for service in matches]
        if any(value is UNRESOLVABLE for value in values):
            return UNRESOLVABLE
        first = values[0]
        if any(first != value for value in values[1:]):
            return UNRESOLVABLE
        resolved.append(first)
    if not resolved:
        return UNRESOLVABLE
    return tuple(sorted(resolved, key=lambda item: (item[0], item[1])))
