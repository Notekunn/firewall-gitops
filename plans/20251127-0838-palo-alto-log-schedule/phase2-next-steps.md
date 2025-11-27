# Phase 2: YAML Parser Integration - Next Steps

**Phase:** 2 of 6
**Status:** Ready to Begin
**Estimated Effort:** 1-2 hours
**Dependencies:** Phase 1 Complete ✅

---

## Executive Summary

Phase 2 will implement the YAML parser integration to read `log_forwarding_profiles` from cluster configuration files and pass them to the Palo Alto module for resource creation.

## Implementation Tasks

### 1. Update terraform/main.tf Parser

**File:** `terraform/main.tf`

**Location:** Lines ~12-79 (existing YAML parsing logic)

**Required Changes:**
```hcl
# Add to locals block (after existing parsing logic)
locals {
  # ... existing locals ...

  # Parse cluster configuration
  cluster_config = yamldecode(file("${path.module}/../clusters/${var.cluster_name}/cluster.yaml"))

  # NEW: Extract log forwarding profiles from cluster config
  log_forwarding_profiles = try(local.cluster_config.firewall.log_forwarding_profiles, [])

  # ... rest of existing locals ...
}
```

### 2. Update Module Invocation

**File:** `terraform/main.tf`

**Location:** Lines ~84-97 (palo-alto module call)

**Required Changes:**
```hcl
module "palo_alto_firewall" {
  count = local.firewall_config.type == "palo-alto" ? 1 : 0

  source = "../modules/palo-alto"

  # Existing parameters
  firewall_rules    = local.firewall_rules
  firewall_addresses = local.firewall_addresses
  firewall_services  = local.firewall_services
  position          = local.position_config
  location          = local.location_config

  # NEW: Pass log forwarding profiles
  log_forwarding_profiles = local.log_forwarding_profiles

  global = {
    log_setting = try(local.cluster_config.firewall.log_setting, null)
  }
}
```

## Implementation Details

### Parsing Logic Strategy

1. **Graceful Handling:** Use `try()` to handle missing profiles
2. **Default Behavior:** Empty array when no profiles defined
3. **Error Handling:** YAML syntax errors handled by existing error logic
4. **Backward Compatibility:** No impact on existing clusters

### Integration Points

#### Existing Parser Structure (Reference)
```hcl
# terraform/main.tf:12-50
locals {
  cluster_dir   = "${path.module}/../clusters/${var.cluster_name}"
  cluster_config = yamldecode(file("${cluster_dir}/cluster.yaml"))

  # Single file vs multi-file detection
  objects_file = "${cluster_dir}/objects.yaml"
  objects_dir  = "${cluster_dir}/objects"

  # Multi-file mode detection
  is_multi_file = fileexists(local.objects_dir) && !fileexists(local.objects_file)

  # Parse objects (addresses, services, rules)
  # ... existing logic ...
}
```

#### New Integration Point
```hcl
# Add after cluster_config parsing
log_forwarding_profiles = try(local.cluster_config.firewall.log_forwarding_profiles, [])
```

## Testing Strategy

### 1. Configuration File Tests

**Test Case 1: Profiles Present**
```yaml
# clusters/test/cluster.yaml
cluster:
  name: test-cluster
  environment: development

firewall:
  type: palo-alto
  standalone:
    ngfw_device: localhost.localdomain
    vsys_name: vsys1

  log_forwarding_profiles:
    - name: "test-profile"
      description: "Test profile"
      match_list:
        - name: "traffic-test"
          log_type: "traffic"
          send_to_panorama: true
```

**Expected Result:** `local.log_forwarding_profiles` contains profile object

**Test Case 2: No Profiles**
```yaml
# clusters/test/cluster.yaml
cluster:
  name: test-cluster
  environment: development

firewall:
  type: palo-alto
  standalone:
    ngfw_device: localhost.localdomain
    vsys_name: vsys1

  log_setting: "global-setting"
```

**Expected Result:** `local.log_forwarding_profiles` = `[]`

**Test Case 3: Empty Profiles Array**
```yaml
# clusters/test/cluster.yaml
firewall:
  log_forwarding_profiles: []
```

**Expected Result:** `local.log_forwarding_profiles` = `[]`

### 2. Terraform Console Tests

```bash
cd terraform
terraform init

# Test with example cluster
export TF_VAR_cluster_name=example
terraform console

# Verify parser output
> local.log_forwarding_profiles
[
  {
    "description" = "Default log forwarding to Panorama"
    "match_list" = [
      {
        "log_type" = "traffic"
        "name" = "traffic-to-panorama"
        "send_to_panorama" = true
      },
      {
        "log_type" = "threat"
        "name" = "threat-to-panorama"
        "send_to_panorama" = true
      }
    ]
    "name" = "default-logging"
  },
]

> var.palo_alto_firewall[0].log_forwarding_profiles
# Should show same data passed to module
```

### 3. Plan Tests

```bash
# Create Terraform plan
./scripts/deploy.sh -c example -a plan

# Verify plan includes log forwarding profiles
terraform show -json plan-example.tfplan | jq '.planned_values.module_calls.palo_alto_firewall[0].expressions.log_forwarding_profiles.value'
```

## Error Handling

### Expected Errors and Solutions

1. **Invalid YAML Syntax**
   - **Detection:** Existing YAML decode error handling
   - **Solution:** Same error messaging as other cluster config errors

2. **Invalid Log Type**
   - **Detection:** Terraform variable validation (from Phase 1)
   - **Solution:** Clear error message about valid log types

3. **Schema Validation Failure**
   - **Detection:** JSON schema validation in Python script
   - **Solution:** Detailed validation errors with field locations

### Error Message Examples

```
Error: Invalid value for variable

  on terraform/main.tf line 101, in locals:
  101:   log_forwarding_profiles = try(local.cluster_config.firewall.log_forwarding_profiles, [])

Invalid log type "invalid" in match list. Valid log types are:
- traffic
- threat
- wildfire
- url
- data
- tunnel
- auth
- decryption
```

## Backward Compatibility Testing

### Existing Cluster Test
```bash
# Test with existing cluster without log_forwarding_profiles
./scripts/deploy.sh -c existing-cluster -a plan

# Expected: Plan succeeds, no profile resources created
# Expected: log_forwarding_profiles = []
```

## Integration Checklist

- [ ] Update terraform/main.tf locals block
- [ ] Update palo-alto module invocation
- [ ] Test with example cluster containing profiles
- [ ] Test with existing cluster without profiles
- [ ] Verify Terraform plan shows correct profiles
- [ ] Test error handling for invalid configurations
- [ ] Run full validation pipeline
- [ ] Update documentation

## Files to Modify

| File | Type | Changes |
|------|------|---------|
| `terraform/main.tf` | Modified | Add profile parsing logic |
| No new files required | | |

## Success Criteria

- [ ] Parser correctly extracts log_forwarding_profiles from YAML
- [ ] Empty array returned when profiles not defined
- [ ] Profiles passed to module correctly
- [ ] Existing clusters continue to work without modification
- [ ] Terraform plan shows correct resource creation intent
- [ ] Error messages are clear and actionable

## Phase Dependencies

### Prerequisites
- ✅ Phase 1 Complete (Schema & Variables)
- ✅ Module variable definition exists
- ✅ JSON schema validation working

### Next Phases
- Phase 3: Module Resource Implementation (panos_log_forwarding_profile)
- Phase 4: Example Configuration Updates
- Phase 5: Validation & Testing
- Phase 6: Documentation Updates

## Rollback Plan

If issues arise during Phase 2:

1. **Immediate Rollback:** Remove `log_forwarding_profiles` parameter from module call
2. **Parser Rollback:** Remove profile extraction from locals block
3. **Fallback:** System reverts to Phase 1 state (variables defined but not used)
4. **Testing:** Verify existing functionality unaffected

## Ready to Begin

Phase 2 is ready to begin with:
- ✅ Phase 1 foundation complete
- ✅ Clear implementation path identified
- ✅ Comprehensive testing strategy
- ✅ Backward compatibility assured
- ✅ Rollback plan documented

**Estimated Timeline:** 1-2 hours
**Risk Level:** Low (based on solid Phase 1 foundation)