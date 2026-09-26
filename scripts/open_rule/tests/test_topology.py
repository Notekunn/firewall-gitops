from pathlib import Path

import pytest
import yaml

from scripts.open_rule import netutils
from scripts.open_rule.topology import (
    AmbiguousSegmentError,
    SegmentNotFoundError,
    interface_zone,
    load_topology,
    resolve_segment,
)


def test_resolve_segment_prefers_specific_non_terminal(tmp_path):
    topo = _load_tmp_topology(
        tmp_path,
        {
            "segments": [
                {"name": "internet", "nets": ["0.0.0.0/0"], "terminal": True},
                {"name": "core", "nets": ["172.25.0.0/16"]},
                {"name": "core-app", "nets": ["172.25.1.0/24"]},
            ],
            "firewalls": [],
        },
    )

    segment = resolve_segment(topo, netutils.parse_endpoint("172.25.1.5"))
    assert segment.name == "core-app"


def test_specificity_ignores_unrelated_segment_nets(tmp_path):
    topo = _load_tmp_topology(
        tmp_path,
        {
            "segments": [
                {"name": "internet", "nets": ["0.0.0.0/0"], "terminal": True},
                {"name": "wide", "nets": ["10.0.0.0/8", "192.168.1.0/24"]},
                {"name": "core", "nets": ["172.25.0.0/16"]},
            ],
            "firewalls": [],
        },
    )

    segment = resolve_segment(topo, netutils.parse_endpoint("172.25.1.5"))
    assert segment.name == "core"


def test_straddle_precedes_terminal_fallback(tmp_path):
    topo = _load_tmp_topology(
        tmp_path,
        {
            "segments": [
                {"name": "internet", "nets": ["0.0.0.0/0"], "terminal": True},
                {"name": "core-a", "nets": ["10.10.0.0/24"]},
                {"name": "core-b", "nets": ["10.10.1.0/24"]},
            ],
            "firewalls": [],
        },
    )

    with pytest.raises(AmbiguousSegmentError):
        resolve_segment(topo, netutils.parse_endpoint("10.10.0.0/23"))


def test_partial_overlap_is_ambiguous(tmp_path):
    topo = _load_tmp_topology(
        tmp_path,
        {
            "segments": [
                {"name": "internet", "nets": ["0.0.0.0/0"], "terminal": True},
                {"name": "core-a", "nets": ["10.10.0.0/24"]},
            ],
            "firewalls": [],
        },
    )

    with pytest.raises(AmbiguousSegmentError):
        resolve_segment(topo, netutils.parse_endpoint("10.10.0.0/23"))


def test_public_and_unmatched_private_resolution(tmp_path):
    topo = _load_tmp_topology(
        tmp_path,
        {
            "segments": [
                {"name": "internet", "nets": ["0.0.0.0/0"], "terminal": True},
                {"name": "core", "nets": ["172.25.0.0/16"]},
            ],
            "firewalls": [],
        },
    )

    assert resolve_segment(topo, netutils.parse_endpoint("8.8.8.8")).name == "internet"
    with pytest.raises(SegmentNotFoundError):
        resolve_segment(topo, netutils.parse_endpoint("172.16.1.5"))


def test_interface_zone_is_firewall_local(tmp_path):
    topo = _load_tmp_topology(
        tmp_path,
        {
            "segments": [
                {"name": "t-out", "nets": ["10.0.2.0/24"]},
                {"name": "internet", "nets": ["0.0.0.0/0"], "terminal": True},
            ],
            "firewalls": [
                {
                    "name": "fw-core",
                    "cluster": "fw-core",
                    "vendor": "palo-alto",
                    "interfaces": [{"zone": "untrust-out", "segment": "t-out"}],
                    "edges": [],
                },
                {
                    "name": "fw-out",
                    "cluster": "fw-out",
                    "vendor": "fortinet",
                    "interfaces": [
                        {"zone": "inside", "segment": "t-out"},
                        {"zone": "outside", "segment": "internet"},
                    ],
                    "edges": [{"from": "t-out", "to": "internet"}],
                },
            ],
        },
    )

    fw_by_name = {fw.name: fw for fw in topo.firewalls}
    assert interface_zone(fw_by_name["fw-core"], "t-out") == "untrust-out"
    assert interface_zone(fw_by_name["fw-out"], "t-out") == "inside"


def test_duplicate_firewall_interface_segment_rejected(tmp_path):
    with pytest.raises(ValueError, match="duplicate interface segment"):
        _load_tmp_topology(
            tmp_path,
            {
                "segments": [{"name": "core", "nets": ["172.25.0.0/16"]}],
                "firewalls": [
                    {
                        "name": "fw-core",
                        "cluster": "fw-core",
                        "vendor": "palo-alto",
                        "interfaces": [
                            {"zone": "trust-a", "segment": "core"},
                            {"zone": "trust-b", "segment": "core"},
                        ],
                        "edges": [],
                    }
                ],
            },
        )


def test_repo_topology_loads_and_resolves_hub():
    topo = load_topology(_repo_root() / "topology.yaml")

    assert resolve_segment(topo, netutils.parse_endpoint("172.25.1.5")).name == "core"
    assert resolve_segment(topo, netutils.parse_endpoint("172.25.10.5")).name == "mgmt"
    assert resolve_segment(topo, netutils.parse_endpoint("8.8.8.8")).name == "internet"


def _load_tmp_topology(tmp_path: Path, data):
    path = tmp_path / "topology.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_topology(path)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
