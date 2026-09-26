from pathlib import Path

from scripts.open_rule.orchestrator import process_flow
from scripts.open_rule.topology import load_topology


def test_core_to_internet_reports_two_already_open_hops():
    result = _process(
        {"ticket": "T1", "src": "172.25.1.5", "dst": "8.8.8.8", "proto": "tcp", "port": 443}
    )

    assert result.path == ("fw-core", "fw-out")
    assert [hop.decision.verdict for hop in result.hops] == [
        "ALREADY_OPEN",
        "ALREADY_OPEN",
    ]
    assert result.status == "ALREADY_OPEN"


def test_core_to_internet_extend_is_per_hop():
    result = _process(
        {"ticket": "T2", "src": "172.25.1.6", "dst": "8.8.8.8", "proto": "tcp", "port": 443}
    )

    assert [hop.firewall for hop in result.hops] == ["fw-core", "fw-out"]
    assert [hop.decision.verdict for hop in result.hops] == ["EXTEND", "EXTEND"]
    assert result.status == "EXTEND"


def test_internet_to_core_marks_f5_manual_and_core_unverified():
    result = _process(
        {"ticket": "T3", "src": "8.8.8.8", "dst": "172.25.1.5", "proto": "tcp", "port": 443}
    )

    assert result.path == ("fw-in", "fw-core")
    assert [hop.decision.verdict for hop in result.hops] == ["MANUAL_F5", "CREATE"]
    assert result.hops[1].decision.proposed_rule["source_addresses"] == [
        "verify-src-after-f5"
    ]
    assert result.status == "MANUAL_F5"


def test_core_to_mgmt_multi_vendor_path():
    result = _process(
        {
            "ticket": "T4",
            "src": "172.25.1.5",
            "dst": "172.25.10.5",
            "proto": "tcp",
            "port": 22,
        }
    )

    assert result.path == ("fw-core", "fw-mgmt")
    assert [hop.vendor for hop in result.hops] == ["palo-alto", "fortinet"]
    assert [hop.decision.verdict for hop in result.hops] == [
        "ALREADY_OPEN",
        "ALREADY_OPEN",
    ]


def test_internet_to_mgmt_fails_closed_instead_of_transiting_core():
    result = _process(
        {
            "ticket": "T6",
            "src": "8.8.8.8",
            "dst": "172.25.10.5",
            "proto": "tcp",
            "port": 22,
        }
    )

    assert result.status == "ERROR"
    assert "no directed path" in result.error


def test_bad_flow_is_error_and_batch_can_continue():
    result = _process(
        {"ticket": "T5", "src": "172.25.1.5", "dst": "8.8.8.8", "proto": "icmp", "port": 8}
    )

    assert result.status == "ERROR"
    assert "unsupported proto" in result.error


def _process(flow):
    root = Path(__file__).resolve().parents[3]
    topo = load_topology(root / "topology.yaml")
    return process_flow(flow, topo, str(root / "clusters"), {})
