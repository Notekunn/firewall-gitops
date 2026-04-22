# System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          FIREWALL GITOPS SYSTEM                          │
└─────────────────────────────────────────────────────────────────────────┘

                  ┌──────────────┐
                  │ SOAR Platform │
                  │ (Splunk, etc) │
                  └──────┬───────┘
                         │ Webhook
                         ▼
              ┌─────────────────────┐
              │   SOAR Webhook      │  <-- NEW: Automated Security Response
              │     Service         │  - Receives security events
              └──────┬───────┬──────┘
                     │       │ Git Push
                     ▼       ▼
            ┌─────────────────────┐
            │  Firewall Config    │
            │   Repository        │
            └──────┬───────┬──────┘
                   │       │
                   ▼       ▼
  ┌──────────────┐  ┌──────────────┐
  │   Engineer   │  │   SOAR Bot    │  Writes YAML configs
  └──────┬───────┘  └──────┬───────┘  (automated responses)
         │                 │
         ▼                 ▼
  ┌──────────────┐  ┌──────────────┐
  │  Git Push    │  │  Git Push    │  Feature branch → GitLab
  └──────┬───────┘  └──────┬───────┘
         │                 │
         ▼                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         GITLAB CI/CD PIPELINE                           │
├────────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │ VALIDATE │──▶│   PLAN   │──▶│  APPLY   │──▶│ CLEANUP  │            │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘            │
│       │              │               │              │                   │
│    YAML           Generate        Deploy        Remove                 │
│    Schema         Terraform       Changes       Artifacts              │
│    Terraform      Plan                                                 │
│    Format                                                              │
│    Validate                                                            │
│    Security                                                            │
└────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       TERRAFORM ORCHESTRATOR                            │
│                         (terraform/main.tf)                             │
├────────────────────────────────────────────────────────────────────────┤
│  1. Read cluster.yaml → firewall.type                                  │
│  2. Detect objects.yaml OR objects/*.yaml                              │
│  3. Merge all addresses/services/rules                                 │
│  4. Conditional module execution based on firewall.type                │
└────────────────┬───────────────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┬────────────────┬────────────────┐
    ▼                         ▼                ▼                ▼
┌─────────┐            ┌────────────┐   ┌──────────┐   ┌──────────┐
│ PAN-OS  │            │ CheckPoint │   │  F5 WAF  │   │ Fortinet │
│ Module  │            │   Module   │   │  Module  │   │  Module  │
└────┬────┘            └─────┬──────┘   └────┬─────┘   └────┬─────┘
     │                       │               │              │
     ▼                       ▼               ▼              ▼
┌─────────┐            ┌────────────┐   ┌──────────┐   ┌──────────┐
│panos_*  │            │checkpoint_ │   │ bigip_*  │   │fortios_* │
│Provider │            │management_*│   │ Provider │   │ Provider │
└────┬────┘            └─────┬──────┘   └────┬─────┘   └────┬─────┘
     │                       │               │              │
     ▼                       ▼               ▼              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      FIREWALL DEVICES                             │
│  Panorama / NGFW    Management Server    BIG-IP WAF   FortiManager│
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  GitLab State    │
                    │  HTTP Backend    │
                    │  (per-cluster)   │
                    └──────────────────┘
```

---

## Data Flow (5 Stages)

### Stage 1: YAML Configuration

**Input:** Network engineer creates/modifies YAML files

```
clusters/production/
├── cluster.yaml          # Firewall type, connection, settings
└── objects/              # Split configuration
    ├── addresses.yaml    # Global addresses
    ├── services.yaml     # Global services
    ├── trust-zone.yaml   # Trust zone rules
    └── dmz-zone.yaml     # DMZ zone rules
```

**Processing:**
- Engineer writes human-readable YAML
- No Terraform knowledge required
- Version controlled in Git

**Output:** Committed YAML files in Git repository

---

### Stage 2: YAML Parsing & Merging

**Input:** YAML files from multiple sources

**Processing:** `terraform/main.tf` (lines 20-109)

```hcl
# 1. Auto-detect mode
has_single_objects_file = fileexists("objects.yaml")
has_objects_folder = length(fileset("objects", "*.yaml")) > 0

# 2. Read all files
single_file_data = yamldecode(file("objects.yaml"))
objects_data_list = [for f in objects_files : yamldecode(file("objects/${f}"))]

# 3. Merge addresses from all sources
addresses_from_single = try(single_file_data.addresses, [])
addresses_from_multi = flatten([for data in objects_data_list : try(data.addresses, [])])
firewall_addresses = concat(addresses_from_single, addresses_from_multi)

# 4. Merge services and rules similarly
firewall_services = concat(services_from_single, services_from_multi)
firewall_rules = concat(rules_from_single, rules_from_multi)
```

**Output:** Three unified lists
- `local.firewall_addresses`
- `local.firewall_services`
- `local.firewall_rules`

---

### Stage 3: Conditional Module Execution

**Input:** Merged data + firewall.type from cluster.yaml

**Processing:** `terraform/main.tf` (lines 120-180)

```hcl
module "palo_alto_firewall" {
  count = local.firewall_config.type == "palo-alto" ? 1 : 0
  source = "../modules/palo-alto"
  firewall_rules = local.firewall_rules
  firewall_addresses = local.firewall_addresses
  firewall_services = local.firewall_services
}

module "checkpoint_firewall" {
  count = local.firewall_config.type == "checkpoint" ? 1 : 0
  source = "../modules/checkpoint"
  # ... same data
}
```

**Logic:** Only ONE module executes per cluster (determined by firewall.type)

**Output:** Module invocation with location context

---

### Stage 4: Provider Resource Creation

**Input:** Module receives addresses/services/rules

**Processing:** Module creates vendor-specific resources

#### PAN-OS Module
```hcl
# modules/palo-alto/main.tf
resource "panos_addresses" "address_objects" {
  for_each = { for addr in var.firewall_addresses : addr.name => addr }
  name = each.value.name
  ip_netmask = lookup(each.value, "ip_netmask", null)
}

resource "panos_service" "service_objects" {
  for_each = { for svc in var.firewall_services : svc.name => svc }
  name = each.value.name
  protocol = each.value.type
  destination_port = each.value.destination_port
}

resource "panos_schedule" "schedules" {
  for_each = { for s in var.firewall_schedules : s.name => s }
  name             = each.value.name
  schedule_type    = each.value.schedule_type
}

resource "panos_security_policy_rules" "rules" {
  depends_on = [
    panos_addresses.address_objects,
    panos_service.service_objects,
    panos_schedule.schedules,
  ]
  # ... rule configuration (schedule + log_setting now passed through)
}
```

#### CheckPoint Module
```hcl
# modules/checkpoint/main.tf
# Separate hosts (/32) from networks
locals {
  host_addresses = [for addr in var.firewall_addresses : addr if can(regex("/32$", addr.ip_netmask))]
  network_addresses = [for addr in var.firewall_addresses : addr if !can(regex("/32$", addr.ip_netmask))]
}

resource "checkpoint_management_host" "host_objects" {
  for_each = { for addr in local.host_addresses : addr.name => addr }
  name = each.value.name
  ipv4_address = regex("^([^/]+)", each.value.ip_netmask)[0]
}

resource "checkpoint_management_network" "network_objects" {
  for_each = { for addr in local.network_addresses : addr.name => addr }
  name = each.value.name
  subnet4 = each.value.ip_netmask
}

resource "checkpoint_management_publish" "publish" {
  count = var.global.auto_publish ? 1 : 0
  depends_on = [
    checkpoint_management_host.host_objects,
    checkpoint_management_network.network_objects,
    checkpoint_management_access_rule.rules
  ]
}
```

**Output:** API calls to firewall providers

---

### Stage 5: Firewall Deployment

**Input:** Terraform provider API calls

**Processing:**
- **PAN-OS:** REST API to Panorama/NGFW
- **CheckPoint:** Management Server API with automatic publish
- **F5:** BIG-IP iControl REST API

**Output:**
- Address objects created on firewall
- Service objects created
- Security rules deployed
- Terraform state updated in GitLab

---

## SOAR Webhook Integration (Automated Security Response)

### Overview

The SOAR (Security Orchestration, Automation and Response) Webhook Service enables automated security responses by integrating external security platforms with the Firewall GitOps workflow. This allows security teams to automatically block threats, update firewall rules, and respond to incidents without manual intervention.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SOAR WEBHOOK SERVICE                     │
│                    (Go Microservice)                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │  Webhook     │  │  Event       │  │  Git Integration │ │
│  │  Receiver    │->│  Processor   |->│     Module       │ │
│  │  (HTTP API)  │  │  (Parser)    │  │  (Clone/Push)    │ │
│  └──────────────┘  └──────────────┘  └──────────────────┘ │
└──────────────────┬──────────────────────────────────────────┘
                   │ Git Push
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              FIREWALL CONFIG REPOSITORY                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │  clusters/   │  │  objects/    │  │  Auto-generated  │ │
│  │  *.yaml      │  │  *.yaml      │  │  branch         │ │
│  └──────────────┘  └──────────────┘  └──────────────────┘ │
└──────────────────┬──────────────────────────────────────────┘
                   │ Triggers
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                  GITLAB CI/CD PIPELINE                      │
│  Validate → Plan → Review → Apply → Verify                 │
└─────────────────────────────────────────────────────────────┘
```

### Event Flow

1. **Security Event Detected**: SOAR platform (Splunk SOAR, Palo Alto Cortex XSOAR, etc.) detects a threat
2. **Webhook Triggered**: SOAR sends HTTP POST to SOAR Webhook Service
3. **Event Validation**: Service validates webhook signature and parses payload
4. **Response Generation**: Based on event type, generates appropriate firewall rule updates
5. **Git Operations**:
   - Clones the firewall configuration repository
   - Creates new branch with automated rule changes
   - Commits changes with descriptive commit message
   - Pushes to GitLab, triggering CI/CD pipeline
6. **Automated Deployment**: GitLab CI/CD validates and applies changes to firewall

### Configuration

Environment Variables:
```bash
# GitLab Integration
GITLAB_URL="https://gitlab.example.com"
GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
GITLAB_PROJECT_ID="123"
REPO_CLONE_URL="https://gitlab.example.com/your-org/firewall-configs.git"

# Service Configuration
WEBHOOK_SECRET="your-random-secret-string"
TARGET_CLUSTER="production"  # Default cluster to update
SERVER_PORT="8080"           # HTTP server port
```

### Supported Event Types (Planned)

- **Malicious IP**: Automatically blocks IP addresses
- **C2 Domain**: Blocks command and control domains
- **Threat Intelligence**: Integrates with threat feeds
- **Anomaly Detection**: Creates temporary restrictions
- **Incident Response**: Implements quarantine rules

### Security Features

- **Webhook Signature Validation**: HMAC-SHA256 signature verification
- **Rate Limiting**: Prevents abuse and DoS attacks
- **Audit Logging**: All actions logged with full traceability
- **Rule Validation**: Generated rules undergo YAML schema validation
- **Manual Override**: Security team can review automated changes

### Implementation Phases

**Phase 01 (Current)**: ✅ Project Setup & Configuration
- Configuration management with environment variables
- Structured logging implementation
- Unit test framework setup

**Phase 02**: 🚧 Web API Development
- HTTP server with webhook endpoints
- Request validation and parsing
- Response formatting

**Phase 03**: 🚧 Git Integration
- Repository cloning and management
- Branch creation and file operations
- Commit and push automation

**Phase 04**: 🚧 Event Processing
- Event parsing and classification
- Rule generation logic
- Security response workflows

**Phase 05**: 🚧 Advanced Features
- Multi-platform integration
- Custom workflow engine
- Performance optimization

---

## Component Interactions

### YAML Parser → Module Flow

```
┌──────────────────────────────────────────────────────────────┐
│                   terraform/main.tf                           │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  [1] Read cluster.yaml                                        │
│      ↓                                                        │
│  [2] Extract firewall.type = "palo-alto"                     │
│      ↓                                                        │
│  [3] Detect configuration mode                                │
│      has_single_objects_file?  ──Yes──▶ Read objects.yaml    │
│      has_objects_folder?       ──Yes──▶ Read objects/*.yaml  │
│      ↓                                                        │
│  [4] Merge addresses/services/rules                           │
│      firewall_addresses = concat(single, multi)              │
│      ↓                                                        │
│  [5] Build location context                                   │
│      Panorama: {device_group, panorama_device, rulebase}     │
│      Standalone: {ngfw_device, vsys_name}                    │
│      ↓                                                        │
│  [6] Conditional module execution                             │
│      count = firewall.type == "palo-alto" ? 1 : 0            │
│      ↓                                                        │
│  [7] Pass to module                                           │
│      module.palo_alto_firewall[0]                            │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│            modules/palo-alto/main.tf                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  [1] Receive merged data                                      │
│      var.firewall_addresses (50 addresses)                   │
│      var.firewall_services (30 services)                     │
│      var.firewall_rules (100 rules)                          │
│      var.firewall_schedules (N schedules)                    │
│      ↓                                                        │
│  [2] Create address objects                                   │
│      for_each = { for addr in addresses : addr.name => addr }│
│      panos_addresses.address_objects                         │
│      ↓                                                        │
│  [3] Create service objects                                   │
│      for_each = { for svc in services : svc.name => svc }    │
│      panos_service.service_objects                           │
│      ↓                                                        │
│  [4] Create schedule objects                                  │
│      for_each = { for s in schedules : s.name => s }         │
│      panos_schedule.schedules                                │
│      ↓                                                        │
│  [5] Create rules (depends on 2, 3 & 4)                       │
│      panos_security_policy_rules.rules                       │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
                ┌──────────────┐
                │ PAN-OS API   │
                └──────────────┘
```

---

## State Management Architecture

### GitLab HTTP Backend

**Configuration:**
```hcl
terraform {
  backend "http" {}
}
```

**Runtime Backend Config:**
```bash
terraform init \
  -backend-config="address=$GITLAB_API_URL/projects/$PROJECT_ID/terraform/state/firewall-gitops-${CLUSTER}" \
  -backend-config="lock_address=$GITLAB_API_URL/projects/$PROJECT_ID/terraform/state/firewall-gitops-${CLUSTER}/lock" \
  -backend-config="unlock_address=$GITLAB_API_URL/projects/$PROJECT_ID/terraform/state/firewall-gitops-${CLUSTER}/lock" \
  -backend-config="username=$GITLAB_USERNAME" \
  -backend-config="password=$GITLAB_TOKEN" \
  -backend-config="lock_method=POST" \
  -backend-config="unlock_method=DELETE"
```

### State Isolation

**Per-Cluster State:**
```
GitLab Project: firewall-gitops
├── State: firewall-gitops-example        (example cluster)
├── State: firewall-gitops-development    (development cluster)
└── State: firewall-gitops-production     (production cluster)
```

**Benefits:**
1. **Parallel Deployments:** Different clusters deploy simultaneously
2. **Blast Radius Limitation:** Changes to dev don't affect prod state
3. **Independent Rollback:** Revert one cluster without affecting others
4. **Access Control:** GitLab project permissions control state access

### State Locking

**Mechanism:** GitLab provides built-in state locking

**Flow:**
```
1. Terraform acquires lock (POST to lock_address)
2. GitLab creates lock in database
3. Other Terraform processes wait or fail
4. Terraform releases lock after operation (DELETE to unlock_address)
```

**Resource Groups:** Additional layer in CI/CD
```yaml
resource_group: terraform-${CLUSTER_NAME}
```
- Ensures only ONE pipeline job runs per cluster
- Prevents concurrent modifications even if state lock fails

---

## CI/CD Pipeline Architecture

### Pipeline Stages (4)

```
┌─────────────────────────────────────────────────────────────────┐
│                         VALIDATE STAGE                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │validate_yaml │  │terraform_fmt_*   │  │security_scan     │   │
│  │              │  │                  │  │ (Checkov)        │   │
│  │All clusters  │  │Per cluster       │  │Allow failure     │   │
│  └──────────────┘  └──────────────────┘  └──────────────────┘   │
│  ┌──────────────────┐                                            │
│  │terraform_validate│                                            │
│  │Per cluster       │                                            │
│  └──────────────────┘                                            │
└─────────────────────────────────────────────────────────────────┘
                              ║
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                          PLAN STAGE                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │plan_example     │  │plan_development │  │plan_production  │  │
│  │                 │  │                 │  │                 │  │
│  │Triggered by:    │  │Triggered by:    │  │Triggered by:    │  │
│  │- cluster change │  │- cluster change │  │- cluster change │  │
│  │- module change  │  │- module change  │  │- module change  │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                    │            │
│           ▼                    ▼                    ▼            │
│  Artifacts: plan-*.tfplan (expire: 1 week)                       │
└─────────────────────────────────────────────────────────────────┘
                              ║
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         APPLY STAGE                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │apply_example    │  │apply_development│  │apply_production │  │
│  │                 │  │                 │  │                 │  │
│  │Auto-apply       │  │Auto-apply       │  │Manual approval  │  │
│  │when: manual     │  │when: on_success │  │needs:           │  │
│  │                 │  │                 │  │approve_production│ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                    ▲              │
│                                        ┌───────────┴────────────┐│
│                                        │approve_production      ││
│                                        │(Manual gate)           ││
│                                        └────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              ║
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CLEANUP STAGE                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐   │
│  │cleanup_artifacts                                          │   │
│  │Remove old plan files from GitLab                          │   │
│  │when: always                                               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Job Triggering Logic

**Conditional Execution:**
```yaml
only:
  changes:
    - clusters/${CLUSTER_NAME}/**/*
    - terraform/**/*
    - modules/**/*
```

**Why:** Only run plan/apply for affected clusters

**Example:**
- Change `clusters/production/objects/trust-zone.yaml`
- Only `plan_production` and `apply_production` execute
- Other clusters (example, development) skip

---

## Security Architecture

### Secret Management

**GitLab CI/CD Variables:**
```
Project Settings → CI/CD → Variables

PAN-OS:
- PANOS_HOSTNAME (protected, masked)
- PANOS_USERNAME (protected, masked)
- PANOS_PASSWORD (protected, masked)

CheckPoint:
- CHECKPOINT_SERVER (protected, masked)
- CHECKPOINT_USERNAME (protected, masked)
- CHECKPOINT_PASSWORD (protected, masked)
- CHECKPOINT_CONTEXT (protected)

GitLab State:
- GITLAB_TOKEN (protected, masked)
- GITLAB_USERNAME (protected)
- GITLAB_API_URL (not sensitive)
```

**Protection Levels:**
- **Protected:** Only available on protected branches (main, production)
- **Masked:** Hidden in job logs
- **Scoped:** Can limit to specific environments

### Validation Layers

**Layer 1: JSON Schema (scripts/validate_yaml.py)**
- Required fields present
- Data types correct
- Regex patterns match (IPs, ports)
- Enum values valid

**Layer 2: Terraform Validate**
- Syntax correctness
- Variable references exist
- Resource dependencies valid

**Layer 3: Terraform Plan**
- Preview changes before apply
- Human review in MR
- Catch logical errors

**Layer 4: Manual Approval (Production)**
- Security team approval required
- Review plan output
- Verify compliance

**Layer 5: Checkov Security Scan**
- OWASP best practices
- CIS benchmarks
- NIST compliance
- PCI-DSS checks

---

## Firewall-Specific Architectures

### PAN-OS Architecture

#### Panorama Mode
```
┌──────────────────────────────────────────────────────────┐
│                     PANORAMA                              │
│  ┌────────────────────────────────────────────────────┐  │
│  │         Device Group: Production-DG                 │  │
│  │  ┌──────────────┐  ┌──────────────┐               │  │
│  │  │  Addresses   │  │   Services   │               │  │
│  │  └──────────────┘  └──────────────┘               │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  Pre-Rulebase                                │  │  │
│  │  │  - Rule 1: allow-web-traffic                 │  │  │
│  │  │  - Rule 2: allow-ssh-admin                   │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────┬───────────────────────────────────────┘
                   │ Push policy
                   ▼
        ┌──────────────────┐
        │  NGFW Firewalls  │
        │  (Managed)       │
        └──────────────────┘
```

**Terraform Resources:**
- `device_group` context required
- `panorama_device` (default: "localhost.localdomain")
- `rulebase` (default: "pre-rulebase")

#### Standalone Mode
```
┌──────────────────────────────────────────────────────────┐
│                 STANDALONE NGFW                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │              vsys1 (Virtual System)                 │  │
│  │  ┌──────────────┐  ┌──────────────┐               │  │
│  │  │  Addresses   │  │   Services   │               │  │
│  │  └──────────────┘  └──────────────┘               │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  Security Rules                              │  │  │
│  │  │  - Rule 1: allow-web-traffic                 │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Terraform Resources:**
- `vsys` context required
- `ngfw_device` (default: "localhost.localdomain")

### CheckPoint Architecture

```
┌──────────────────────────────────────────────────────────────┐
│            CHECKPOINT MANAGEMENT SERVER                       │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Domain: Production                         │  │
│  │  ┌──────────────┐  ┌──────────────┐                   │  │
│  │  │    Hosts     │  │   Networks   │                   │  │
│  │  │  (IP /32)    │  │  (Subnets)   │                   │  │
│  │  └──────────────┘  └──────────────┘                   │  │
│  │  ┌──────────────┐  ┌──────────────┐                   │  │
│  │  │  TCP Service │  │ UDP Service  │                   │  │
│  │  └──────────────┘  └──────────────┘                   │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │     Access Layer: Network                        │  │  │
│  │  │  - Rule 1: allow-web                             │  │  │
│  │  │  - Rule 2: deny-external                         │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │                                                         │  │
│  │  [Auto-Publish: true] → Publish changes               │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────┬───────────────────────────────────────────┘
                   │ Install policy
                   ▼
        ┌─────────────────────┐
        │ Security Gateways   │
        │ (Policy Targets)    │
        └─────────────────────┘
```

**Key Differences:**
- Separate host/network resources based on /32
- Requires explicit publish step
- Uses policy layers for organization

### F5 WAF Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    F5 BIG-IP WAF                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Partition: Common                          │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │           IP Lists                                │  │  │
│  │  │  - whitelist-api (allow list)                    │  │  │
│  │  │  - blacklist-attackers (block list)              │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  iRule: gitops_ip_filter                         │  │  │
│  │  │  - Check source IP against lists                 │  │  │
│  │  │  - Block if in blacklist                         │  │  │
│  │  │  - Allow if in whitelist                         │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │                                                         │  │
│  │  Applied to Virtual Servers                            │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**Implementation:**
- IP lists stored as JSON arrays
- iRule references lists by name
- Applied at virtual server level

---

## Performance Considerations

### Terraform Parallelism

**Automatic Parallelization:**
- Independent resources execute in parallel
- Default: 10 parallel operations
- Configurable: `terraform apply -parallelism=20`

**Resource Graph:**
```
addresses ─┐
           ├─▶ rules (depends_on both)
services ──┘
```

**Execution:**
1. addresses and services create in parallel
2. rules wait for both to complete
3. rules create in parallel (if no inter-rule dependencies)

### YAML Merging Efficiency

**Single Operation:**
```hcl
# Efficient: Single concat + flatten
firewall_addresses = concat(
  addresses_from_single,
  flatten([for data in objects_data_list : try(data.addresses, [])])
)
```

**Avoids:**
- Multiple file reads
- Incremental concatenation
- Nested loops

### State File Size

**Typical Size:**
- Small cluster (50 rules): ~100KB
- Medium cluster (500 rules): ~1MB
- Large cluster (2000 rules): ~5MB

**Optimization:**
- Use GitLab HTTP backend (no local state)
- Per-cluster state isolation
- Automatic compression

---

## Disaster Recovery

### Rollback Procedures

**Git Revert:**
```bash
# Revert last commit
git revert HEAD
git push origin main

# Pipeline automatically:
# 1. Validates reverted config
# 2. Generates plan (shows removal)
# 3. Applies (removes resources)
```

**State Recovery:**
- GitLab maintains state history
- Can restore previous state version
- Terraform import for manual recovery

### Backup Strategy

**Automatic:**
- Git history (infinite retention)
- GitLab state versioning
- Pipeline artifacts (1 week)

**Manual:**
```bash
# Export current state
terraform state pull > backup-$(date +%Y%m%d).json

# Import state from backup
terraform state push backup-20250326.json
```

---

## Monitoring & Observability

### Pipeline Monitoring

**GitLab Built-in:**
- Job success/failure rates
- Pipeline duration trends
- Artifact storage usage

**Metrics to Track:**
- Validation pass rate
- Average plan time
- Deploy frequency
- Rollback frequency

### Firewall Monitoring

**Post-Deployment Checks:**
- PAN-OS commit status
- CheckPoint policy installation
- F5 iRule compilation

**Health Checks (Manual):**
```bash
# PAN-OS
scripts/commit.sh

# CheckPoint
show changes  # Via Management Server CLI

# F5
tmsh list ltm rule gitops_ip_filter
```

---

## Scalability

### Horizontal Scaling

**Add New Cluster:**
1. Create `clusters/new-cluster/` directory
2. Add cluster-specific jobs to `.gitlab-ci.yml`
3. Configure CI/CD variables for new cluster
4. Deploy

**Limits:**
- GitLab: ~100 concurrent jobs
- Terraform: No hard limit on clusters
- Firewall APIs: Vendor-specific rate limits

### Vertical Scaling

**Large Rule Sets:**
- Multi-file configuration (reduces merge conflicts)
- Terraform parallelism tuning
- Provider timeouts configuration

**State Size:**
- Consider S3 backend for very large clusters (10K+ rules)
- Current GitLab backend handles up to ~50MB state

---

## Future Architecture Improvements

### Planned Enhancements

1. **Drift Detection**
   - Compare Git state vs firewall actual config
   - Alert on manual changes

2. **Multi-Region Deployments**
   - Deploy same config to multiple firewalls
   - Region-specific overrides

3. **Advanced Testing**
   - Integration tests before production
   - Traffic simulation

4. **Change Impact Analysis**
   - Predict affected connections
   - Risk scoring

5. **Real-time Monitoring**
   - WebSocket connections to firewalls
   - Live rule hit counts

---

## Architecture Decisions Record

### ADR-001: GitLab HTTP Backend
**Decision:** Use GitLab HTTP backend for state
**Rationale:** Integrated with existing infrastructure, no additional cost
**Alternatives:** Terraform Cloud ($$), S3 backend (complexity)

### ADR-002: Conditional Module Execution
**Decision:** Use `count` for vendor selection
**Rationale:** Simpler than workspaces, clearer intent
**Alternatives:** Terraform workspaces (harder to manage)

### ADR-003: Multi-File YAML Merging
**Decision:** Auto-merge objects/*.yaml files
**Rationale:** Reduces merge conflicts, backward compatible
**Alternatives:** Force single file (doesn't scale), manual merging (error-prone)

### ADR-004: CheckPoint Auto-Publish
**Decision:** Default auto_publish: true
**Rationale:** Matches PAN-OS behavior (immediate effect)
**Alternatives:** Manual publish (extra step), session management (complex)

### ADR-005: Per-Cluster State Isolation
**Decision:** Separate state files per cluster
**Rationale:** Parallel deployments, blast radius limitation
**Alternatives:** Single state (deployment bottleneck), no backend (team conflicts)

---

## Reference Architecture

**Production-Grade Deployment:**
```
GitLab Project: firewall-gitops
├── Clusters:
│   ├── prod-us-east (PAN-OS Panorama)
│   ├── prod-us-west (PAN-OS Panorama)
│   ├── prod-eu (CheckPoint)
│   └── staging (PAN-OS Standalone)
├── CI/CD:
│   ├── 20 parallel jobs
│   ├── Manual approval for prod
│   └── Auto-deploy for staging
├── State:
│   ├── GitLab HTTP backend
│   ├── Per-cluster isolation
│   └── State locking enabled
└── Security:
    ├── Protected variables
    ├── Masked secrets
    └── Checkov scanning
```

---

## Troubleshooting Architecture Issues

### State Lock Timeout
**Symptom:** Pipeline stuck waiting for lock
**Cause:** Previous job crashed without releasing lock
**Fix:** Force unlock via Terraform CLI

### Module Not Executing
**Symptom:** No resources created
**Cause:** firewall.type mismatch or count = 0
**Fix:** Verify cluster.yaml firewall.type

### Provider Authentication Failure
**Symptom:** "Error: authentication failed"
**Cause:** Missing or incorrect CI/CD variables
**Fix:** Verify PANOS_HOSTNAME, CHECKPOINT_SERVER, etc.

### YAML Merge Not Working
**Symptom:** Addresses missing from plan
**Cause:** File not in objects/ directory or wrong extension
**Fix:** Ensure .yaml extension, check file location
