# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Firewall GitOps: A YAML-to-Terraform automation system for managing Palo Alto Networks firewall configurations. Network engineers write YAML files defining firewall rules, addresses, and services, which are automatically transformed into Terraform resources and deployed via GitLab CI/CD.

## Core Architecture

### Data Flow: YAML → Terraform → PAN-OS

1. **YAML Configuration** (`clusters/<cluster>/`)
   - `cluster.yaml`: Firewall connection details, positioning strategy, log settings
   - `objects.yaml`: Single file with addresses, services, rules (Option 1)
   - `objects/*.yaml`: Multiple files automatically merged (Option 2)

2. **YAML Parser** (`terraform/main.tf` lines 12-79)
   - Reads cluster configuration using `yamldecode()`
   - Detects single-file vs multi-file mode (lines 24-25)
   - Merges all addresses/services/rules from multiple sources (lines 38-50)
   - Produces three unified lists: `local.firewall_addresses`, `local.firewall_services`, `local.firewall_rules`

3. **Module Invocation** (`terraform/main.tf` lines 84-97)
   - Passes merged data to `modules/palo-alto/`
   - Includes location context (Panorama device_group OR standalone vsys)
   - Includes positioning config (where/pivot/directly)

4. **PAN-OS Provider Resources** (`modules/palo-alto/main.tf`)
   - `panos_addresses`: Creates address objects (line 14)
   - `panos_service`: Creates service objects (line 28)
   - `panos_security_policy_rules`: Creates firewall rules with explicit dependencies (line 43)

### Multi-File Merging Logic

The system automatically merges YAML files from `clusters/<cluster>/objects/*.yaml`:

```hcl
# terraform/main.tf:32-50
objects_files = fileset("${local.cluster_dir}/objects", "*.yaml")
objects_data_list = [for f in objects_files : yamldecode(file("..."))]

# Flatten and concatenate addresses from all files
addresses_from_multi = flatten([for data in objects_data_list : try(data.addresses, [])])
firewall_addresses = concat(addresses_from_single, addresses_from_multi)
```

This means each YAML file can contain any combination of addresses, services, and rules. Terraform will merge them all before creating resources.

### State Management

Each cluster maintains independent state in GitLab using HTTP backend (`terraform/main.tf:8`). State naming pattern: `firewall-gitops-{cluster_name}`. This enables parallel deployments of multiple clusters without state conflicts.

## Common Commands

### Setup
```bash
# Create Python virtual environment and install validation dependencies
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

### Validation
```bash
# Validate all cluster YAML files against JSON schemas
python scripts/validate_yaml.py

# Format Terraform files
terraform fmt -recursive

# Check formatting without changes
terraform fmt -check
```

### Local Development
```bash
# Required environment variables for GitLab state backend
export GITLAB_TOKEN="your-personal-access-token"
export GITLAB_API_URL="https://gitlab.com/api/v4"
export GITLAB_USERNAME="your-gitlab-username"

# Required for PAN-OS provider authentication
export PANOS_HOSTNAME="firewall.example.com"
export PANOS_USERNAME="admin"
export PANOS_PASSWORD="password"  # OR use PANOS_API_KEY

# Deployment workflow
./scripts/deploy.sh -c <cluster> -a plan      # Create Terraform plan
./scripts/deploy.sh -c <cluster> -a plan -d   # Plan with debug output
./scripts/deploy.sh -c <cluster> -a apply -y  # Apply changes
./scripts/deploy.sh -c <cluster> -a validate  # Validate Terraform config
```

### PAN-OS Commit
```bash
# Commit changes to PAN-OS (uses partial commits per-admin)
./scripts/commit.sh
```

## File Organization

**Cluster Configurations:**
```
clusters/<cluster-name>/
├── cluster.yaml        # Firewall type, connection, positioning, log settings
└── objects.yaml        # Single file (backward compatible)
    OR
└── objects/            # Multiple files (recommended for large configs)
    ├── addresses.yaml
    ├── services.yaml
    ├── trust-zone.yaml
    └── *.yaml          # All .yaml files automatically merged
```

**Terraform Modules:**
```
terraform/main.tf              # YAML parsing, merging, module invocation
modules/palo-alto/
├── main.tf                    # PAN-OS provider resources
└── variables.tf               # Variable definitions (source for schema generation)
modules/fortinet/              # Planned future support
```

## GitLab CI/CD Pipeline

**Stages:** validate → plan → apply → cleanup

**Validation Stage:**
- `validate_yaml`: Schema validation for all cluster YAML
- `terraform_fmt_*`: Format checking per cluster
- `terraform_validate_*`: Terraform validation per cluster
- `security_scan`: Checkov security scanning (allow_failure: true)

**Plan Stage:**
- `plan_example`, `plan_development`, `plan_production`: Creates plans for changed clusters
- Triggered by changes to cluster YAML or Terraform files
- Artifacts: `plan-*.tfplan` and `plan-*.json` (1 week retention)

**Apply Stage:**
- `apply_example`, `apply_development`: Auto-applies after successful plan
- `apply_production`: Requires manual approval gate (`approve_production` job)

**Resource Groups:**
Each cluster uses `resource_group: terraform-$CLUSTER_NAME` to prevent concurrent modifications to the same cluster while allowing parallel deployments across different clusters.

## Coding Conventions

From AGENTS.md:

**Terraform:**
- Two-space indentation, `terraform fmt` enforced
- Snake_case for variables/outputs
- Always run `terraform fmt -recursive` before commits

**YAML:**
- Two-space indentation
- Single quotes for strings with special characters
- Meaningful names: `web_access` (rule groups), `web-server-01` (objects)
- Exact file names: `cluster.yaml` and `objects.yaml` (or `objects/*.yaml`)

**Python:**
- PEP 8, four-space indentation
- Pure functions preferred
- CLI entry points: `if __name__ == "__main__":`

**Commits:**
- Conventional Commits: `feat:`, `fix:`, `chore:`, `refactor:`
- Each commit should be atomic (one logical change)
- Link GitLab issues when relevant
- Include Terraform plan snippets in merge request descriptions

## Key Implementation Details

### Positioning Configuration

Rules are positioned relative to existing firewall rules (`terraform/main.tf:74-78`):
- `where`: "before", "after", "top", "bottom", "last" (default)
- `pivot`: Reference rule name (required for before/after)
- `directly`: Boolean for exact vs. generic placement

### Location Context

Determined from `cluster.yaml` firewall configuration:
- **Panorama mode**: Requires `device_group`, optional `panorama_device` (default: "localhost.localdomain") and `rulebase` (default: "pre-rulebase")
- **Standalone mode**: Requires `ngfw_device` (default: "localhost.localdomain") and `vsys_name` (default: "vsys1")

### Resource Dependencies

`panos_security_policy_rules` has explicit dependencies (`modules/palo-alto/main.tf:46`):
```hcl
depends_on = [panos_addresses.address_objects, panos_service.service_objects]
```

This ensures address and service objects exist before rules reference them.

### Log and Security Profiles

- **Global log setting**: Applied from `cluster.yaml` via `log_setting` parameter
- **Per-rule logging**: Override with `log_start` and `log_end` booleans
- **Security profiles**: Configure via `profile_setting` with either `group` (profile group name) or `profiles` (individual profile names: virus, spyware, vulnerability, url_filtering, file_blocking, wildfire_analysis, data_filtering)

### Null Handling

Modules use `lookup()` and `try()` for optional YAML fields:
```hcl
ip_netmask = lookup(addr, "ip_netmask", null)
```

This handles YAML omissions gracefully without errors.

## Debugging YAML Merge Issues

Use Terraform console to inspect merged data:

```bash
cd terraform
terraform init -backend-config="address=$GITLAB_API_URL/projects/$GITLAB_PROJECT_ID/terraform/state/firewall-gitops-<cluster>"
terraform console
> local.firewall_addresses
> local.firewall_services
> local.firewall_rules
```

Check outputs in `terraform/main.tf:110-118` to verify merged results.

## Security Requirements

From AGENTS.md:

- **Never commit**: API keys, passwords, tokens, certificates
- **Environment variables**: `GITLAB_TOKEN`, `PANOS_API_KEY`, `PANOS_PASSWORD`
- **GitLab CI/CD**: Store secrets in project CI/CD variables
- **PAN-OS Partial Commits**: `scripts/commit.sh` uses per-admin partial commits to avoid overwriting other administrators' configurations
