# Code Standards & Best Practices

## Overview

Coding conventions for Firewall GitOps project following YAGNI-KISS-DRY principles.

---

## Terraform Standards

### Formatting
- Two-space indentation
- Run `terraform fmt -recursive` before commit

### Naming
- Snake_case for variables/resources/locals/outputs
- Descriptive resource names: `address_objects`, `service_objects`

### Optional Fields
```hcl
# Use lookup() for optional YAML fields
ip_netmask = lookup(each.value, "ip_netmask", null)
description = lookup(each.value, "description", null)
tags = lookup(each.value, "tags", [])
```

### Dependencies
```hcl
# Explicit depends_on when needed
resource "panos_security_policy_rules" "rules" {
  depends_on = [panos_addresses.address_objects, panos_service.service_objects]
}
```

### Iteration
- Prefer `for_each` over `count` for resources
- Use `count` for conditional creation

---

## YAML Standards

### Formatting
- Two-space indentation (no tabs)
- Quote strings with special chars: `'192.168.1.100/32'`
- Single quotes preferred

### Naming
- Lowercase with hyphens: `web-server-01`, `db-primary-prod`
- Descriptive rule names: `allow-web-traffic`, `deny-external-ssh`

### File Organization
**Single file:** `objects.yaml` (addresses → services → rules)
**Multi-file:** `objects/*.yaml` (descriptive names: `trust-zone.yaml`, `dmz-zone.yaml`)

### Validation
```bash
python scripts/validate_yaml.py
```

---

## Python Standards

### Style
- PEP 8: 4-space indentation, 88-char line length
- Snake_case functions/variables, PascalCase classes

### Type Hints
```python
def validate_cluster(cluster_path: Path) -> Dict[str, bool]:
    """Validate cluster configuration."""
    # ...
```

### Error Handling
```python
try:
    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)
except FileNotFoundError:
    print(f"Error: File not found: {yaml_file}")
    sys.exit(1)
```

### CLI Entry
```python
if __name__ == "__main__":
    main()
```

---

## Bash Standards

### Shebang
```bash
#!/usr/bin/env bash
set -euo pipefail
```

### Variables
- UPPERCASE for env vars: `GITLAB_TOKEN`
- lowercase for local: `cluster_name`
- Always quote: `"${variable}"`

### Functions
```bash
setup_backend() {
    local cluster_name="${1}"
    # ...
}
```

---

## Git Commit Standards

### Conventional Commits
Format: `<type>(<scope>): <description>`

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `docs:` - Documentation
- `chore:` - Maintenance
- `test:` - Tests

**Examples:**
```
feat(palo-alto): add security profile support
fix(checkpoint): correct host/network classification
docs: update README with multi-file config
```

### Message Guidelines
- Max 50 chars for subject
- Imperative mood: "add" not "added"
- Lowercase after colon
- One logical change per commit

---

## File Naming

### Terraform
- `main.tf`, `variables.tf`, `outputs.tf`
- Module-specific: lowercase with hyphens

### YAML
- `cluster.yaml` (required exact name)
- `objects.yaml` OR `objects/*.yaml`
- Multi-file: descriptive names (`addresses.yaml`, `trust-zone.yaml`)

### Scripts
- Lowercase with extension: `deploy.sh`, `validate_yaml.py`

### Documentation
- Lowercase with hyphens: `project-overview-pdr.md`, `code-standards.md`

---

## Security Standards

### Never Commit
- API keys, passwords, tokens, certificates

### Use Environment Variables
```bash
export PANOS_PASSWORD="secret"
export GITLAB_TOKEN="token"
```

### Input Validation
```python
def validate_ip_address(ip: str) -> bool:
    pattern = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
    return bool(re.match(pattern, ip))
```

### Least Privilege
- Default deny, explicit allow
- Specific zones/addresses (avoid "any")
- Log denied traffic

---

## CI/CD Standards

### Pipeline Stages
1. validate - YAML + Terraform checks
2. plan - Generate plans
3. apply - Deploy changes
4. cleanup - Remove artifacts

### Job Naming
Pattern: `<action>_<cluster>`
Examples: `validate_yaml`, `plan_production`, `apply_development`

### Artifacts
```yaml
artifacts:
  paths:
    - plan-${CLUSTER_NAME}.tfplan
  expire_in: 1 week
```

### Resource Groups
```yaml
resource_group: terraform-${CLUSTER_NAME}
```

---

## Code Review Checklist

### Before MR
- [ ] YAML validation passes
- [ ] Terraform fmt/validate passes
- [ ] Plan reviewed locally
- [ ] No secrets committed
- [ ] Commit messages follow conventions

### Reviewer Checks
- [ ] Changes match description
- [ ] Plan output reviewed
- [ ] No security risks
- [ ] Variable names follow conventions
- [ ] Documentation updated

---

## Common Anti-Patterns

### ❌ Hardcoding Values
```hcl
vsys = "vsys1"  # Bad - should come from config
vsys = try(var.location.vsys.vsys_name, null)  # Good
```

### ❌ Overly Permissive Rules
```yaml
# Bad
action: allow
source_zones: [any]
services: [any]

# Good
action: allow
source_zones: [trust]
services: [https-service]
```

### ❌ Missing Error Handling
```python
# Bad
data = yaml.safe_load(open(file))

# Good
try:
    with open(file, 'r') as f:
        data = yaml.safe_load(f)
except FileNotFoundError:
    print(f"Error: {file} not found")
    sys.exit(1)
```

---

## Editor Configuration

### VS Code Extensions
- HashiCorp Terraform
- YAML
- Python
- ShellCheck

### Settings
```json
{
  "editor.formatOnSave": true,
  "terraform.format.enable": true,
  "yaml.schemas": {
    "schemas/cluster.schema.json": "clusters/*/cluster.yaml",
    "schemas/rules.schema.json": ["clusters/*/objects.yaml", "clusters/*/objects/*.yaml"]
  }
}
```

---

## Reference

- Terraform Style: https://developer.hashicorp.com/terraform/language/style
- Python PEP 8: https://peps.python.org/pep-0008/
- Conventional Commits: https://www.conventionalcommits.org/
