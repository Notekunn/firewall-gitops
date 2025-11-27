# Implementation Plan: PAN-OS Log Forwarding Profiles & Schedule Objects

**Plan ID:** 20251127-0838-palo-alto-log-schedule
**Created:** 2025-11-27 08:38:28 ICT
**Status:** Phase 1 Complete - Ready for Phase 2
**Phase 1 Complete:** 2025-11-27 15:45:00 ICT
**Phase 1 Report:** [reports/20251127-phase1-completion-report.md](reports/20251127-phase1-completion-report.md)

---

## Executive Summary

Implement log forwarding profile management for Palo Alto Networks firewalls in the GitOps workflow. Schedule objects are NOT available in Terraform provider and will be deferred.

### Scope
- ✅ **IN SCOPE**: Log forwarding profiles (NGFW & Panorama)
- ❌ **OUT OF SCOPE**: Schedule objects (not supported by provider)

### Impact
- Enables centralized logging configuration via YAML
- Supports both standalone NGFW and Panorama deployments
- Backward compatible with existing configurations

---

## Research Summary

Research report: `plans/20251127-0838-palo-alto-log-schedule/research/researcher-01-provider-resources.md`

### Key Findings

**Log Forwarding Profiles:**
- Available resources: `panos_log_forwarding_profile`, `panos_panorama_log_forwarding_profile`
- Supports 8 log types: traffic, threat, wildfire, url, data, tunnel, auth, decryption
- Integrates with security rules via `log_setting` field

**Schedule Objects:**
- No Terraform resource available in panos provider v2.x
- Alternative: Ansible module `panos_schedule_object`
- Recommendation: Defer implementation, document limitation

---

## Solution Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    YAML Configuration                        │
│  clusters/<cluster>/cluster.yaml                             │
│    - log_forwarding_profiles: [...]                          │
│  clusters/<cluster>/objects.yaml                             │
│    - rules:                                                   │
│      - log_setting: "profile-name"                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              terraform/main.tf (Parser)                      │
│  - Read log_forwarding_profiles from cluster.yaml            │
│  - Merge with existing config                                │
│  - Pass to module                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          modules/palo-alto/main.tf                           │
│  - Create panos_log_forwarding_profile resources             │
│  - Link to security rules via log_setting                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 PAN-OS Firewall                              │
│  - Log forwarding profiles created                           │
│  - Rules reference profiles                                  │
└─────────────────────────────────────────────────────────────┘
```

### YAML Schema Design

**cluster.yaml:**
```yaml
log_forwarding_profiles:
  - name: "siem-forward"
    description: "Forward logs to SIEM"
    match_list:
      - name: "traffic-logs"
        log_type: "traffic"
        send_to_panorama: false
        syslog_profiles: ["syslog-siem"]
        email_profiles: []
        http_profiles: []
      - name: "threat-logs"
        log_type: "threat"
        send_to_panorama: false
        syslog_profiles: ["syslog-siem"]
```

**objects.yaml (rules):**
```yaml
rules:
  - name: "allow-web"
    action: "allow"
    log_setting: "siem-forward"  # Reference profile
    log_start: true
    log_end: true
```

---

## Implementation Phases

### Phase 1: Schema & Variables (Core) ✅ **COMPLETED**
**Completed:** 2025-11-27 15:45:00 ICT
**Files:** `modules/palo-alto/variables.tf`, `schemas/cluster.schema.json`

**Tasks Completed:**
1. ✅ Added `log_forwarding_profiles` variable to palo-alto module
2. ✅ Updated cluster schema to validate profiles
3. ✅ Added profile validation rules with enum validation

**Accomplishments:**
- Variable definition added with proper type constraints and validation
- JSON schema updated with comprehensive validation for log types
- Support for all 8 log types: traffic, threat, wildfire, url, data, tunnel, auth, decryption
- Optional fields properly handled with defaults
- Integration points established for Phase 2

**Code Changes:**
```hcl
# modules/palo-alto/variables.tf
variable "log_forwarding_profiles" {
  type = list(object({
    name        = string
    description = optional(string, "")
    match_list = list(object({
      name                  = string
      log_type              = string  # traffic, threat, wildfire, url, data, tunnel, auth, decryption
      send_to_panorama      = optional(bool, false)
      syslog_profiles       = optional(list(string), [])
      email_profiles        = optional(list(string), [])
      http_profiles         = optional(list(string), [])
      snmp_profiles         = optional(list(string), [])
      log_forwarding_profile = optional(string, null)
    }))
  }))
  default = []
}
```

**JSON Schema:**
```json
{
  "log_forwarding_profiles": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["name", "match_list"],
      "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "match_list": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "log_type"],
            "properties": {
              "name": {"type": "string"},
              "log_type": {
                "type": "string",
                "enum": ["traffic", "threat", "wildfire", "url", "data", "tunnel", "auth", "decryption"]
              },
              "send_to_panorama": {"type": "boolean"},
              "syslog_profiles": {"type": "array", "items": {"type": "string"}},
              "email_profiles": {"type": "array", "items": {"type": "string"}},
              "http_profiles": {"type": "array", "items": {"type": "string"}}
            }
          }
        }
      }
    }
  }
}
```

---

### Phase 2: YAML Parser Integration
**Files:** `terraform/main.tf`

**Tasks:**
1. Read `log_forwarding_profiles` from cluster.yaml
2. Pass to palo-alto module
3. Handle null/missing profiles gracefully

**Code Changes:**
```hcl
# terraform/main.tf (add to locals)
locals {
  # ... existing locals ...

  # Log forwarding profiles from cluster config
  log_forwarding_profiles = try(local.cluster_config.log_forwarding_profiles, [])
}

# Update palo-alto module call
module "palo_alto_firewall" {
  count = local.firewall_config.type == "palo-alto" ? 1 : 0

  source = "../modules/palo-alto"

  firewall_rules              = local.firewall_rules
  firewall_addresses          = local.firewall_addresses
  firewall_services           = local.firewall_services
  log_forwarding_profiles     = local.log_forwarding_profiles  # NEW
  position                    = local.position_config
  location                    = local.location_config
  global = {
    log_setting = try(local.cluster_config.log_setting, null)
  }
}
```

---

### Phase 3: Module Resource Implementation
**Files:** `modules/palo-alto/main.tf`

**Tasks:**
1. Create `panos_log_forwarding_profile` resource
2. Use `for_each` for multiple profiles
3. Dynamic `match_list` blocks
4. Handle NGFW vs Panorama locations

**Code Changes:**
```hcl
# modules/palo-alto/main.tf
resource "panos_log_forwarding_profile" "profiles" {
  for_each = { for p in var.log_forwarding_profiles : p.name => p }

  location    = local.location
  name        = each.value.name
  description = try(each.value.description, "")

  dynamic "match_list" {
    for_each = each.value.match_list
    content {
      name             = match_list.value.name
      log_type         = match_list.value.log_type
      send_to_panorama = try(match_list.value.send_to_panorama, false)

      syslog_profiles  = try(match_list.value.syslog_profiles, null)
      email_profiles   = try(match_list.value.email_profiles, null)
      http_profiles    = try(match_list.value.http_profiles, null)
      snmp_profiles    = try(match_list.value.snmp_profiles, null)
    }
  }
}

# Update security rules to reference profiles
resource "panos_security_policy_rules" "firewall_rules" {
  location   = local.location
  position   = var.position
  depends_on = [
    panos_addresses.address_objects,
    panos_service.service_objects,
    panos_log_forwarding_profile.profiles  # NEW DEPENDENCY
  ]

  rules = [
    for rule in var.firewall_rules : {
      # ... existing fields ...
      log_setting = coalesce(
        rule.log_setting,  # Per-rule override
        try(var.global.log_setting, null)  # Global default
      )
      # ... remaining fields ...
    }
  ]
}
```

---

### Phase 4: Example Configuration
**Files:** `clusters/example/cluster.yaml`, `clusters/example/objects.yaml`

**Tasks:**
1. Add example log forwarding profile
2. Update rules to use profile
3. Document configuration patterns

**Example Configuration:**
```yaml
# clusters/example/cluster.yaml
cluster:
  name: 'example-cluster'
  environment: development

firewall:
  type: palo-alto
  standalone:
    ngfw_device: 'localhost.localdomain'
    vsys_name: 'vsys1'

# NEW: Log forwarding profiles
log_forwarding_profiles:
  - name: "default-logging"
    description: "Default log forwarding to Panorama"
    match_list:
      - name: "traffic-to-panorama"
        log_type: "traffic"
        send_to_panorama: true
      - name: "threat-to-panorama"
        log_type: "threat"
        send_to_panorama: true

position:
  where: last
```

```yaml
# clusters/example/objects.yaml
rules:
  - name: "allow-web-traffic"
    description: "Allow HTTP/HTTPS"
    source_zones: [trust]
    destination_zones: [untrust]
    applications: [web-browsing, ssl]
    services: [application-default]
    action: allow
    log_setting: "default-logging"  # Reference profile
    log_start: false
    log_end: true
```

---

### Phase 5: Validation & Testing
**Files:** `scripts/validate_yaml.py`

**Tasks:**
1. Update validation script to check log_type enum
2. Validate profile references in rules
3. Test with example cluster

**Validation Logic:**
```python
# Validate log_type values
VALID_LOG_TYPES = ["traffic", "threat", "wildfire", "url", "data", "tunnel", "auth", "decryption"]

def validate_log_forwarding_profiles(profiles):
    for profile in profiles:
        for match in profile.get("match_list", []):
            log_type = match.get("log_type")
            if log_type not in VALID_LOG_TYPES:
                raise ValueError(f"Invalid log_type: {log_type}")
```

**Test Commands:**
```bash
# Validate configuration
python scripts/validate_yaml.py

# Plan deployment
./scripts/deploy.sh -c example -a plan

# Verify plan output
terraform show -json plan-example.tfplan | jq '.resource_changes[] | select(.type == "panos_log_forwarding_profile")'
```

---

### Phase 6: Documentation
**Files:** `docs/codebase-summary.md`, `CLAUDE.md`, `README.md`

**Tasks:**
1. Document log forwarding profile configuration
2. Add examples to README
3. Update CLAUDE.md with architecture details
4. Note schedule limitation

**Documentation Additions:**
```markdown
## Log Forwarding Profiles

Configure centralized logging for firewall events.

### Configuration

**cluster.yaml:**
```yaml
log_forwarding_profiles:
  - name: "siem-forward"
    description: "Forward to SIEM"
    match_list:
      - name: "traffic"
        log_type: "traffic"
        syslog_profiles: ["syslog-siem"]
```

**objects.yaml:**
```yaml
rules:
  - name: "allow-web"
    log_setting: "siem-forward"
```

### Supported Log Types
- traffic, threat, wildfire, url, data, tunnel, auth, decryption

### Limitations
- Schedule objects not supported in Terraform provider
- Use `log_setting` field in rules to reference profiles
```

---

## File Changes Summary

| File | Type | Changes |
|------|------|---------|
| `modules/palo-alto/variables.tf` | Modified | Add `log_forwarding_profiles` variable |
| `modules/palo-alto/main.tf` | Modified | Add `panos_log_forwarding_profile` resource |
| `terraform/main.tf` | Modified | Parse & pass profiles to module |
| `schemas/cluster.schema.json` | Modified | Add profile validation schema |
| `clusters/example/cluster.yaml` | Modified | Add example profile config |
| `clusters/example/objects.yaml` | Modified | Add `log_setting` to rules |
| `docs/codebase-summary.md` | Modified | Document profiles |
| `CLAUDE.md` | Modified | Architecture details |
| `README.md` | Modified | Usage examples |

**Total:** 9 files modified, 0 new files

---

## Testing Strategy

### Unit Tests
1. YAML schema validation
2. Terraform validate
3. Terraform plan (dry-run)

### Integration Tests
1. Deploy to example cluster
2. Verify profile creation in PAN-OS
3. Verify rule references
4. Test profile updates

### Test Cases

**TC-01: Single Profile**
```yaml
log_forwarding_profiles:
  - name: "basic"
    match_list:
      - name: "traffic"
        log_type: "traffic"
        send_to_panorama: true
```
Expected: Profile created, no errors

**TC-02: Multiple Profiles**
```yaml
log_forwarding_profiles:
  - name: "traffic-logs"
    match_list: [...]
  - name: "threat-logs"
    match_list: [...]
```
Expected: Both profiles created

**TC-03: Profile Reference in Rules**
```yaml
rules:
  - name: "test"
    log_setting: "traffic-logs"
```
Expected: Rule references profile

**TC-04: Missing Profile (Error)**
```yaml
rules:
  - name: "test"
    log_setting: "non-existent"
```
Expected: Terraform error (reference not found)

**TC-05: Invalid Log Type (Error)**
```yaml
match_list:
  - log_type: "invalid-type"
```
Expected: Schema validation error

---

## Migration Guide

### Existing Configurations

**Before:**
```yaml
# cluster.yaml
log_setting: "default-logging"  # Global setting only

# objects.yaml
rules:
  - name: "rule1"
    log_end: true  # Basic logging
```

**After:**
```yaml
# cluster.yaml
log_forwarding_profiles:
  - name: "default-logging"
    match_list:
      - name: "traffic"
        log_type: "traffic"
        send_to_panorama: true

log_setting: "default-logging"  # Still supported as global default

# objects.yaml
rules:
  - name: "rule1"
    log_setting: "default-logging"  # Can override global
    log_end: true
```

**Backward Compatibility:**
- Global `log_setting` still works
- Per-rule `log_setting` overrides global
- Existing configs continue to work

---

## Known Limitations

### Schedule Objects
**Status:** NOT IMPLEMENTED
**Reason:** No Terraform resource in panos provider v2.x

**Workarounds:**
1. **Ansible Integration:**
   ```yaml
   - name: Create schedule
     paloaltonetworks.panos.panos_schedule_object:
       name: "business-hours"
       schedule_type: "recurring"
       recurring_weekly:
         monday: ["09:00-17:00"]
   ```

2. **Direct API:**
   ```hcl
   resource "null_resource" "schedule" {
     provisioner "local-exec" {
       command = "curl -X POST https://firewall/api/..."
     }
   }
   ```

3. **Manual Configuration:**
   - Create schedules manually in PAN-OS
   - Reference by name in YAML rules

**Recommendation:** Document limitation, defer implementation until provider support added

---

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Breaking existing configs | HIGH | LOW | Maintain backward compatibility |
| Invalid log_type values | MEDIUM | MEDIUM | JSON schema validation |
| Profile reference errors | MEDIUM | MEDIUM | Terraform dependency management |
| Provider version mismatch | MEDIUM | LOW | Pin provider version >= 2.0.5 |

---

## Success Criteria

**Phase 1 Completed:**
- [x] Schema validation prevents errors

**Remaining Criteria:**
- [ ] Log forwarding profiles configurable via YAML
- [ ] Multiple profiles supported per cluster
- [ ] Profiles integrate with security rules
- [ ] NGFW and Panorama modes both work
- [ ] Backward compatible with existing configs
- [ ] Documentation complete
- [ ] Example cluster demonstrates usage
- [ ] All tests pass

---

## Timeline Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Schema & Variables | 1 hour | None |
| Phase 2: Parser Integration | 1 hour | Phase 1 |
| Phase 3: Module Resources | 2 hours | Phase 2 |
| Phase 4: Examples | 30 min | Phase 3 |
| Phase 5: Validation | 1 hour | Phase 4 |
| Phase 6: Documentation | 1 hour | Phase 5 |

**Total Estimated Effort:** 6.5 hours

---

## References

### Research Documents
- [Full Research Report](research/researcher-01-provider-resources.md)

### External Documentation
- [PAN-OS Terraform Provider](https://registry.terraform.io/providers/PaloAltoNetworks/panos/latest/docs)
- [panos_log_forwarding_profile Resource](https://registry.terraform.io/providers/PaloAltoNetworks/panos/latest/docs/resources/log_forwarding_profile)
- [PAN-OS Developer Docs](https://pan.dev/terraform/docs/panos/)
- [Provider GitHub](https://github.com/PaloAltoNetworks/terraform-provider-panos)

### Related Issues
- Schedule object support: https://github.com/PaloAltoNetworks/terraform-provider-panos/issues/305

---

## Next Steps

**Phase 1 Completed ✅**
- Schema and variable definitions implemented
- JSON schema validation added
- Ready for Phase 2 implementation

**Immediate Next Steps:**
1. **Phase 2: YAML Parser Integration** - Update terraform/main.tf to parse and pass profiles
2. **Phase 3: Module Resource Implementation** - Create panos_log_forwarding_profile resources
3. **Phase 4: Example Configuration** - Add example cluster with profiles
4. **Phase 5: Validation & Testing** - Update validation scripts and test
5. **Phase 6: Documentation** - Complete documentation updates

**Development Sequence:**
1. Begin Phase 2 (Parser Integration)
2. Code review after Phase 2 completion
3. Continue with remaining phases sequentially
4. Final validation and documentation

---

## Appendix: Code Snippets

### Complete Variable Definition
```hcl
variable "log_forwarding_profiles" {
  description = "List of log forwarding profiles for centralized logging"
  type = list(object({
    name        = string
    description = optional(string, "")
    match_list = list(object({
      name                  = string
      log_type              = string  # Enum validated by schema
      send_to_panorama      = optional(bool, false)
      syslog_profiles       = optional(list(string), [])
      email_profiles        = optional(list(string), [])
      http_profiles         = optional(list(string), [])
      snmp_profiles         = optional(list(string), [])
    }))
  }))
  default = []

  validation {
    condition = alltrue([
      for profile in var.log_forwarding_profiles : alltrue([
        for match in profile.match_list :
          contains(["traffic", "threat", "wildfire", "url", "data", "tunnel", "auth", "decryption"], match.log_type)
      ])
    ])
    error_message = "log_type must be one of: traffic, threat, wildfire, url, data, tunnel, auth, decryption"
  }
}
```

### Complete Resource Implementation
```hcl
resource "panos_log_forwarding_profile" "profiles" {
  for_each = { for p in var.log_forwarding_profiles : p.name => p }

  location    = local.location
  name        = each.value.name
  description = try(each.value.description, "")

  dynamic "match_list" {
    for_each = each.value.match_list
    content {
      name             = match_list.value.name
      log_type         = match_list.value.log_type
      send_to_panorama = try(match_list.value.send_to_panorama, false)

      # Optional log forwarding destinations
      syslog_profiles  = length(try(match_list.value.syslog_profiles, [])) > 0 ? match_list.value.syslog_profiles : null
      email_profiles   = length(try(match_list.value.email_profiles, [])) > 0 ? match_list.value.email_profiles : null
      http_profiles    = length(try(match_list.value.http_profiles, [])) > 0 ? match_list.value.http_profiles : null
      snmp_profiles    = length(try(match_list.value.snmp_profiles, [])) > 0 ? match_list.value.snmp_profiles : null
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

---

**Plan Status:** PHASE 1 COMPLETE - IN PROGRESS
**Phase 1 Complete:** 2025-11-27 15:45:00 ICT
**Next Phase:** Phase 2 - YAML Parser Integration
**Implementation Start:** PHASE 2 READY
