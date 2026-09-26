from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from scripts.open_rule import netutils
from scripts.open_rule.loader import load_cluster
from scripts.open_rule.matcher import Flow, covers, decide, extendable
from scripts.open_rule.objects import UNRESOLVABLE, StagedObjects


def test_covers_vendor_permit_and_app_dimension(tmp_path):
    pa = _cluster(
        tmp_path,
        "pa",
        "palo-alto",
        addresses=_addresses(),
        services=_services(),
        rules=[
            _rule("mysql-only", applications=["mysql"]),
            _rule("any-app", applications=["any"]),
        ],
    )
    forti = _cluster(
        tmp_path,
        "fg",
        "fortinet",
        addresses=_addresses(),
        services=_services(),
        rules=[_rule("fg-app-specific", action="Accept", applications=["mysql"])],
    )
    flow = _flow()

    assert not covers(flow, pa, pa.rules[0])
    assert covers(flow, pa, pa.rules[1])
    assert covers(flow, forti, forti.rules[0])


def test_reset_action_vendor_semantics(tmp_path):
    pa = _cluster(
        tmp_path,
        "pa",
        "palo-alto",
        addresses=_addresses(),
        services=_services(),
        rules=[_rule("reset", action="reset-client")],
    )
    forti = replace(pa, vendor="fortinet")

    assert decide(_flow(), pa).verdict == "SHADOWED"
    decision = decide(_flow(), forti)
    assert decision.verdict == "ALREADY_OPEN"
    assert "fortinet_reset_deploys_accept" in decision.caveats


def test_prefilter_rules_never_cover_or_extend(tmp_path):
    cluster = _cluster(
        tmp_path,
        "pa",
        "palo-alto",
        addresses=_addresses(),
        services=_services(),
        rules=[_rule("disabled", disabled=True)],
    )

    assert not covers(_flow(), cluster, cluster.rules[0])
    assert extendable(_flow(dst="10.10.1.6"), cluster, cluster.rules[0]) is None


def test_extend_requires_exact_other_dims_and_blocks_any_append(tmp_path):
    cluster = _cluster(
        tmp_path,
        "pa",
        "palo-alto",
        addresses=_addresses(),
        services=_services(),
        rules=[
            _rule("dst-diff"),
            _rule("src-any", source_addresses=["any"], services=["https"]),
        ],
    )

    assert extendable(_flow(dst="10.10.1.6"), cluster, cluster.rules[0]) == "dst_addr"
    assert extendable(_flow(port="8443"), cluster, cluster.rules[1]) is None
    assert extendable(_flow(src="0.0.0.0/0"), cluster, cluster.rules[0]) is None


def test_shadowed_and_shadow_unknown_precede_already_open(tmp_path):
    shadowed = _cluster(
        tmp_path,
        "shadowed",
        "palo-alto",
        addresses=_addresses(),
        services=_services(),
        rules=[_rule("deny-first", action="deny"), _rule("allow-later")],
    )
    unknown = _cluster(
        tmp_path,
        "unknown",
        "palo-alto",
        addresses=[*_addresses(), {"name": "fqdn", "fqdn": "example.com"}],
        services=_services(),
        rules=[
            _rule("deny-fqdn", action="deny", destination_addresses=["fqdn"]),
            _rule("allow-later"),
        ],
    )

    assert decide(_flow(), shadowed).verdict == "SHADOWED"
    assert decide(_flow(), unknown).verdict == "SHADOW_UNKNOWN"


def test_decide_already_open_extend_and_create(tmp_path):
    cluster = _cluster(
        tmp_path,
        "pa",
        "palo-alto",
        addresses=_addresses(),
        services=_services(),
        rules=[_rule("allow-existing")],
    )
    staged = StagedObjects.for_cluster(cluster)

    assert decide(_flow(), cluster, staged).verdict == "ALREADY_OPEN"
    extend = decide(_flow(dst="10.10.1.6"), cluster, staged)
    assert extend.verdict == "EXTEND"
    assert extend.dim == "dst_addr"
    assert extend.proposed_rule["name"] == "allow-existing"
    assert extend.proposed_rule["destination_addresses"] == [
        "dst",
        "host-10-10-1-6",
    ]
    assert extend.proposed_rule["source_addresses"] == ["src"]
    assert extend.proposed_rule["services"] == ["https"]

    create = decide(_flow(src="10.10.1.6", port="8443"), cluster, staged)
    assert create.verdict == "CREATE"
    assert create.proposed_rule["action"] == "allow"
    assert create.new_services[-1]["name"] == "tcp-8443"


def test_fortinet_create_emits_schema_valid_accept(tmp_path):
    cluster = _cluster(
        tmp_path,
        "fg",
        "fortinet",
        addresses=_addresses(),
        services=[],
        rules=[],
    )

    decision = decide(_flow(), cluster)

    assert decision.verdict == "CREATE"
    assert decision.proposed_rule["action"] == "Accept"


def test_unresolvable_source_creates_with_caveat(tmp_path):
    cluster = _cluster(
        tmp_path,
        "pa",
        "palo-alto",
        addresses=_addresses(),
        services=_services(),
        rules=[],
    )

    decision = decide(_flow(src=UNRESOLVABLE), cluster)

    assert decision.verdict == "CREATE"
    assert decision.proposed_rule["source_addresses"] == ["verify-src-after-f5"]
    assert "src_after_f5_unverified" in decision.caveats


def test_matcher_rejects_unsupported_vendor(tmp_path):
    cluster = _cluster(
        tmp_path,
        "pa",
        "palo-alto",
        addresses=_addresses(),
        services=_services(),
        rules=[],
    )

    with pytest.raises(ValueError):
        decide(_flow(), replace(cluster, vendor="checkpoint"))


def _cluster(tmp_path, name, vendor, addresses, services, rules):
    cluster_dir = tmp_path / name
    cluster_dir.mkdir()
    (cluster_dir / "cluster.yaml").write_text(
        yaml.safe_dump({"firewall": {"type": vendor}, "position": {"where": "first"}}),
        encoding="utf-8",
    )
    (cluster_dir / "objects.yaml").write_text(
        yaml.safe_dump(
            {"addresses": addresses, "services": services, "rules": rules}
        ),
        encoding="utf-8",
    )
    return load_cluster(tmp_path, name)


def _flow(src="10.10.1.5", dst="10.10.2.5", port="443"):
    return Flow(
        src_zone="trust",
        dst_zone="untrust",
        src_nets=UNRESOLVABLE if src is UNRESOLVABLE else netutils.as_nets(src),
        dst_nets=netutils.as_nets(dst),
        proto="tcp",
        port=netutils.parse_port(port),
        src_after_f5_unverified=src is UNRESOLVABLE,
    )


def _addresses():
    return [
        {"name": "src", "ip_netmask": "10.10.1.5/32"},
        {"name": "dst", "ip_netmask": "10.10.2.5/32"},
    ]


def _services():
    return [{"name": "https", "type": "tcp", "destination_port": "443"}]


def _rule(name, **overrides):
    rule = {
        "name": name,
        "source_zones": ["trust"],
        "destination_zones": ["untrust"],
        "source_addresses": ["src"],
        "destination_addresses": ["dst"],
        "applications": ["any"],
        "services": ["https"],
        "action": "allow",
    }
    rule.update(overrides)
    return rule
