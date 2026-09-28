"""Derive exact resource ownership from the same YAML inputs as OpenTofu."""

import argparse
import json
from pathlib import Path

import yaml

try:
    from .validate_yaml import load_cluster_objects
except ImportError:
    from validate_yaml import load_cluster_objects


def ownership(cluster_dir):
    cluster = yaml.safe_load((Path(cluster_dir) / "cluster.yaml").read_text())
    vendor = cluster["firewall"]["type"]
    objects = {key: [] for key in ("addresses", "services", "schedules", "rules")}
    for _, document in load_cluster_objects(str(cluster_dir)):
        for key in objects:
            objects[key].extend(document.get(key, []))
    resources = {}

    def add(resource, name, kind):
        resources[f'{prefix}.{resource}[{json.dumps(name)}]'] = {"name": name, "kind": kind}

    if vendor == "palo-alto":
        prefix = "module.palo_alto_firewall[0]"
        resources[f"{prefix}.panos_addresses.address_objects"] = {
            "members": "addresses", "names": [item["name"] for item in objects["addresses"]]
        }
        resources[f"{prefix}.panos_security_policy_rules.firewall_rules"] = {
            "members": "rules", "names": [item["name"] for item in objects["rules"]]
        }
        for item in objects["services"]:
            add("panos_service.service_objects", item["name"], "services")
        for item in objects["schedules"]:
            add("panos_schedule.schedules", item["name"], "schedules")
    elif vendor == "fortinet":
        prefix = "module.fortinet_firewall[0]"
        for kind, resource in (("addresses", "fortios_firewall_address.addresses"),
                               ("services", "fortios_firewallservice_custom.services")):
            for item in objects[kind]:
                add(resource, item["name"], kind)
        for item in objects["schedules"]:
            schedule_type = "onetime" if "non_recurring" in item["schedule_type"] else "recurring"
            add(f"fortios_firewallschedule_{schedule_type}.schedules", item["name"], "schedules")
        for index, item in enumerate(objects["rules"]):
            key = json.dumps(f'{index:03d}-{item["name"]}')
            resources[f"{prefix}.fortios_firewall_policy.rules[{key}]"] = {"name": item["name"], "kind": "rules"}
    else:
        raise ValueError(f"V2 migration is unsupported for {vendor}")
    return resources


def read_manifest(path, expected):
    rows = []
    seen = set()
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 2 or not all(fields):
            raise ValueError("Manifest rows must have exactly an address and import ID")
        address, import_id = fields
        if address not in expected or address in seen:
            raise ValueError(f"Unknown or duplicate manifest resource: {address}")
        seen.add(address)
        rows.append((address, import_id))
    if seen != set(expected):
        raise ValueError("Manifest must match all YAML-owned resource addresses")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        rows = read_manifest(args.manifest, ownership(args.cluster_dir))
    except (KeyError, OSError, TypeError, ValueError, yaml.YAMLError) as error:
        parser.error(str(error))
    print(f"Manifest validated: {len(rows)} YAML-owned resources")


if __name__ == "__main__":
    main()
