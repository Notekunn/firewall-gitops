from ipaddress import IPv4Network

import pytest

from scripts.open_rule import netutils


def test_parse_host_cidr_any_and_range():
    host = netutils.parse_endpoint("10.1.5.4")
    assert host.nets == (IPv4Network("10.1.5.4/32"),)

    cidr = netutils.parse_endpoint("10.1.0.0/16")
    assert cidr.nets == (IPv4Network("10.1.0.0/16"),)

    any_net = netutils.parse_endpoint("any")
    assert any_net.nets == (IPv4Network("0.0.0.0/0"),)

    range_endpoint = netutils.parse_endpoint("192.168.3.10-192.168.3.20")
    assert range_endpoint.range_bounds is not None
    assert len(range_endpoint.nets) > 1
    assert netutils.nets_equal(
        range_endpoint,
        netutils.parse_endpoint("192.168.3.10-192.168.3.20"),
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "2001:db8::1",
        "10.1.5.4/24",
        "192.168.3.20-192.168.3.10",
        "x-y",
    ],
)
def test_parse_endpoint_rejects_invalid(value):
    with pytest.raises(ValueError):
        netutils.parse_endpoint(value)


def test_contains_overlaps_and_equal():
    assert netutils.contains("0.0.0.0/0", "10.1.5.4")
    assert netutils.contains("10.1.0.0/16", "10.1.5.4")
    assert not netutils.contains("10.1.0.0/24", "10.1.5.4")
    assert netutils.overlaps("10.1.0.0/24", "10.1.0.128/25")
    assert not netutils.overlaps("10.1.0.0/24", "10.1.1.0/24")
    assert netutils.nets_equal("10.1.5.4", IPv4Network("10.1.5.4/32"))


def test_range_round_trip_and_sparse_guard():
    endpoint = netutils.parse_endpoint("192.168.3.10-192.168.3.20")
    range_text = netutils.format_ip_range(endpoint)
    assert range_text == "192.168.3.10-192.168.3.20"
    assert netutils.nets_equal(netutils.parse_endpoint(range_text), endpoint)

    sparse = (IPv4Network("192.168.1.1/32"), IPv4Network("192.168.1.3/32"))
    with pytest.raises(ValueError):
        netutils.format_ip_range(sparse)


def test_endpoint_prefix_cap(monkeypatch):
    monkeypatch.setattr(netutils, "MAX_ENDPOINT_PREFIXES", 1)
    with pytest.raises(ValueError):
        netutils.parse_endpoint("192.168.3.10-192.168.3.20")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", (0, 0)),
        ("443", (443, 443)),
        ("1024-65535", (1024, 65535)),
        ("any", (0, 65535)),
    ],
)
def test_parse_port(value, expected):
    assert netutils.parse_port(value) == expected


@pytest.mark.parametrize("value", ["", "-1", "65536", "80-22", "tcp/80", "1-"])
def test_parse_port_rejects_invalid(value):
    with pytest.raises(ValueError):
        netutils.parse_port(value)


def test_port_compare():
    assert netutils.port_contains(
        netutils.parse_port("80-443"),
        netutils.parse_port("443"),
    )
    assert not netutils.port_contains(
        netutils.parse_port("80"),
        netutils.parse_port("80-443"),
    )
    assert netutils.port_equal(netutils.parse_port("53"), netutils.parse_port(53))
