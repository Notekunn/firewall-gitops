import json
import subprocess
from pathlib import Path

import yaml
import jsonschema
import pytest

from scripts import validate_yaml


def write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def cluster_config(timezone="Asia/Bangkok"):
    return {
        "cluster": {"name": "test", "environment": "test"},
        "global": {"timezone": timezone},
        "firewall": {"type": "fortinet", "auto_commit": {"enabled": False}},
    }


def test_merged_validation_rejects_duplicate_names_and_missing_schedule(tmp_path):
    cluster = tmp_path / "clusters" / "test"
    write_yaml(cluster / "cluster.yaml", cluster_config())
    write_yaml(cluster / "objects" / "a.yaml", {"addresses": [{"name": "dup", "ip_netmask": "10.0.0.1/32"}]})
    write_yaml(cluster / "objects" / "b.yaml", {
        "addresses": [{"name": "dup", "ip_netmask": "10.0.0.2/32"}],
        "rules": [{"name": "r1", "source_addresses": ["any"], "destination_addresses": ["any"], "services": ["any"], "schedule": "missing"}],
    })

    errors = validate_yaml.validate_merged_cluster(str(cluster / "cluster.yaml"))

    assert any("Duplicate address" in error for error in errors)
    assert any("missing schedule" in error for error in errors)


def test_plan_gate_rejects_delete(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"resource_changes": [{"address": "x.y", "change": {"actions": ["delete", "create"]}}]}), encoding="utf-8")
    source = Path(__file__).parents[1] / "scripts" / "check-plan-json.py"
    result = subprocess.run(["python3", str(source), str(plan)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "x.y" in result.stdout


def test_plan_gate_accepts_non_destructive_change(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"resource_changes": [{"address": "x.y", "change": {"actions": ["update"]}}]}), encoding="utf-8")
    source = Path(__file__).parents[1] / "scripts" / "check-plan-json.py"
    result = subprocess.run(["python3", str(source), str(plan)], capture_output=True, text=True)
    assert result.returncode == 0


def test_change_metadata_must_be_complete():
    document = {
        "rules": [{
            "name": "r1",
            "source_addresses": ["any"],
            "destination_addresses": ["any"],
            "services": ["any"],
            "change": {"ticket": "CHG-1", "revision": 1},
        }]
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(document, validate_yaml.FIREWALL_RULES_SCHEMA)
