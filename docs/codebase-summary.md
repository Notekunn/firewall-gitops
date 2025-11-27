# Codebase Summary

## Overview

**Repository:** firewall-gitops
**Purpose:** GitOps automation for multi-vendor firewall management using YAML → Terraform pipeline
**Architecture:** Modular Terraform with vendor-specific implementations
**CI/CD:** GitLab pipelines with 4 stages (validate → plan → apply → cleanup)

---

## Directory Structure

```
firewall-gitops/
├── clusters/               # Per-cluster YAML configurations
│   ├── example/           # Example cluster (PAN-OS standalone)
│   ├── development/       # Development cluster (CheckPoint)
│   └── production/        # Production cluster (PAN-OS Panorama)
├── docs/                  # Project documentation
├── modules/               # Vendor-specific Terraform modules
│   ├── checkpoint/       # CheckPoint Management Server module
│   ├── f5-waf/          # F5 BIG-IP WAF module
│   ├── fortinet/        # Fortinet FortiGate module (WIP)
│   └── palo-alto/       # Palo Alto Networks (PAN-OS) module
├── schemas/              # JSON schemas for YAML validation
│   ├── cluster.schema.json
│   └── rules.schema.json
├── scripts/              # Automation scripts
│   ├── commit.sh        # PAN-OS commit script (partial commits)
│   ├── deploy.sh        # Local deployment wrapper
│   └── validate_yaml.py # YAML validation against schemas
├── terraform/            # Main Terraform orchestration
│   ├── main.tf          # YAML parser, conditional module execution
│   └── variables.tf     # Global variables
├── .gitlab-ci.yml       # CI/CD pipeline definition
├── CLAUDE.md            # Project guide for Claude Code
├── README.md            # User-facing documentation
└── requirements.txt     # Python dependencies
```

---

## Key Files

### Root Configuration

#### `.gitlab-ci.yml` (305 lines)
**Purpose:** GitLab CI/CD pipeline orchestration

**Stages:**
1. **validate** - Schema validation, Terraform fmt/validate, Checkov security scan
2. **plan** - Generate Terraform plans for changed clusters
3. **apply** - Deploy changes (auto for dev/staging, manual approval for prod)
4. **cleanup** - Remove old artifacts

**Key Features:**
- Dynamic job generation per cluster (example, development, production)
- Resource groups prevent concurrent cluster modifications
- Artifact retention (plans stored 1 week)
- Conditional execution based on file changes

**Critical Jobs:**
```yaml
validate_yaml:
  - python scripts/validate_yaml.py

terraform_fmt_<cluster>:
  - terraform fmt -check -recursive

plan_<cluster>:
  - terraform plan -out=plan-<cluster>.tfplan

apply_<cluster>:
  - terraform apply plan-<cluster>.tfplan
```

#### `CLAUDE.md` (280 lines)
**Purpose:** Comprehensive project guide for Claude Code AI agent

**Sections:**
- Project overview and architecture
- Data flow: YAML → Terraform → Firewall
- Multi-file merging logic
- Common commands (setup, validation, deployment)
- File organization patterns
- Coding conventions
- Debugging instructions

**Key Insight:** Acts as single source of truth for AI-assisted development

#### `README.md` (456 lines)
**Purpose:** User-facing documentation

**Contents:**
- Quick start guide
- Configuration examples (single-file vs multi-file)
- Requirements and setup
- GitOps workflow
- Provider configuration (PAN-OS, CheckPoint, F5)
- State management explanation

---

### Terraform Orchestration

#### `terraform/main.tf` (190 lines)
**Purpose:** Central orchestration layer - YAML parsing, merging, conditional module execution

**Key Sections:**

**1. YAML Parser (lines 20-109)**
```hcl
# Auto-detect single file (objects.yaml) vs multi-file (objects/*.yaml)
has_single_objects_file = fileexists("${local.cluster_dir}/objects.yaml")
has_objects_folder = try(length(fileset("${local.cluster_dir}/objects", "*.yaml")) > 0, false)

# Merge addresses from all sources
firewall_addresses = concat(addresses_from_single, addresses_from_multi)
```

**Critical Logic:**
- Reads `cluster.yaml` for firewall type and connection details
- Detects single-file or multi-file mode automatically
- Flattens and merges addresses/services/rules from multiple YAML files
- Produces unified lists: `local.firewall_addresses`, `local.firewall_services`, `local.firewall_rules`

**2. Location Context (lines 64-109)**
```hcl
# PAN-OS: Panorama vs Standalone
is_panorama = can(local.firewall_config.panorama)
panorama_config = { device_group, panorama_device, rulebase }
standalone_config = { ngfw_device, vsys_name }

# CheckPoint: Domain and Layer
checkpoint_location_config = { domain }

# F5: Partition
f5_location_config = { partition }
```

**3. Conditional Module Execution (lines 120-180)**
```hcl
module "palo_alto_firewall" {
  count = local.firewall_config.type == "palo-alto" ? 1 : 0
  source = "../modules/palo-alto"
  # ... pass merged data
}

module "checkpoint_firewall" {
  count = local.firewall_config.type == "checkpoint" ? 1 : 0
  source = "../modules/checkpoint"
  # ... pass merged data
}

module "f5_waf" {
  count = local.firewall_config.type == "f5-waf" ? 1 : 0
  source = "../modules/f5-waf"
  # ... pass IP lists
}
```

**Why This Matters:** Single entry point for all firewall types; vendor selection via YAML config

#### `terraform/variables.tf` (20 lines)
**Purpose:** Global variable definitions

```hcl
variable "cluster_name" {
  description = "Name of the cluster to deploy"
  type        = string
  default     = ""
}
```

---

### Vendor Modules

#### `modules/palo-alto/main.tf` (120 lines)
**Purpose:** PAN-OS resource creation via `paloaltonetworks/panos` provider

**Resources:**
1. **Address Objects** (`panos_addresses`, line 14)
   - Supports: `ip_netmask`, `ip_range`, `ip_wildcard`, `fqdn`
   - Uses `lookup()` for optional fields

2. **Service Objects** (`panos_service`, line 28)
   - TCP/UDP services with source/destination ports

3. **Security Policy Rules** (`panos_security_policy_rules`, line 43)
   - Depends on addresses and services (explicit `depends_on`)
   - Supports security profile groups and individual profiles
   - Log settings per-rule or global

4. **Log Forwarding Profiles** (Phase 1 Complete, Phase 2 In Progress)
   - Variable: `log_forwarding_profiles` (defined in `variables.tf` lines 101-127)
   - Schema: Validated in `schemas/cluster.schema.json` lines 134-224
   - Supports 8 log types: traffic, threat, wildfire, url, data, tunnel, auth, decryption
   - Destinations: syslog, email, HTTP, SNMP, Panorama
   - **Phase 1:** Schema and variable definitions ✅ Complete
   - **Phase 2:** YAML parser integration (planned)

**Key Pattern:**
```hcl
resource "panos_addresses" "address_objects" {
  for_each = { for addr in var.firewall_addresses : addr.name => addr }

  name = each.value.name
  ip_netmask = lookup(each.value, "ip_netmask", null)
  ip_range = lookup(each.value, "ip_range", null)
  # ... handle all address types with null defaults
}
```

**Location Handling:**
```hcl
device_group = try(var.location.panorama.device_group, null)
vsys = try(var.location.vsys.vsys_name, null)
```

#### `modules/palo-alto/variables.tf` (180 lines)
**Purpose:** Variable definitions - source for JSON schema generation

**Critical Variables:**
```hcl
variable "firewall_addresses" {
  type = list(object({
    name = string
    ip_netmask = optional(string)
    ip_range = optional(string)
    ip_wildcard = optional(string)
    fqdn = optional(string)
    description = optional(string)
    tags = optional(list(string))
  }))
}

variable "firewall_rules" {
  type = list(object({
    name = string
    source_zones = list(string)
    destination_zones = list(string)
    # ... 20+ optional fields
  }))
}
```

**Schema Generation:** These type definitions drive `schemas/rules.schema.json`

#### `modules/checkpoint/main.tf` (180 lines)
**Purpose:** CheckPoint resource creation via `CheckPointSW/checkpoint` provider

**Key Differences from PAN-OS:**

1. **Host vs Network Classification (lines 15-25)**
```hcl
locals {
  # Separate /32 addresses (hosts) from subnets (networks)
  host_addresses = [for addr in var.firewall_addresses : addr if can(regex("/32$", addr.ip_netmask))]
  network_addresses = [for addr in var.firewall_addresses : addr if !can(regex("/32$", addr.ip_netmask))]
}
```

2. **Separate Resources**
- `checkpoint_management_host` for /32 and FQDNs
- `checkpoint_management_network` for subnets
- `checkpoint_management_service_tcp` and `_udp` (separate resources)

3. **Automatic Publish (lines 160-175)**
```hcl
resource "checkpoint_management_publish" "publish" {
  count = var.global.auto_publish ? 1 : 0
  depends_on = [
    checkpoint_management_host.host_objects,
    checkpoint_management_network.network_objects,
    checkpoint_management_service_tcp.tcp_services,
    checkpoint_management_service_udp.udp_services,
    checkpoint_management_access_rule.rules
  ]
}
```

**Why Publish Matters:** CheckPoint requires explicit publish to commit changes to management database

#### `modules/checkpoint/variables.tf` (220 lines)
**Purpose:** CheckPoint-specific variable definitions

**Additional Variables:**
```hcl
variable "global" {
  type = object({
    layer_name = string
    auto_publish = bool
    install_on = list(string)
    track_type = string
    track_settings = object({
      accounting = bool
      alert = string
      enable_firewall_session = bool
      per_connection = bool
      per_session = bool
    })
  })
}
```

#### `modules/f5-waf/main.tf` (85 lines)
**Purpose:** F5 BIG-IP WAF configuration via `F5Networks/bigip` provider

**Resources:**
1. **IP Lists** (`bigip_waf_ip_list`, line 12)
   - Allow/block lists with descriptions
   - Supports multiple IPs per list

2. **iRule** (`bigip_ltm_irule`, line 28)
   - Custom Tcl-based traffic filtering
   - References IP lists by name
   - Applied to virtual servers

**Key Pattern:**
```hcl
resource "bigip_waf_ip_list" "ip_lists" {
  for_each = var.ip_lists

  name = "/Common/${each.key}"
  description = lookup(each.value, "description", "")
  ip_addresses = jsonencode([for ip in each.value.addresses : { "ip_address": ip }])
}
```

#### `modules/fortinet/main.tf` (100 lines)
**Purpose:** Fortinet FortiGate module (Work in Progress)

**Status:** Placeholder implementation - not yet functional

**Planned Resources:**
- `fortimanager_object_firewall_address`
- `fortimanager_object_firewall_service_custom`
- `fortimanager_object_firewall_policy`

---

### Clusters (YAML Configurations)

#### `clusters/example/cluster.yaml` (35 lines)
**Purpose:** Example PAN-OS standalone configuration

```yaml
cluster:
  name: example
  environment: development

firewall:
  type: palo-alto
  standalone:
    ngfw_device: localhost.localdomain
    vsys_name: vsys1

position:
  where: last

log_setting: default-logging
```

#### `clusters/development/cluster.yaml` (30 lines)
**Purpose:** CheckPoint development environment

```yaml
firewall:
  type: checkpoint
  checkpoint:
    layer_name: Network
    auto_publish: true
    install_on:
      - Policy Targets
```

#### `clusters/production/cluster.yaml` (40 lines)
**Purpose:** PAN-OS Panorama production configuration

```yaml
firewall:
  type: palo-alto
  panorama:
    device_group: Production-DG
    panorama_device: localhost.localdomain
    rulebase: pre-rulebase

position:
  where: before
  pivot: default-deny-rule
  directly: true
```

#### Multi-File Configuration Example

**Option 1: Single File**
```
clusters/example/
└── objects.yaml  # Contains addresses, services, rules
```

**Option 2: Multiple Files (Recommended)**
```
clusters/development/
└── objects/
    ├── addresses.yaml       # Address objects only
    ├── services.yaml        # Service objects only
    ├── trust-zone.yaml      # Trust zone rules
    └── dmz-zone.yaml        # DMZ zone rules + zone-specific addresses
```

**Merging Logic:**
- Terraform reads all `.yaml` files from `objects/` directory
- Flattens addresses from all files into single list
- Flattens services from all files into single list
- Concatenates rules from all files

**Benefit:** Reduces merge conflicts when multiple engineers work on different zones

---

### Schemas (JSON Schema Validation)

#### `schemas/cluster.schema.json` (304 lines)
**Purpose:** Validates `cluster.yaml` structure

**Key Validations:**
- `firewall.type` enum: `palo-alto`, `checkpoint`, `fortinet`, `f5-waf`
- PAN-OS: Requires either `panorama` or `standalone` (mutually exclusive)
- **NEW:** `log_forwarding_profiles` with comprehensive validation:
  - Profile name validation (1-63 chars, alphanumeric/hyphens/underscores)
  - Log type enum validation (8 supported types)
  - Destination profile validation (syslog, email, HTTP, SNMP)
  - Required field enforcement and defaults
- CheckPoint: Requires `checkpoint` config with `layer_name`
- F5: Requires `f5` config with `partition`
- Position: `where`, `pivot`, `directly` fields

#### `schemas/rules.schema.json` (520 lines)
**Purpose:** Validates `objects.yaml` and `objects/*.yaml` files

**Schema Sections:**

1. **Addresses** (lines 15-80)
```json
{
  "type": "object",
  "required": ["name"],
  "properties": {
    "name": { "type": "string" },
    "ip_netmask": { "type": "string", "pattern": "^\\d{1,3}(\\.\\d{1,3}){3}/\\d{1,2}$" },
    "ip_range": { "type": "string", "pattern": "^\\d{1,3}(\\.\\d{1,3}){3}-\\d{1,3}(\\.\\d{1,3}){3}$" },
    "fqdn": { "type": "string" }
  },
  "oneOf": [
    { "required": ["ip_netmask"] },
    { "required": ["ip_range"] },
    { "required": ["fqdn"] },
    { "required": ["ip_wildcard"] }
  ]
}
```

2. **Services** (lines 85-140)
```json
{
  "type": "object",
  "required": ["name", "type", "destination_port"],
  "properties": {
    "name": { "type": "string" },
    "type": { "enum": ["tcp", "udp"] },
    "destination_port": { "type": "string", "pattern": "^\\d{1,5}(-\\d{1,5})?$" },
    "source_port": { "type": "string" }
  }
}
```

3. **Rules** (lines 145-520)
```json
{
  "type": "object",
  "required": ["name", "source_zones", "destination_zones", "action"],
  "properties": {
    "name": { "type": "string" },
    "source_zones": { "type": "array", "items": { "type": "string" } },
    "destination_zones": { "type": "array" },
    "source_addresses": { "type": "array", "default": ["any"] },
    "destination_addresses": { "type": "array", "default": ["any"] },
    "applications": { "type": "array", "default": ["any"] },
    "services": { "type": "array", "default": ["application-default"] },
    "action": { "enum": ["allow", "deny", "drop", "reset-client", "reset-server", "reset-both"] },
    "log_start": { "type": "boolean" },
    "log_end": { "type": "boolean" },
    "profile_setting": { "type": "object" }
  }
}
```

**Auto-Generation:** Schemas generated from Terraform `variables.tf` type definitions

---

### Scripts

#### `scripts/validate_yaml.py` (180 lines)
**Purpose:** YAML validation against JSON schemas

**Features:**
- Validates all clusters automatically
- Reports validation errors with line numbers
- Exits with non-zero code on failure (CI/CD integration)

**Usage:**
```bash
python scripts/validate_yaml.py
```

**Output:**
```
Validating clusters/example/cluster.yaml... ✓
Validating clusters/example/objects.yaml... ✓
Validating clusters/development/cluster.yaml... ✓
All validations passed!
```

#### `scripts/deploy.sh` (220 lines)
**Purpose:** Local deployment wrapper

**Features:**
- Sets up Terraform backend dynamically
- Supports multiple actions: `plan`, `apply`, `validate`, `destroy`
- Handles GitLab state backend configuration
- Debug mode for troubleshooting

**Usage:**
```bash
./scripts/deploy.sh -c <cluster> -a <action> [-y] [-d]

Options:
  -c  Cluster name (required)
  -a  Action: plan, apply, validate, destroy (required)
  -y  Auto-approve (skip confirmation)
  -d  Debug mode (verbose output)
```

**Example:**
```bash
export GITLAB_TOKEN="glpat-xxxxx"
./scripts/deploy.sh -c production -a plan
./scripts/deploy.sh -c production -a apply -y
```

#### `scripts/commit.sh` (80 lines)
**Purpose:** PAN-OS partial commit script

**Features:**
- Uses per-admin partial commits (avoids overwriting others' changes)
- Automatically detects Panorama vs standalone mode
- Handles commit errors gracefully

**Why Partial Commits:** In multi-admin environments, full commits would deploy ALL pending changes (including from other admins). Partial commits only deploy changes made by the current admin.

**Usage:**
```bash
export PANOS_HOSTNAME="panorama.example.com"
export PANOS_USERNAME="automation"
export PANOS_PASSWORD="password"

./scripts/commit.sh
```

---

## Configuration Patterns

### YAML Structure

**Cluster Configuration (`cluster.yaml`):**
```yaml
cluster:
  name: <cluster-name>
  environment: <dev|staging|prod>

firewall:
  type: <palo-alto|checkpoint|fortinet|f5-waf>

  # PAN-OS Panorama
  panorama:
    device_group: <device-group-name>
    panorama_device: localhost.localdomain
    rulebase: pre-rulebase

  # PAN-OS Standalone
  standalone:
    ngfw_device: localhost.localdomain
    vsys_name: vsys1

  # CheckPoint
  checkpoint:
    domain: <domain-name>  # Optional, for MDSM
    layer_name: Network
    auto_publish: true
    install_on: [Policy Targets]

  # F5 WAF
  f5:
    partition: Common
    irule_name: gitops_ip_filter

position:
  where: <first|last|after|before|top|bottom|above|below>
  pivot: <reference-rule-name>
  directly: <true|false>

log_setting: <log-forwarding-profile-name>
```

**Objects Configuration (`objects.yaml` or `objects/*.yaml`):**
```yaml
addresses:
  - name: web-server
    ip_netmask: 192.168.1.100/32
    description: Web server
    tags: [web, production]

services:
  - name: web-service
    type: tcp
    destination_port: '80'
    source_port: 1024-65535
    description: HTTP service

rules:
  - name: allow-web-traffic
    source_zones: [trust]
    destination_zones: [dmz]
    source_addresses: [any]
    destination_addresses: [web-server]
    applications: [web-browsing]
    services: [web-service]
    action: allow
    log_end: true
```

**F5 IP Lists Configuration:**
```yaml
ip_lists:
  whitelist-api:
    description: "API client whitelist"
    addresses:
      - 192.168.1.10
      - 192.168.1.20
      - 10.0.0.0/24

  blacklist-attackers:
    description: "Blocked malicious IPs"
    addresses:
      - 203.0.113.15
      - 198.51.100.42
```

---

## Dependencies

### External Providers

**Terraform Providers:**
```hcl
paloaltonetworks/panos ~> 2.0.5
CheckPointSW/checkpoint ~> 2.11.0
F5Networks/bigip ~> 1.24.0
```

**Provider Authentication:**
- PAN-OS: `PANOS_HOSTNAME`, `PANOS_USERNAME`, `PANOS_PASSWORD` (or `PANOS_API_KEY`)
- CheckPoint: `CHECKPOINT_SERVER`, `CHECKPOINT_USERNAME`, `CHECKPOINT_PASSWORD`, `CHECKPOINT_CONTEXT`
- F5: `BIGIP_HOST`, `BIGIP_USER`, `BIGIP_PASSWORD`

### Python Dependencies

**From `requirements.txt`:**
```
jsonschema>=4.17.0  # YAML validation
PyYAML>=6.0        # YAML parsing
```

### GitLab Requirements

- GitLab >= 15.0 (for HTTP backend and resource groups)
- Project access token with `api` scope
- CI/CD variables configured per environment

---

## Data Flow

### End-to-End Flow

```
1. Network Engineer writes YAML
   ↓
2. Git push to feature branch
   ↓
3. GitLab pipeline: validate stage
   - YAML schema validation (scripts/validate_yaml.py)
   - Terraform fmt check
   - Terraform validate
   - Checkov security scan
   ↓
4. GitLab pipeline: plan stage
   - terraform/main.tf reads cluster.yaml
   - Detects single-file vs multi-file mode
   - Merges all addresses/services/rules
   - Conditional module execution (based on firewall.type)
   - Generates Terraform plan
   - Stores plan artifact
   ↓
5. Merge request created
   - Security team reviews plan output
   - Approves MR
   ↓
6. Merge to main branch
   ↓
7. GitLab pipeline: apply stage
   - Production requires manual approval (approve_production job)
   - Terraform applies plan
   - Firewall provider creates resources:
     * PAN-OS: panos_addresses, panos_service, panos_security_policy_rules
     * CheckPoint: checkpoint_management_host/network, services, rules, publish
     * F5: bigip_waf_ip_list, bigip_ltm_irule
   ↓
8. Terraform state updated in GitLab HTTP backend
   ↓
9. (Optional) PAN-OS partial commit via scripts/commit.sh
```

---

## Module Interactions

### Terraform Module Hierarchy

```
terraform/main.tf (orchestrator)
  ↓
  ├─ modules/palo-alto/main.tf
  │   └─ Creates: panos_addresses, panos_service, panos_security_policy_rules
  │
  ├─ modules/checkpoint/main.tf
  │   └─ Creates: checkpoint_management_host, checkpoint_management_network,
  │                checkpoint_management_service_tcp/udp,
  │                checkpoint_management_access_rule,
  │                checkpoint_management_publish
  │
  ├─ modules/f5-waf/main.tf
  │   └─ Creates: bigip_waf_ip_list, bigip_ltm_irule
  │
  └─ modules/fortinet/main.tf (WIP)
      └─ Creates: TBD
```

### Conditional Execution

Only ONE module executes per cluster (determined by `firewall.type`):

```hcl
# terraform/main.tf
module "palo_alto_firewall" {
  count = local.firewall_config.type == "palo-alto" ? 1 : 0
  # ...
}

module "checkpoint_firewall" {
  count = local.firewall_config.type == "checkpoint" ? 1 : 0
  # ...
}
```

**Why:** Avoids provider conflicts; each cluster targets single firewall type

---

## State Management

### GitLab HTTP Backend

**Configuration:**
```hcl
terraform {
  backend "http" {}
}
```

**Runtime Configuration:**
```bash
terraform init \
  -backend-config="address=$GITLAB_API_URL/projects/$GITLAB_PROJECT_ID/terraform/state/firewall-gitops-${CLUSTER_NAME}" \
  -backend-config="lock_address=$GITLAB_API_URL/projects/$GITLAB_PROJECT_ID/terraform/state/firewall-gitops-${CLUSTER_NAME}/lock" \
  -backend-config="unlock_address=$GITLAB_API_URL/projects/$GITLAB_PROJECT_ID/terraform/state/firewall-gitops-${CLUSTER_NAME}/lock" \
  -backend-config="username=$GITLAB_USERNAME" \
  -backend-config="password=$GITLAB_TOKEN" \
  -backend-config="lock_method=POST" \
  -backend-config="unlock_method=DELETE" \
  -backend-config="retry_wait_min=5"
```

**State Naming:** `firewall-gitops-{cluster_name}`
- `firewall-gitops-example`
- `firewall-gitops-development`
- `firewall-gitops-production`

**Benefits:**
- Centralized state storage in GitLab
- Automatic state locking (prevents concurrent modifications)
- Per-cluster isolation (parallel deployments possible)
- Built-in backup and recovery

---

## Testing & Validation

### Validation Layers

**Layer 1: YAML Schema Validation**
- Tool: `scripts/validate_yaml.py`
- When: On every commit (validate stage)
- Validates: YAML syntax, required fields, data types, regex patterns

**Layer 2: Terraform Format Check**
- Tool: `terraform fmt -check -recursive`
- When: On every commit (validate stage)
- Validates: Terraform formatting consistency

**Layer 3: Terraform Validate**
- Tool: `terraform validate`
- When: On every commit (validate stage)
- Validates: Terraform syntax, variable references, resource dependencies

**Layer 4: Security Scan**
- Tool: Checkov
- When: On every commit (validate stage)
- Validates: Security best practices, compliance (PCI-DSS, NIST, CIS)

**Layer 5: Terraform Plan Review**
- Tool: `terraform plan`
- When: On merge request (plan stage)
- Validates: Resource changes preview, human review before apply

---

## Common Operations

### Add New Firewall Rule

1. Edit `clusters/<cluster>/objects/trust-zone.yaml`
2. Add rule to `rules:` array
3. Commit: `feat: allow SSH to bastion host`
4. Push and create MR
5. Review plan output in pipeline
6. Merge to deploy

### Add New Address Object

1. Edit `clusters/<cluster>/objects/addresses.yaml`
2. Add address to `addresses:` array
3. Commit: `feat: add new-server address object`
4. Push and create MR

### Switch from Single-File to Multi-File

1. Create `clusters/<cluster>/objects/` directory
2. Split `objects.yaml` into separate files:
   - `addresses.yaml`
   - `services.yaml`
   - `trust-zone.yaml`
   - `dmz-zone.yaml`
3. Delete `objects.yaml`
4. Commit: `refactor: split objects.yaml into multiple files`
5. Terraform automatically detects and merges all files

### Deploy New Cluster

1. Create `clusters/new-cluster/` directory
2. Copy `cluster.yaml` template
3. Configure firewall type and connection details
4. Create `objects.yaml` or `objects/*.yaml`
5. Update `.gitlab-ci.yml` to include new cluster jobs
6. Commit and push

---

## Code Statistics

```
Total Files: 50+
Total Lines: ~4,500

Terraform: ~1,200 lines (27%)
  - terraform/main.tf: 190
  - modules/palo-alto: 300
  - modules/checkpoint: 400
  - modules/f5-waf: 100
  - modules/fortinet: 100
  - variables.tf files: 110

YAML: ~800 lines (18%)
  - cluster.yaml files: 105
  - objects.yaml files: 450
  - .gitlab-ci.yml: 305

Python: ~250 lines (6%)
  - validate_yaml.py: 180
  - Other scripts: 70

Bash: ~350 lines (8%)
  - deploy.sh: 220
  - commit.sh: 80
  - Other scripts: 50

JSON Schema: ~850 lines (19%)
  - cluster.schema.json: 280
  - rules.schema.json: 520
  - Other schemas: 50

Documentation: ~1,000 lines (22%)
  - README.md: 456
  - CLAUDE.md: 280
  - Other docs: 264
```

---

## Architecture Decisions

### Why Conditional Module Execution?

**Alternative:** Use `terraform workspace` for multi-vendor support

**Chosen:** Conditional `count` based on `firewall.type`

**Rationale:**
- Single Terraform configuration per cluster
- Simpler CI/CD (no workspace switching)
- Clearer intent (explicitly define firewall type in YAML)
- Easier to add new vendors (just add new module + condition)

### Why Multi-File YAML Merging?

**Alternative:** Force single `objects.yaml` file

**Chosen:** Auto-detect and merge multiple YAML files

**Rationale:**
- Large firewall configs (1000+ rules) are unwieldy in single file
- Reduces merge conflicts (different engineers work on different zones)
- Backward compatible (single file still works)
- Flexible organization (by zone, team, application)

### Why GitLab HTTP Backend?

**Alternatives:** Terraform Cloud, S3 backend, local state

**Chosen:** GitLab HTTP backend with per-cluster state names

**Rationale:**
- Integrated with existing GitLab infrastructure
- No additional cost or services
- State locking included
- Per-cluster isolation enables parallel deployments
- Access control via GitLab project permissions

### Why Separate CheckPoint Host/Network Resources?

**Alternative:** Single unified address resource

**Chosen:** `checkpoint_management_host` for /32, `checkpoint_management_network` for subnets

**Rationale:**
- CheckPoint API requires different endpoints for hosts vs networks
- Provider design decision (not our choice)
- Module handles classification automatically via regex

---

## Future Enhancements

### Planned Improvements

1. **Fortinet Module Completion** - Implement FortiGate/FortiManager support
2. **Terraform Plan Visualization** - Render plan diffs in MR comments
3. **Configuration Drift Detection** - Compare Git state vs firewall actual config
4. **Advanced Security Profiles** - Enhanced profile management for PAN-OS
5. **Multi-Region Support** - Deploy same config to multiple firewalls
6. **Automated Testing** - Integration tests for rule validation
7. **Change Impact Analysis** - Predict affected connections before deployment
8. **Disaster Recovery** - Automated backup and restore procedures

### Technical Debt

1. **Fortinet Module** - Currently placeholder; needs full implementation
2. **Schema Generation** - Manual process; should auto-generate from Terraform
3. **Error Handling** - Improve error messages for provider API failures
4. **Logging** - Centralized logging for debugging deployments
5. **Documentation** - API reference documentation for modules

---

## Troubleshooting Guide

### Common Issues

**Issue:** `Error: fileexists: no file exists at path`
**Cause:** Neither `objects.yaml` nor `objects/` directory exists
**Fix:** Create either `objects.yaml` OR `objects/` directory with YAML files

**Issue:** `Error: Invalid value for "pattern" parameter`
**Cause:** YAML validation failed; invalid IP address or port format
**Fix:** Run `python scripts/validate_yaml.py` locally to see specific errors

**Issue:** `Error: Resource already exists`
**Cause:** Terraform state out of sync with firewall
**Fix:** `terraform import` the existing resource OR delete from firewall

**Issue:** `Error: State locked by another process`
**Cause:** Previous pipeline job still running or crashed without unlocking
**Fix:** Wait for previous job to complete OR force-unlock via Terraform CLI

**Issue:** `Error: timeout while waiting for connection`
**Cause:** Firewall API unreachable or credentials invalid
**Fix:** Verify `PANOS_HOSTNAME`, `CHECKPOINT_SERVER` variables; check network connectivity

---

## References

- **Terraform PAN-OS Provider:** https://registry.terraform.io/providers/PaloAltoNetworks/panos/latest/docs
- **Terraform CheckPoint Provider:** https://registry.terraform.io/providers/CheckPointSW/checkpoint/latest/docs
- **Terraform F5 BIG-IP Provider:** https://registry.terraform.io/providers/F5Networks/bigip/latest/docs
- **GitLab Terraform State:** https://docs.gitlab.com/ee/user/infrastructure/iac/terraform_state.html
- **JSON Schema Specification:** https://json-schema.org/
