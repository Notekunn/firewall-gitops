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
CLUSTER_CONFIG_SCHEMA = load_schema("cluster-config.schema.json")
FIREWALL_RULES_SCHEMA = load_schema("firewall-rules.schema.json")


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
    cluster_configs = glob.glob("clusters/*/cluster-config.yaml")
    firewall_rules = glob.glob("clusters/*/firewall-rules.yaml")
    
    return cluster_configs, firewall_rules

def validate_cluster_references(cluster_configs, firewall_rules):
    """Validate that cluster configurations have corresponding firewall rules"""
    errors = []
    
    cluster_dirs = set(os.path.dirname(config) for config in cluster_configs)
    rules_dirs = set(os.path.dirname(rules) for rules in firewall_rules)
    
    # Check for missing firewall rules
    missing_rules = cluster_dirs - rules_dirs
    if missing_rules:
        for missing in missing_rules:
            errors.append(f"Missing firewall-rules.yaml for cluster: {missing}")
    
    # Check for orphaned firewall rules
    orphaned_rules = rules_dirs - cluster_dirs
    if orphaned_rules:
        for orphaned in orphaned_rules:
            errors.append(f"Orphaned firewall-rules.yaml without cluster-config.yaml: {orphaned}")
    
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
    cluster_configs, firewall_rules = find_yaml_files()
    
    if not cluster_configs and not firewall_rules:
        print("No YAML configuration files found.")
        return 0
    
    print(f"Found {len(cluster_configs)} cluster configs and {len(firewall_rules)} firewall rule files")
    
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
    
    # Validate firewall rules files
    for rules_file in firewall_rules:
        print(f"Validating {rules_file}...")
        
        # Check YAML syntax
        is_valid, error = validate_yaml_syntax(rules_file)
        if not is_valid:
            errors.append(f"YAML syntax error in {rules_file}: {error}")
            continue
        
        # Load and validate schema
        with open(rules_file, 'r') as file:
            data = yaml.safe_load(file)
        
        is_valid, error = validate_schema(data, FIREWALL_RULES_SCHEMA, rules_file)
        if not is_valid:
            errors.append(error)
    
    # Validate cluster references
    ref_errors = validate_cluster_references(cluster_configs, firewall_rules)
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
