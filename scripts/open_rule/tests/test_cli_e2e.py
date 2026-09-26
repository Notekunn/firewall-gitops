import json
import os
from pathlib import Path
import subprocess
import sys

from scripts.open_rule.cli import main


def test_cli_json_examples_exit_zero(capsys):
    root = Path(__file__).resolve().parents[3]

    exit_code = main(
        [
            str(root / "examples" / "flows.json"),
            "--topology",
            str(root / "topology.yaml"),
            "--clusters-dir",
            str(root / "clusters"),
            "--format",
            "json",
        ]
    )

    out = capsys.readouterr().out
    data = json.loads(out)
    assert exit_code == 0
    assert len(data) == 4
    assert data[2]["hops"][0]["verdict"] == "MANUAL_F5"


def test_cli_bad_flow_exits_two(tmp_path, capsys):
    root = Path(__file__).resolve().parents[3]
    batch = tmp_path / "bad.json"
    batch.write_text(
        json.dumps(
            [
                {
                    "ticket": "bad",
                    "src": "172.25.1.5",
                    "dst": "8.8.8.8",
                    "proto": "icmp",
                    "port": 8,
                }
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            str(batch),
            "--topology",
            str(root / "topology.yaml"),
            "--clusters-dir",
            str(root / "clusters"),
        ]
    )

    assert exit_code == 2
    assert "unsupported proto" in capsys.readouterr().out


def test_cli_mixed_good_and_bad_batch_continues(tmp_path, capsys):
    root = Path(__file__).resolve().parents[3]
    batch = tmp_path / "mixed.json"
    batch.write_text(
        json.dumps(
            [
                {
                    "ticket": "good",
                    "src": "172.25.1.5",
                    "dst": "8.8.8.8",
                    "proto": "tcp",
                    "port": 443,
                },
                {
                    "ticket": "bad",
                    "src": "172.25.1.5",
                    "dst": "8.8.8.8",
                    "proto": "icmp",
                    "port": 8,
                },
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            str(batch),
            "--topology",
            str(root / "topology.yaml"),
            "--clusters-dir",
            str(root / "clusters"),
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert [item["status"] for item in data] == ["ALREADY_OPEN", "ERROR"]


def test_cli_non_list_is_fatal(tmp_path, capsys):
    root = Path(__file__).resolve().parents[3]
    bad = tmp_path / "object.json"
    bad.write_text("{}", encoding="utf-8")

    exit_code = main([str(bad), "--topology", str(root / "topology.yaml")])

    assert exit_code == 1
    assert "top-level JSON must be a list" in capsys.readouterr().err


def test_cli_malformed_json_is_fatal(tmp_path, capsys):
    root = Path(__file__).resolve().parents[3]
    bad = tmp_path / "bad.json"
    bad.write_text("[", encoding="utf-8")

    exit_code = main([str(bad), "--topology", str(root / "topology.yaml")])

    assert exit_code == 1
    assert "fatal:" in capsys.readouterr().err


def test_module_invocation_open_rule_path():
    root = Path(__file__).resolve().parents[3]
    env = {**os.environ, "PYTHONPATH": "scripts"}

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "open_rule",
            str(root / "examples" / "flows.json"),
            "--topology",
            str(root / "topology.yaml"),
            "--clusters-dir",
            str(root / "clusters"),
            "--format",
            "json",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)[2]["hops"][0]["verdict"] == "MANUAL_F5"
