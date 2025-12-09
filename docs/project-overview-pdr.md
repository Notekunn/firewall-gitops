# Project Overview & Product Development Requirements

## Executive Summary

**Project Name:** Firewall GitOps

**Purpose:** YAML-to-Terraform automation system enabling network engineers to manage multi-vendor firewall configurations through GitOps workflows.

**Core Value Proposition:** Transform complex firewall management into simple YAML files with automated validation, version control, and deployment via GitLab CI/CD.

---

## Problem Statement

### Current Challenges

**Manual Firewall Management:**
- Error-prone CLI configurations
- No version control for rule changes
- Difficult to audit who changed what and when
- Inconsistent configurations across environments
- No automated validation before deployment

**Multi-Vendor Complexity:**
- Each firewall vendor has different APIs and CLIs
- Learning curve for PAN-OS, CheckPoint, Fortinet, F5 syntax
- No unified interface across platforms
- Configuration drift between dev/staging/production

**Collaboration Bottlenecks:**
- Single admin making all changes (SPOF)
- No code review process for firewall rules
- Manual approval workflows via email/tickets
- Difficult to coordinate changes across teams

**Lack of Testing:**
- Changes applied directly to production
- No dry-run or plan preview
- Manual rollback procedures
- Fear of breaking production connectivity

### Target Users

1. **Network Engineers** - Define firewall rules using YAML
2. **Security Teams** - Review and approve rule changes via MRs
3. **DevOps Engineers** - Integrate firewall changes into CI/CD pipelines
4. **Compliance Officers** - Audit firewall configuration history

---

## Solution Overview

### Architecture Philosophy

**Infrastructure as Code (IaC):**
- Declarative YAML configuration
- Version-controlled in Git
- Peer-reviewed via merge requests
- Automated deployment via CI/CD

**GitOps Workflow:**
```
YAML Config → Git Push → Pipeline Validation → Terraform Plan → Approval → Terraform Apply → Firewall Update
```

**Multi-Vendor Abstraction:**
- Unified YAML schema for all vendors
- Vendor-specific Terraform modules
- Conditional module execution based on firewall type
- Provider-agnostic addressing and service definitions

### Key Features

#### 1. YAML-Based Configuration
- **Human-readable** address, service, and rule definitions
- **Multi-file support** for large configurations (automatic merging)
- **Type-safe** validation via JSON schemas
- **Reusable** objects across rules

#### 2. Multi-Vendor Support
- ✅ **Palo Alto Networks (PAN-OS)** - Panorama and standalone NGFW
- ✅ **Check Point** - Management Server with policy layers
- ✅ **F5 WAF** - BIG-IP security policies and IP lists
- 🚧 **Fortinet** - Planned for future release

#### 3. GitOps Automation
- **Automatic validation** on every commit (YAML schema + Terraform fmt/validate)
- **Terraform plan** generated for every change
- **Manual approval gates** for production deployments
- **Parallel deployments** for independent clusters
- **State management** via GitLab HTTP backend (per-cluster isolation)

#### 4. Multi-File Configuration
- **Single file mode**: `objects.yaml` (backward compatible)
- **Multi-file mode**: `objects/*.yaml` (recommended for large configs)
- **Automatic merging**: All addresses, services, rules combined from multiple files
- **Team collaboration**: Separate files per zone/team to reduce merge conflicts

#### 5. Security & Compliance
- **JSON schema validation** prevents configuration errors
- **Terraform plan review** before applying changes
- **Full audit trail** via Git history
- **Security scanning** with Checkov (static analysis)
- **Secret management** via GitLab CI/CD variables

#### 6. Intelligent Positioning
- **Rule placement control** - first/last/after/before (PAN-OS) or top/bottom/above/below (CheckPoint)
- **Reference-based positioning** - place rules relative to pivot rule
- **Direct positioning** - exact or generic placement

---

## Product Development Requirements (PDR)

### Functional Requirements

#### FR1: YAML Configuration Management
- **FR1.1** - Support single-file `objects.yaml` configuration (backward compatible)
- **FR1.2** - Support multi-file `objects/*.yaml` configuration with automatic merging
- **FR1.3** - Parse and merge addresses, services, rules from multiple YAML files
- **FR1.4** - Validate YAML against JSON schemas before deployment
- **FR1.5** - Support address types: `ip_netmask`, `ip_range`, `ip_wildcard`, `fqdn`
- **FR1.6** - Support service types: TCP, UDP with source/destination ports
- **FR1.7** - Support firewall rule attributes: zones, addresses, applications, services, action, logging

#### FR2: Multi-Vendor Firewall Support
- **FR2.1** - Conditional module execution based on `firewall.type` in `cluster.yaml`
- **FR2.2** - PAN-OS support for Panorama (device_group) and standalone (vsys) modes
- **FR2.3** - CheckPoint support with management domains and policy layers
- **FR2.4** - F5 WAF support for IP lists and security policies
- **FR2.5** - Unified YAML schema across all vendors
- **FR2.6** - Vendor-specific resource mapping (addresses → panos_addresses / checkpoint_management_host)

#### FR3: Terraform State Management
- **FR3.1** - GitLab HTTP backend for centralized state storage
- **FR3.2** - Per-cluster state isolation (naming: `firewall-gitops-{cluster_name}`)
- **FR3.3** - State locking to prevent concurrent modifications
- **FR3.4** - Support parallel deployments of different clusters

#### FR4: GitLab CI/CD Pipeline
- **FR4.1** - **Validate stage**: YAML schema validation, Terraform fmt/validate, Checkov scan
- **FR4.2** - **Plan stage**: Generate Terraform plan for changed clusters
- **FR4.3** - **Apply stage**: Auto-apply for dev/staging, manual approval for production
- **FR4.4** - **Cleanup stage**: Remove old plan artifacts
- **FR4.5** - Resource groups to prevent concurrent cluster modifications
- **FR4.6** - Artifact retention (plans stored for 1 week)

#### FR5: Rule Positioning
- **FR5.1** - Support PAN-OS positioning: `first`, `last`, `after`, `before`
- **FR5.2** - Support CheckPoint positioning: `top`, `bottom`, `above`, `below`
- **FR5.3** - Reference-based positioning with `pivot` rule name
- **FR5.4** - Direct vs generic placement via `directly` boolean

#### FR6: Logging & Security Profiles
- **FR6.1** - Global log setting from `cluster.yaml`
- **FR6.2** - Per-rule log overrides (`log_start`, `log_end`)
- **FR6.3** - Security profile groups (PAN-OS)
- **FR6.4** - Individual security profiles (virus, spyware, vulnerability, URL filtering, etc.)

#### FR7: CheckPoint-Specific Features
- **FR7.1** - Automatic host/network classification based on CIDR (/32 → host, else → network)
- **FR7.2** - Automatic publish after changes (`auto_publish: true`)
- **FR7.3** - Policy installation on gateways (`install_on` list)
- **FR7.4** - Track settings for logging (accounting, alert, per-connection, per-session)

#### FR8: F5 WAF Features
- **FR8.1** - IP list management (allow/block lists)
- **FR8.2** - iRule-based filtering
- **FR8.3** - Partition support for multi-tenancy

#### FR9: SOAR Webhook Service (NEW - Phase 01 Complete)
- **FR9.1** - HTTP webhook endpoint for receiving SOAR security alerts
- **FR9.2** - Configuration management for GitLab integration
- **FR9.3** - Go-based service with modular architecture
- **FR9.4** - Environment-based configuration (GitLab token, project ID, YAML paths)
- **FR9.5** - Foundation for automated IP blocklist updates
- **FR9.6** - Comprehensive test coverage for all components

### Non-Functional Requirements

#### NFR1: Performance
- **NFR1.1** - Pipeline validation completes in < 2 minutes
- **NFR1.2** - Terraform plan generation in < 5 minutes for typical cluster
- **NFR1.3** - Support 100+ firewall rules per cluster
- **NFR1.4** - Parallel cluster deployments without performance degradation
- **NFR1.5** - SOAR webhook response time < 500ms (Phase 02 target)

#### NFR2: Reliability
- **NFR2.1** - State locking prevents concurrent modifications
- **NFR2.2** - Atomic Terraform operations (all-or-nothing deployments)
- **NFR2.3** - Automatic retry for transient provider API failures
- **NFR2.4** - Rollback capability via Git revert

#### NFR3: Security
- **NFR3.1** - No secrets in Git repository
- **NFR3.2** - Secrets stored in GitLab CI/CD variables
- **NFR3.3** - PAN-OS partial commits per-admin (avoid overwriting others' changes)
- **NFR3.4** - HTTPS-only connections to firewall APIs
- **NFR3.5** - SSL certificate verification (configurable skip for dev)

#### NFR4: Usability
- **NFR4.1** - Network engineers can define rules without Terraform knowledge
- **NFR4.2** - Clear error messages for YAML validation failures
- **NFR4.3** - Terraform plan preview before applying changes
- **NFR4.4** - Schema auto-generated from Terraform variables (single source of truth)

#### NFR5: Maintainability
- **NFR5.1** - Modular Terraform structure (vendor-specific modules)
- **NFR5.2** - DRY principle - no duplicated configuration
- **NFR5.3** - Self-documenting file names (kebab-case)
- **NFR5.4** - Comprehensive documentation in `docs/` directory

#### NFR6: Scalability
- **NFR6.1** - Support 10+ independent clusters
- **NFR6.2** - Multi-file configuration for large rule sets (1000+ rules)
- **NFR6.3** - Horizontal scaling via parallel pipeline jobs

---

## Use Cases

### UC1: Network Engineer Adds New Firewall Rule

**Actor:** Network Engineer

**Preconditions:**
- Access to GitLab repository
- Understanding of YAML syntax
- Knowledge of firewall zones and policies

**Flow:**
1. Clone repository and create feature branch
2. Edit `clusters/production/objects/web-zone.yaml`
3. Add new rule to allow HTTPS traffic to web server
4. Commit changes: `feat: allow HTTPS to web-server-01`
5. Push to GitLab
6. Pipeline validates YAML and generates Terraform plan
7. Create merge request with plan output
8. Security team reviews and approves MR
9. Merge to main branch
10. Pipeline applies changes to production firewall (after manual approval)

**Postconditions:**
- New rule deployed to firewall
- Git history records change with author/timestamp
- Terraform state updated

### UC2: Security Team Audits Firewall Changes

**Actor:** Security Officer

**Preconditions:**
- Access to GitLab repository

**Flow:**
1. Navigate to repository commits page
2. Filter by date range (e.g., last 30 days)
3. Review commit messages and diffs
4. Click on commit to see full YAML changes
5. View Terraform plan in pipeline artifacts
6. Verify changes comply with security policy

**Postconditions:**
- Audit report generated
- Non-compliant changes flagged for review

### UC3: DevOps Engineer Deploys Multi-Environment Config

**Actor:** DevOps Engineer

**Preconditions:**
- Separate clusters: `development`, `staging`, `production`
- CI/CD variables configured per environment

**Flow:**
1. Update firewall rules in `clusters/development/objects.yaml`
2. Push changes - dev cluster auto-deploys
3. Test in development environment
4. Promote changes to `clusters/staging/objects.yaml`
5. Push changes - staging cluster auto-deploys
6. Validate in staging
7. Copy validated config to `clusters/production/objects.yaml`
8. Push changes - pipeline generates plan
9. Manual approval gate triggered
10. Approve and deploy to production

**Postconditions:**
- Changes progressively validated across environments
- Production deployment only after successful dev/staging tests

### UC4: Team Collaboration on Large Ruleset

**Actor:** Multiple Network Engineers

**Preconditions:**
- Large firewall with 500+ rules
- Multi-file configuration enabled

**Flow:**
1. **Engineer A** works on `objects/trust-zone.yaml` (internal rules)
2. **Engineer B** works on `objects/dmz-zone.yaml` (DMZ rules)
3. Both push changes simultaneously
4. Git handles merge conflicts (different files → no conflicts)
5. Pipeline validates all files together
6. Terraform merges all addresses, services, rules automatically
7. Apply deploys both engineers' changes atomically

**Postconditions:**
- Parallel collaboration without conflicts
- All changes deployed together

---

## Success Criteria

### Technical Success

✅ **Schema Validation** - 100% of YAML configs pass schema validation before deployment
✅ **Pipeline Reliability** - 99%+ successful deployment rate (excluding intentional validation failures)
✅ **State Consistency** - Zero state corruption incidents
✅ **Multi-Vendor Support** - Successful deployments to PAN-OS, CheckPoint, F5 WAF

### User Success

✅ **Adoption Rate** - 80%+ of firewall changes via GitOps (vs manual CLI)
✅ **Merge Request Reviews** - 100% of production changes reviewed by security team
✅ **Configuration Consistency** - Zero configuration drift between Git and firewall
✅ **Audit Compliance** - 100% of changes traceable to Git commits

### Business Success

✅ **Time Savings** - 50%+ reduction in time to deploy firewall changes
✅ **Error Reduction** - 80%+ reduction in firewall misconfigurations
✅ **Collaboration Improvement** - 3x increase in number of engineers contributing changes
✅ **Incident Reduction** - 90%+ reduction in firewall-related outages

---

## Roadmap

### Phase 1: Core Platform (Completed ✅)
- PAN-OS module (Panorama + standalone)
- YAML parser with multi-file merging
- GitLab CI/CD pipeline (validate → plan → apply)
- JSON schema validation
- State management via GitLab HTTP backend

### Phase 2: Multi-Vendor Expansion (Completed ✅)
- CheckPoint module with automatic publish
- F5 WAF module for IP lists
- Vendor-specific documentation
- Position configuration (first/last/after/before/top/bottom/above/below)

### Phase 3: Enhanced Features (In Progress 🚧)
- Fortinet module implementation
- Advanced security profile management
- Enhanced logging configuration
- Terraform plan diff visualization in MRs

### Phase 4: Enterprise Features (Planned 📋)
- Multi-region deployments
- Disaster recovery automation
- Configuration drift detection
- Change impact analysis
- Slack/Teams notifications
- SOAR webhook service completion (Phases 02-05)

### Phase 5: Advanced Automation (Planned 📋)
- AI-powered rule optimization suggestions
- Automatic rule cleanup (unused rules detection)
- Compliance policy enforcement (NIST, PCI-DSS, ISO 27001)
- Integration with SIEM systems
- Real-time firewall health monitoring

---

## Technical Constraints

### Known Limitations

1. **Provider API Rate Limits** - PAN-OS/CheckPoint APIs have rate limits; large deployments may need throttling
2. **CheckPoint Session Timeout** - Default 600s; long-running applies may timeout (configurable)
3. **Terraform State Size** - Large clusters (1000+ rules) result in large state files (use S3 for scalability)
4. **Panorama Commit Time** - PAN-OS commits can take 5-10 minutes; use partial commits per-admin
5. **F5 iRule Limitations** - IP list size limited by iRule memory constraints

### Dependencies

- **Terraform** >= 1.0
- **Python** >= 3.8 (for validation scripts)
- **GitLab** >= 15.0 (for HTTP backend and resource groups)
- **PAN-OS Provider** >= 2.0.5
- **CheckPoint Provider** >= 2.11.0
- **F5 BIG-IP Provider** >= 1.24.0

---

## Risk Assessment

### High Risk
- **State Corruption** - Mitigation: GitLab state locking, regular backups
- **Production Outage** - Mitigation: Manual approval gates, Terraform plan review, rollback via Git revert

### Medium Risk
- **Provider API Changes** - Mitigation: Pin provider versions, test upgrades in dev first
- **Large Config Performance** - Mitigation: Multi-file splitting, parallel processing where possible

### Low Risk
- **YAML Syntax Errors** - Mitigation: Schema validation catches errors before deployment
- **Merge Conflicts** - Mitigation: Multi-file configuration reduces conflicts

---

## Open Questions

1. Should we support automatic rollback on apply failure?
2. Need integration with change management (ServiceNow, Jira)?
3. Should we implement automatic firewall health checks post-deployment?
4. Need support for emergency bypass (skip approval for critical incidents)?
5. Should we add cost estimation for multi-cloud firewall deployments?
