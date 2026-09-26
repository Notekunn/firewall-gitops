from dataclasses import replace
from pathlib import Path

import pytest

from scripts.open_rule.path import PathError, compute_path
from scripts.open_rule.topology import Segment, Topology, load_topology


def test_internet_to_core_path_has_f5_then_core():
    topo = _hub()
    hops = compute_path(topo, "internet", "core")

    assert [hop.firewall for hop in hops] == ["fw-in", "fw-core"]
    assert [(hop.in_zone, hop.out_zone) for hop in hops] == [
        ("ingress", "to-core"),
        ("untrust-in", "trust"),
    ]
    assert hops[0].vendor == "f5-waf"
    assert hops[1].vendor == "palo-alto"


def test_core_to_internet_path_uses_core_then_out():
    topo = _hub()
    hops = compute_path(topo, "core", "internet")

    assert [hop.firewall for hop in hops] == ["fw-core", "fw-out"]
    assert [(hop.in_segment, hop.out_segment) for hop in hops] == [
        ("core", "t-out"),
        ("t-out", "internet"),
    ]
    assert [(hop.in_zone, hop.out_zone) for hop in hops] == [
        ("trust", "untrust-out"),
        ("inside", "outside"),
    ]


def test_terminal_destination_uses_default_route_without_explicit_edge():
    topo = _hub_without_core_egress_edge()
    hops = compute_path(topo, "core", "internet")

    assert [hop.firewall for hop in hops] == ["fw-core", "fw-out"]
    assert [(hop.in_segment, hop.out_segment) for hop in hops] == [
        ("core", "t-out"),
        ("t-out", "internet"),
    ]


def test_core_to_mgmt_path_uses_core_then_mgmt():
    topo = _hub()
    hops = compute_path(topo, "core", "mgmt")

    assert [hop.firewall for hop in hops] == ["fw-core", "fw-mgmt"]
    assert [(hop.in_zone, hop.out_zone) for hop in hops] == [
        ("trust", "mgmt-uplink"),
        ("uplink", "mgmt"),
    ]


def test_path_does_not_transit_host_segments():
    with pytest.raises(PathError):
        compute_path(_hub(), "internet", "mgmt")


def test_intra_segment_path_is_empty():
    assert compute_path(_hub(), "core", "core") == []


def test_terminal_to_terminal_is_error():
    with pytest.raises(PathError):
        compute_path(_hub(), "internet", "internet")


def test_unreachable_private_segment_is_error_not_default_routed():
    topo = _hub_without_core_egress_edge()
    isolated = Segment("isolated", tuple())
    topo = replace(topo, segments={**topo.segments, "isolated": isolated})

    with pytest.raises(PathError):
        compute_path(topo, "core", "isolated")


def _hub_without_core_egress_edge() -> Topology:
    topo = _hub()
    firewalls = []
    for fw in topo.firewalls:
        if fw.name == "fw-core":
            edges = tuple(
                edge for edge in fw.edges if edge.to_segment != "t-out"
            )
            fw = replace(fw, edges=edges)
        firewalls.append(fw)
    return replace(topo, firewalls=tuple(firewalls))


def _hub() -> Topology:
    return load_topology(_repo_root() / "topology.yaml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
