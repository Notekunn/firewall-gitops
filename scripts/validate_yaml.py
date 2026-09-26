#!/usr/bin/env python3
"""
YAML Configuration Validator for Firewall GitOps

This script validates YAML configuration files for syntax and schema compliance.
"""

import os
import sys
import yaml
import glob
import json
from pathlib import Path
import jsonschema
from jsonschema import validate, ValidationError
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def load_schema(schema_file):
    """Load JSON schema from file"""
    try:
        schema_path = Path(__file__).parent.parent / "schemas" / schema_file
        with open(schema_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Schema file not found: {schema_file}")
        return None
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in schema file {schema_file}: {e}")
        return None

# Load schemas from external files
CLUSTER_CONFIG_SCHEMA = load_schema("cluster.schema.json")
FIREWALL_RULES_SCHEMA = load_schema("rules.schema.json")


def validate_yaml_syntax(file_path):
    """Validate YAML syntax"""
    try:
        with open(file_path, 'r') as file:
            yaml.safe_load(file)
        return True, None
    except yaml.YAMLError as e:
        return False, str(e)

def validate_schema(data, schema, file_path):
    """Validate data against JSON schema"""
    try:
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, f"Schema validation error in {file_path}: {e.message}"

def find_yaml_files():
    """Find all YAML configuration files"""
    cluster_configs = glob.glob("clusters/*/cluster.yaml")

    # Find firewall objects - support both single file and multiple files in objects/ folder
    firewall_objects = []

    # Find all cluster directories
    cluster_dirs = glob.glob("clusters/*")

    for cluster_dir in cluster_dirs:
        if not os.path.isdir(cluster_dir):
            continue

        # Check for single objects.yaml file
        single_objects_file = os.path.join(cluster_dir, "objects.yaml")
        if os.path.exists(single_objects_file):
            firewall_objects.append(single_objects_file)

        # Check for objects/ folder with multiple YAML files
        objects_folder = os.path.join(cluster_dir, "objects")
        if os.path.isdir(objects_folder):
            objects_files = glob.glob(os.path.join(objects_folder, "*.yaml"))
            firewall_objects.extend(objects_files)

    return cluster_configs, firewall_objects

def validate_cluster_references(cluster_configs, firewall_objects):
    """Validate that cluster configurations have corresponding firewall objects"""
    errors = []

    cluster_dirs = set(os.path.dirname(config) for config in cluster_configs)

    # Get unique cluster directories that have objects
    # Objects can be either in objects.yaml or in objects/ folder
    objects_dirs = set()
    for objects_path in firewall_objects:
        # Handle both objects.yaml and objects/*.yaml
        if objects_path.endswith("objects.yaml"):
            objects_dirs.add(os.path.dirname(objects_path))
        else:
            # This is a file in objects/ folder, go up one level
            objects_dirs.add(os.path.dirname(os.path.dirname(objects_path)))

    # Check for missing firewall objects
    missing_objects = cluster_dirs - objects_dirs
    if missing_objects:
        for missing in missing_objects:
            errors.append(f"Missing objects configuration (objects.yaml or objects/ folder) for cluster: {missing}")

    # Check for orphaned firewall objects
    orphaned_objects = objects_dirs - cluster_dirs
    if orphaned_objects:
        for orphaned in orphaned_objects:
            errors.append(f"Orphaned objects configuration without cluster.yaml: {orphaned}")

    return errors


def load_cluster_objects(cluster_dir):
    """Load object files in the same deterministic order as OpenTofu."""
    paths = []
    single = os.path.join(cluster_dir, "objects.yaml")
    if os.path.exists(single):
        paths.append(single)
    paths.extend(sorted(glob.glob(os.path.join(cluster_dir, "objects", "*.yaml"))))
    documents = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as file:
            documents.append((path, yaml.safe_load(file) or {}))
    return documents


def validate_merged_cluster(cluster_config_path):
    """Validate ownership and references after all object files are merged."""
    errors = []
    cluster_dir = os.path.dirname(cluster_config_path)
    with open(cluster_config_path, "r", encoding="utf-8") as file:
        cluster = yaml.safe_load(file) or {}

    timezone_name = cluster.get("global", {}).get("timezone", "Asia/Bangkok")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        errors.append(f"Invalid global.timezone in {cluster_config_path}: {timezone_name}")

    merged = {key: [] for key in ("addresses", "services", "rules", "schedules")}
    for _, document in load_cluster_objects(cluster_dir):
        for key in merged:
            merged[key].extend(document.get(key, []))

    for kind, items in merged.items():
        seen = set()
        for item in items:
            name = item.get("name")
            if name in seen:
                singular = "address" if kind == "addresses" else kind[:-1]
                errors.append(f"Duplicate {singular} name in {cluster_dir}: {name}")
            seen.add(name)

    schedule_names = {item.get("name") for item in merged["schedules"]}
    schedules_by_name = {item.get("name"): item for item in merged["schedules"]}
    vendor = cluster.get("firewall", {}).get("type")
    if vendor == "fortinet":
        for schedule in merged["schedules"]:
            schedule_type = schedule.get("schedule_type", {})
            ranges = schedule_type.get("non_recurring") or schedule_type.get("recurring", {}).get("daily")
            weekly = schedule_type.get("recurring", {}).get("weekly", {})
            weekly_ranges = {value for values in weekly.values() for value in values}
            if ranges is not None and len(ranges) != 1:
                errors.append(f"FortiGate schedule {schedule.get('name')} in {cluster_dir} must contain exactly one time range")
            if weekly and len(weekly_ranges) != 1:
                errors.append(f"FortiGate weekly schedule {schedule.get('name')} in {cluster_dir} must use one shared time range")
    for rule in merged["rules"]:
        schedule = rule.get("schedule")
        if schedule and schedule not in schedule_names and schedule != "always":
            errors.append(f"Rule {rule.get('name')} in {cluster_dir} references missing schedule: {schedule}")
        expires_at = rule.get("expires_at")
        if expires_at:
            try:
                datetime.fromisoformat(expires_at)
            except ValueError:
                errors.append(f"Rule {rule.get('name')} in {cluster_dir} has invalid expires_at: {expires_at}")
            if vendor == "palo-alto":
                schedule_data = schedules_by_name.get(schedule, {}).get("schedule_type", {})
                if not schedule or not schedule_data.get("non_recurring"):
                    errors.append(f"PAN-OS rule {rule.get('name')} in {cluster_dir} requires a non-recurring schedule when expires_at is set")

    return errors

def main():
    """Main validation function"""
    print("Starting YAML configuration validation...")
    
    # Change to project root directory
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent
    os.chdir(project_root)
    
    # Check if schemas are loaded
    if CLUSTER_CONFIG_SCHEMA is None or FIREWALL_RULES_SCHEMA is None:
        print("❌ Failed to load JSON schemas")
        return 1
    
    errors = []
    warnings = []
    
    # Find all YAML files
    cluster_configs, firewall_objects = find_yaml_files()

    if not cluster_configs and not firewall_objects:
        print("No YAML configuration files found.")
        return 0

    print(f"Found {len(cluster_configs)} cluster configs and {len(firewall_objects)} firewall object files")

    # Validate cluster configuration files
    for config_file in cluster_configs:
        print(f"Validating {config_file}...")

        # Check YAML syntax
        is_valid, error = validate_yaml_syntax(config_file)
        if not is_valid:
            errors.append(f"YAML syntax error in {config_file}: {error}")
            continue

        # Load and validate schema
        with open(config_file, 'r') as file:
            data = yaml.safe_load(file)

        is_valid, error = validate_schema(data, CLUSTER_CONFIG_SCHEMA, config_file)
        if not is_valid:
            errors.append(error)

    # Validate firewall objects files
    for objects_file in firewall_objects:
        print(f"Validating {objects_file}...")

        # Check YAML syntax
        is_valid, error = validate_yaml_syntax(objects_file)
        if not is_valid:
            errors.append(f"YAML syntax error in {objects_file}: {error}")
            continue

        # Load and validate schema
        with open(objects_file, 'r') as file:
            data = yaml.safe_load(file)

        is_valid, error = validate_schema(data, FIREWALL_RULES_SCHEMA, objects_file)
        if not is_valid:
            errors.append(error)

    # Validate cluster references
    ref_errors = validate_cluster_references(cluster_configs, firewall_objects)
    errors.extend(ref_errors)
    for config_file in cluster_configs:
        errors.extend(validate_merged_cluster(config_file))
    
    # Print results
    if errors:
        print("\n❌ Validation FAILED with the following errors:")
        for error in errors:
            print(f"  - {error}")
        return 1
    
    if warnings:
        print("\n⚠️  Validation completed with warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    print("\n✅ All YAML configurations are valid!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
