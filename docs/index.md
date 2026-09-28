# Firewall GitOps Documentation Index

## Quick Start

- **[README.md](../README.md)** - Getting started guide, setup, and basic usage
- **[CLAUDE.md](../CLAUDE.md)** - Project guidance for Claude Code (development guide)

## Architecture & Implementation

- **[codebase-summary.md](codebase-summary.md)** - Comprehensive codebase overview and file analysis
- **[system-architecture.md](system-architecture.md)** - System architecture and component interactions
- **[project-overview-pdr.md](project-overview-pdr.md)** - Product Development Requirements
- **[code-standards.md](code-standards.md)** - Coding standards and conventions

## API Reference

- **[api-docs.md](api-docs.md)** - API documentation and resource references

## Development Guides

- **[GitOps Workflow](../README.md#gitops-workflow)** - Development and deployment workflow
- **[Multi-File YAML Support](../README.md#multi-file-yaml-organization)** - Split configurations across multiple files
- **[CI/CD Pipeline](../.gitlab-ci.yml)** - GitLab pipeline configuration and stages
- **[Manual V2 State Migration](v2-state-migration.md)** - Backup, import, plan review, apply, verification, and rollback runbook

## Vendor-Specific Documentation

### Palo Alto Networks (PAN-OS)

- **Supported Features:**
  - Address objects (IP ranges, FQDNs, wildcards)
  - Service objects (TCP/UDP)
  - Security policy rules with profiles
  - Log forwarding profiles _(NEW: Phase 1 Complete)_
- **Deployment Modes:**
  - Standalone NGFW
  - Panorama-managed (pre/post rulebase)

### Check Point

- **Supported Features:**
  - Host and network objects
  - TCP/UDP services
  - Access policy rules
  - Automatic publishing

### F5 BIG-IP WAF

- **Supported Features:**
  - IP lists for allow/deny
  - iRule-based traffic filtering
  - Partition-based deployment

## Configuration Examples

- **[clusters/example/](../clusters/example/)** - Example PAN-OS standalone configuration
- **[clusters/development/](../clusters/development/)** - CheckPoint development configuration
- **[clusters/production/](../clusters/production/)** - PAN-OS Panorama production configuration

## Troubleshooting

- **[Debugging YAML Merge Issues](../CLAUDE.md#debugging-yaml-merge-issues)** - Terraform console debugging
- **[Common Errors](../README.md#troubleshooting)** - Validation and deployment errors
- **[GitLab CI/CD Issues](../.gitlab-ci.yml)** - Pipeline troubleshooting

## Reference Materials

- **[JSON Schema Specification](https://json-schema.org/)** - Schema validation reference
- **[Terraform Provider Documentation](../README.md#provider-configuration)** - External provider docs
- **[GitLab Terraform State](https://docs.gitlab.com/ee/user/infrastructure/iac/terraform_state.html)** - State management

## Quick Reference

### Environment Variables

```bash
# GitLab State Backend
export GITLAB_TOKEN="your-token"
export GITLAB_API_URL="https://gitlab.com/api/v4"
export GITLAB_USERNAME="your-username"

# PAN-OS Provider
export PANOS_HOSTNAME="firewall.example.com"
export PANOS_USERNAME="admin"
export PANOS_PASSWORD="password"  # or PANOS_API_KEY

# CheckPoint Provider
export CHECKPOINT_SERVER="mgmt.example.com"
export CHECKPOINT_USERNAME="admin"
export CHECKPOINT_PASSWORD="password"
export CHECKPOINT_CONTEXT="web_api"

# F5 Provider
export BIGIP_HOST="bigip.example.com"
export BIGIP_USER="admin"
export BIGIP_PASSWORD="password"
```

### Common Commands

```bash
# Validate configurations
python scripts/validate_yaml.py

# Format Terraform
tofu fmt -recursive

# Plan deployment
./scripts/deploy.sh -c <cluster> -a plan

# Apply changes
./scripts/deploy.sh -c <cluster> -a apply -y

# PAN-OS commit
./scripts/commit.sh
```

## Getting Help

- **Issues:** Report bugs and feature requests via GitLab issues
- **Documentation:** Update this index for missing information
- **Development:** See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines

---

**Last Updated:** 2025-11-27
**Documentation Version:** v2.1
**Next Update:** After Phase 2 completion
