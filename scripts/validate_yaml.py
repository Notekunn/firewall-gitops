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
