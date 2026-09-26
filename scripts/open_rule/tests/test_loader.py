from pathlib import Path

import pytest
import yaml

from scripts.open_rule.loader import (
    ClusterNotFoundError,
    UnsupportedVendorError,
    load_cluster,
    load_cluster_data_for_merge_test,
)


def test_load_cluster_merges_single_then_sorted_objects(tmp_path):
    cluster_dir = _cluster(tmp_path, "fw-core", "palo-alto")
    _write(
        cluster_dir / "objects.yaml",
        {
            "addresses": [{"name": "single", "ip_netmask": "10.0.0.1/32"}],
            "rules": [{"name": "single-rule"}],
        },
    )
    objects_dir = cluster_dir / "objects"
    objects_dir.mkdir()
    _write(objects_dir / "b.yaml", {"rules": [{"name": "b-rule"}]})
    _write(objects_dir / "a.yaml", {"services": [{"name": "a-svc"}]})

    cluster = load_cluster(tmp_path, "fw-core")

    assert [item["name"] for item in cluster.addresses] == ["single"]
    assert [item["name"] for item in cluster.services] == ["a-svc"]
    assert [rule["name"] for rule in cluster.rules] == ["single-rule", "b-rule"]
    assert [rule["applications"] for rule in cluster.rules] == [["any"], ["any"]]
    assert cluster.rule_sources[0].endswith("objects.yaml")
    assert cluster.rule_sources[1].endswith("b.yaml")


def test_loader_tolerates_missing_objects_yaml(tmp_path):
    cluster_dir = _cluster(tmp_path, "fw-out", "fortinet")
    objects_dir = cluster_dir / "objects"
    objects_dir.mkdir()
    _write(objects_dir / "rules.yaml", {"rules": [{"name": "allow-egress"}]})

    cluster = load_cluster(tmp_path, "fw-out")

    assert cluster.vendor == "fortinet"
    assert not cluster.manual
    assert cluster.rules[0]["name"] == "allow-egress"


def test_f5_partial_loads_ip_lists(tmp_path):
    cluster_dir = _cluster(tmp_path, "fw-in", "f5-waf")
    _write(
        cluster_dir / "objects.yaml",
        {
            "addresses": [{"name": "ignored", "ip_netmask": "10.0.0.1/32"}],
            "ip_lists": {"global": {"blocklist": ["10.0.0.1"]}},
        },
    )

    cluster = load_cluster(tmp_path, "fw-in")

    assert cluster.manual
    assert cluster.addresses == ()
    assert cluster.ip_lists["global"]["blocklist"] == ["10.0.0.1"]


def test_unsupported_and_missing_cluster_errors(tmp_path):
    _cluster(tmp_path, "cp", "checkpoint")

    with pytest.raises(UnsupportedVendorError):
        load_cluster(tmp_path, "cp")
    with pytest.raises(ClusterNotFoundError):
        load_cluster(tmp_path, "missing")


def test_merge_unit_matches_example_counts():
    root = Path(__file__).resolve().parents[3]
    merged = load_cluster_data_for_merge_test(root / "clusters" / "example")

    assert len(merged["addresses"]) == 5
    assert len(merged["services"]) == 4
    assert len(merged["rules"]) == 4
    assert len(merged["rule_sources"]) == 4


def _cluster(tmp_path, name, vendor):
    cluster_dir = tmp_path / name
    cluster_dir.mkdir()
    _write(
        cluster_dir / "cluster.yaml",
        {"firewall": {"type": vendor}, "position": {"where": "first"}},
    )
    return cluster_dir


def _write(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
