from pathlib import Path
import shutil

import yaml

from scripts.open_rule.apply import apply_batch


def test_apply_extends_rules_and_new_objects(tmp_path):
    clusters = _copy_clusters(tmp_path)

    changed = apply_batch(
        [
            {
                "ticket": "T2",
                "src": "172.25.1.6",
                "dst": "8.8.8.8",
                "proto": "tcp",
                "port": 443,
            }
        ],
        topology_path=_repo_root() / "topology.yaml",
        clusters_dir=clusters,
    )

    core = _read(clusters / "fw-core" / "objects.yaml")
    out = _read(clusters / "fw-out" / "objects.yaml")
    assert clusters / "fw-core" / "objects.yaml" in changed
    assert clusters / "fw-out" / "objects.yaml" in changed
    assert core["rules"][0]["source_addresses"] == ["core-host", "core-other"]
    assert out["addresses"][-1]["name"] == "host-172-25-1-6"
    assert out["rules"][0]["source_addresses"] == [
        "core-host",
        "host-172-25-1-6",
    ]


def test_apply_creates_zone_files(tmp_path):
    clusters = _copy_clusters(tmp_path)

    changed = apply_batch(
        [
            {
                "ticket": "T7",
                "src": "172.25.1.7",
                "dst": "8.8.4.4",
                "proto": "tcp",
                "port": 8443,
            }
        ],
        topology_path=_repo_root() / "topology.yaml",
        clusters_dir=clusters,
    )

    core_path = clusters / "fw-core" / "objects" / "untrust-out-zone.yaml"
    out_path = clusters / "fw-out" / "objects" / "outside-zone.yaml"
    assert {core_path, out_path}.issubset(changed)
    assert _read(core_path)["rules"][0]["services"] == ["tcp-8443"]
    assert _read(out_path)["rules"][0]["destination_addresses"] == ["host-8-8-4-4"]


def test_apply_skips_unverified_f5_downstream_create(tmp_path):
    clusters = _copy_clusters(tmp_path)

    changed = apply_batch(
        [
            {
                "ticket": "T8",
                "src": "8.8.4.4",
                "dst": "172.25.1.7",
                "proto": "tcp",
                "port": 8443,
            }
        ],
        topology_path=_repo_root() / "topology.yaml",
        clusters_dir=clusters,
    )

    assert changed == set()
    assert not (clusters / "fw-core" / "objects" / "trust-zone.yaml").exists()


def _copy_clusters(tmp_path: Path) -> Path:
    target = tmp_path / "clusters"
    shutil.copytree(_repo_root() / "clusters", target)
    return target


def _read(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
