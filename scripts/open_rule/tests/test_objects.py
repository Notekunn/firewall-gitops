from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from scripts.open_rule import netutils
from scripts.open_rule.loader import Cluster, load_cluster
from scripts.open_rule.objects import (
    ANY_SERVICE,
    UNRESOLVABLE,
    ObjectResolutionError,
    StagedObjects,
    resolve_address,
    resolve_rule_address,
    resolve_rule_service,
    resolve_service,
)


def test_reuses_exact_address_and_stages_host_cidr_range(tmp_path):
    cluster = _cluster(
        tmp_path,
        addresses=[
            {"name": "host-a", "ip_netmask": "10.10.1.5/32"},
            {"name": "range-a", "ip_range": "10.10.2.10-10.10.2.20"},
        ],
    )
    staged = StagedObjects.for_cluster(cluster)

    assert resolve_address(cluster, "10.10.1.5", staged) == ("host-a", None)
    assert resolve_address(cluster, "10.10.2.10-10.10.2.20", staged) == (
        "range-a",
        None,
    )
    assert resolve_address(cluster, "10.10.3.0/24", staged)[0] == "net-10-10-3-0-24"

    name, obj = resolve_address(cluster, "10.10.4.10-10.10.4.20", staged)
    assert name == "range-10-10-4-10-10-10-4-20"
    assert obj == {"name": name, "ip_range": "10.10.4.10-10.10.4.20"}


def test_in_run_dedupe_and_name_collision(tmp_path):
    cluster = _cluster(
        tmp_path,
        addresses=[{"name": "host-10-10-1-10", "ip_netmask": "10.10.1.1/32"}],
    )
    staged = StagedObjects.for_cluster(cluster)

    first = resolve_address(cluster, "10.10.1.10", staged)
    second = resolve_address(cluster, "10.10.1.10", staged)

    assert first == second
    assert first[0] == "host-10-10-1-10-2"


def test_duplicate_value_warns_and_duplicate_name_errors(tmp_path):
    cluster = _cluster(
        tmp_path,
        addresses=[
            {"name": "a", "ip_netmask": "10.10.1.5/32"},
            {"name": "b", "ip_netmask": "10.10.1.5/32"},
        ],
    )
    with pytest.warns(RuntimeWarning):
        assert resolve_address(cluster, "10.10.1.5")[0] == "a"

    bad = replace(
        cluster,
        addresses=(
            {"name": "dup", "ip_netmask": "10.10.1.5/32"},
            {"name": "dup", "ip_netmask": "10.10.1.6/32"},
        ),
    )
    with pytest.raises(ObjectResolutionError):
        resolve_address(bad, "10.10.1.5")


def test_resolve_rule_address_handles_any_unresolvable_and_union(tmp_path):
    cluster = _cluster(
        tmp_path,
        addresses=[
            {"name": "a", "ip_netmask": "10.10.1.5/32"},
            {"name": "b", "ip_netmask": "10.10.2.0/24"},
            {"name": "fqdn", "fqdn": "example.com"},
        ],
    )

    assert netutils.nets_equal(resolve_rule_address(cluster, ["any"]), "0.0.0.0/0")
    assert netutils.nets_equal(
        resolve_rule_address(cluster, ["a", "b"]),
        netutils.as_nets(
            net
            for value in ("10.10.1.5/32", "10.10.2.0/24")
            for net in netutils.parse_endpoint(value).nets
        ),
    )
    assert resolve_rule_address(cluster, ["fqdn"]) is UNRESOLVABLE
    assert resolve_rule_address(cluster, ["missing"]) is UNRESOLVABLE


def test_reuses_and_stages_services(tmp_path):
    cluster = _cluster(
        tmp_path,
        services=[
            {
                "name": "https",
                "type": "tcp",
                "destination_port": "443",
                "source_port": "1-65535",
            }
        ],
    )
    staged = StagedObjects.for_cluster(cluster)

    assert resolve_service(cluster, "tcp", "443", staged) == ("https", None)
    assert resolve_service(cluster, "tcp", 8443, staged)[1] == {
        "name": "tcp-8443",
        "type": "tcp",
        "destination_port": "8443",
        "source_port": "1024-65535",
    }


def test_resolve_rule_service_keywords_and_named(tmp_path):
    cluster = _cluster(
        tmp_path,
        services=[{"name": "https", "type": "tcp", "destination_port": "443"}],
    )

    assert resolve_rule_service(cluster, ["Any"]) is ANY_SERVICE
    assert resolve_rule_service(cluster, ["application-default"]) is UNRESOLVABLE
    assert resolve_rule_service(cluster, ["missing"]) is UNRESOLVABLE
    assert resolve_rule_service(cluster, ["https"]) == (("tcp", (443, 443)),)


def _cluster(tmp_path, addresses=None, services=None, rules=None) -> Cluster:
    cluster_dir = tmp_path / "fw"
    cluster_dir.mkdir()
    (cluster_dir / "cluster.yaml").write_text(
        yaml.safe_dump({"firewall": {"type": "palo-alto"}}),
        encoding="utf-8",
    )
    (cluster_dir / "objects.yaml").write_text(
        yaml.safe_dump(
            {
                "addresses": addresses or [],
                "services": services or [],
                "rules": rules or [],
            }
        ),
        encoding="utf-8",
    )
    return load_cluster(tmp_path, "fw")
