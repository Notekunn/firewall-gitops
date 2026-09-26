# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Firewall GitOps: A YAML-to-Terraform automation system for managing firewall configurations across multiple vendors. Network engineers write YAML files defining firewall rules, addresses, and services, which are automatically transformed into Terraform resources and deployed via GitLab CI/CD.

**Supported Firewalls:**
- Palo Alto Networks (PAN-OS) - Panorama and standalone NGFW
- Check Point - Management Server with policy layers
- Fortinet - Terraform module WIP; `open_rule` dry-run supports L3 matching

**SOAR Integration:**
- Webhook service for automated threat response (Phase 01 complete)
- Receives security alerts from SOAR platforms
- Automatically updates firewall blocklists via GitOps workflow

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

### Ticket-Driven Rule Opener
```bash
# Decision-only dry run; no writes, no network, no Terraform apply
PYTHONPATH=. python3 -m scripts.open_rule examples/flows.json
PYTHONPATH=. python3 -m scripts.open_rule examples/flows.json --format json
```

`scripts/open_rule/` resolves flow tickets against `topology.yaml`, computes the directed multi-firewall path, and emits one verdict per hop. PAN-OS and FortiGate use the L3 matcher; F5 WAF returns `MANUAL_F5`. Generated YAML is advisory and must be checked for assumed path/routing/NAT and deny placement caveats.

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
modules/checkpoint/
├── main.tf                    # CheckPoint provider resources
└── variables.tf               # Variable definitions
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

## Firewall-Specific Implementation Details

### Palo Alto Networks (PAN-OS)

**Location Context:**
Determined from `cluster.yaml` firewall configuration:
- **Panorama mode**: Requires `device_group`, optional `panorama_device` (default: "localhost.localdomain") and `rulebase` (default: "pre-rulebase")
- **Standalone mode**: Requires `ngfw_device` (default: "localhost.localdomain") and `vsys_name` (default: "vsys1")

**Resource Types:**
- `panos_addresses`: Unified address objects supporting ip_netmask, ip_range, ip_wildcard, fqdn
- `panos_service`: TCP/UDP service objects
- `panos_security_policy_rules`: Firewall rules with security profiles

**Provider Configuration:**
Environment variables: `PANOS_HOSTNAME`, `PANOS_USERNAME`, `PANOS_PASSWORD` (or `PANOS_API_KEY`)

### Check Point

**Location Context:**
- **Domain**: Optional management domain for Multi-Domain Security Management (MDSM)
- **Layer**: Access policy layer (default: "Network")

**Resource Types:**
- `checkpoint_management_host`: Single IP addresses (/32) and FQDNs
- `checkpoint_management_network`: Network subnets (anything except /32)
- `checkpoint_management_service_tcp`: TCP service objects
- `checkpoint_management_service_udp`: UDP service objects
- `checkpoint_management_access_rule`: Firewall rules
- `checkpoint_management_publish`: Publishes changes to the management database

**Key Differences from PAN-OS:**
1. Separate host and network resources (module automatically classifies based on CIDR)
2. Requires explicit publish after changes (controlled by `auto_publish` setting)
3. Uses "layers" for policy organization
4. Rule positioning uses common YAML values (`first`, `last`, `after`, `before`) and maps them to CheckPoint provider values internally.

**Provider Configuration:**
Environment variables: `CHECKPOINT_SERVER`, `CHECKPOINT_USERNAME`, `CHECKPOINT_PASSWORD`, `CHECKPOINT_CONTEXT`

**Auto-Publish:**
The CheckPoint module includes automatic change publishing when `auto_publish: true` (default). The publish resource triggers on any changes to hosts, networks, services, or rules.

## Key Implementation Details

### Positioning Configuration

Rules are positioned relative to existing firewall rules (`terraform/main.tf:83-87`):
- PAN-OS/FortiGate/F5 YAML: `where` values - "first", "last", "after", "before"
- CheckPoint module maps those to provider values: first→top, last→bottom, after→below, before→above
- `pivot`: Reference rule name (required for positional placement)
- `directly`: Boolean for exact vs. generic placement

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

## Provider Configurations

### PAN-OS Provider
Configuration in `terraform/main.tf:91`. Environment variables:
- `PANOS_HOSTNAME`, `PANOS_USERNAME`, `PANOS_PASSWORD` (or `PANOS_API_KEY`)
- `PANOS_SKIP_VERIFY_CERTIFICATE`: Default `true`

### CheckPoint Provider
Configuration in `terraform/main.tf:94`. Environment variables:
- `CHECKPOINT_SERVER`, `CHECKPOINT_USERNAME`, `CHECKPOINT_PASSWORD`
- `CHECKPOINT_CONTEXT`: Management domain context (use `web_api` for default)
- `CHECKPOINT_TIMEOUT`: Connection timeout (default: 120 seconds)

## SOAR Webhook Service

### Overview
Location: `scripts/webhook-soar/`

A Go-based microservice for automated threat response that integrates SOAR platforms with the Firewall GitOps workflow. The service receives security alerts via HTTP webhooks and automatically updates firewall configurations.

### Phase 01 Implementation (Complete)

**Project Structure:**
```
scripts/webhook-soar/
├── cmd/webhook/main.go          # Application entry point
├── internal/
│   └── config/
│       ├── config.go            # Configuration management
│       └── config_test.go       # Unit tests
├── go.mod                       # Go module: firewall-gitops/webhook-soar
└── README.md                    # Service documentation
```

### Ticket Rule Opener Structure

```
scripts/open_rule/
├── netutils.py       # IPv4/port parsing
├── topology.py       # topology.yaml loader and segment resolver
├── path.py           # directed path finder
├── loader.py         # cluster YAML loader
├── objects.py        # object reuse/staging
├── matcher.py        # per-firewall verdict logic
├── orchestrator.py   # per-ticket multi-hop flow processing
├── render.py         # text/json output
├── cli.py            # CLI
├── matcher_*.py      # matcher internals
├── object_*.py       # object internals
└── orchestrator_*.py # orchestration internals
```

**Configuration:**
Environment variables for all settings:
```bash
# Required
GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
GITLAB_PROJECT_ID="123"
REPO_CLONE_URL="https://gitlab.example.com/your-org/firewall-configs.git"

# Optional (with defaults)
GITLAB_URL="https://gitlab.com"
TARGET_CLUSTER="production"
YAML_FILE_PATH="clusters/production/objects.yaml"
OBJECT_PATH="ip_lists.global.blocklist"
SERVER_PORT="8080"
```

**Build and Run:**
```bash
cd scripts/webhook-soar
go build -o webhook ./cmd/webhook
export GITLAB_TOKEN="your-token"
export GITLAB_PROJECT_ID="123"
export REPO_CLONE_URL="https://gitlab.example.com/repo.git"
./webhook
```

### Phase 02-05 (Planned)
- GitLab API integration for repository operations
- YAML processing for IP list updates
- HTTP webhook handlers for SOAR platforms
- Testing and deployment automation

### Integration Flow
```
SOAR Alert → HTTP POST → Webhook Service → Git Operations → CI/CD Pipeline → Firewall Update
```

## Security Requirements

From AGENTS.md:

- **Never commit**: API keys, passwords, tokens, certificates
- **Environment variables**: `GITLAB_TOKEN`, `PANOS_API_KEY`, `PANOS_PASSWORD`, `CHECKPOINT_PASSWORD`
- **GitLab CI/CD**: Store secrets in project CI/CD variables
- **PAN-OS Partial Commits**: `scripts/commit.sh` uses per-admin partial commits to avoid overwriting other administrators' configurations
- **SOAR Webhook**: Use `WEBHOOK_SECRET` for signature validation (Phase 02)
