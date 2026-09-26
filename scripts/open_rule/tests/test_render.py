from pathlib import Path

import yaml

from scripts.open_rule.orchestrator import process_flow
from scripts.open_rule.render import render_json, render_text, yaml_for_decision
from scripts.open_rule.topology import load_topology


def test_text_render_includes_multihop_manual_and_caveats():
    result = _process(
        {"ticket": "T3", "src": "8.8.8.8", "dst": "172.25.1.5", "proto": "tcp", "port": 443}
    )

    text = render_text([result])

    assert "assumed path: fw-in -> fw-core" in text
    assert "verdict=MANUAL_F5" in text
    assert "path auto-computed from topology.yaml" in text
    assert "verify-src-after-f5" in text


def test_yaml_snippet_round_trips():
    result = _process(
        {"ticket": "T3", "src": "8.8.8.8", "dst": "172.25.1.5", "proto": "tcp", "port": 443}
    )
    snippet = yaml_for_decision(result.hops[1].decision)

    parsed = yaml.safe_load(snippet)

    assert parsed["rules"][0]["source_addresses"] == ["verify-src-after-f5"]
    assert parsed["rules"][0]["action"] == "allow"


def test_extend_yaml_is_complete_rule_body():
    result = _process(
        {"ticket": "T2", "src": "172.25.1.6", "dst": "8.8.8.8", "proto": "tcp", "port": 443}
    )
    snippet = yaml_for_decision(result.hops[0].decision)

    parsed = yaml.safe_load(snippet)

    rule = parsed["rules"][0]
    assert rule["source_addresses"] == ["core-host", "core-other"]
    assert rule["destination_addresses"] == ["internet-dns"]
    assert rule["services"] == ["tcp-443"]
    assert rule["action"] == "allow"


def test_text_render_includes_file_hint_and_position():
    result = _process(
        {"ticket": "T3", "src": "8.8.8.8", "dst": "172.25.1.5", "proto": "tcp", "port": 443}
    )

    text = render_text([result])

    assert "suggested file: clusters/fw-core/objects/trust-zone.yaml" in text
    assert "position: first" in text


def test_json_render_shape():
    result = _process(
        {"ticket": "T1", "src": "172.25.1.5", "dst": "8.8.8.8", "proto": "tcp", "port": 443}
    )

    data = render_json([result])

    assert data[0]["path"] == ["fw-core", "fw-out"]
    assert data[0]["hops"][0]["verdict"] == "ALREADY_OPEN"


def _process(flow):
    root = Path(__file__).resolve().parents[3]
    topo = load_topology(root / "topology.yaml")
    return process_flow(flow, topo, str(root / "clusters"), {})
