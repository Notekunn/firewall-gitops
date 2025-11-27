# PaloAltoNetworks Terraform Provider Research
## Log Forwarding Profiles & Schedule Objects

**Date:** 2025-11-27
**Provider:** PaloAltoNetworks/panos (v2.0.0+)
**Research Status:** Complete with findings & recommendations

---

## Executive Summary

Log forwarding profiles are **available & documented** in panos provider with full support for NGFW and Panorama. Schedule objects are **NOT available as dedicated resources** in current panos Terraform provider versions (tested through v2.0.6). This report details findings, integration patterns, and recommended implementation approaches.

---

## 1. Log Forwarding Profile Resources

### Available Resources

#### NGFW (Standalone Firewall)
```
Resource Name: panos_log_forwarding_profile
Type: Provider Resource
Location: modules/palo-alto/
```

#### Panorama (Centralized Management)
```
Resource Name: panos_panorama_log_forwarding_profile
Type: Provider Resource
Location: modules/panorama/
```

### Required Arguments

| Argument | Type | Description | Required |
|----------|------|-------------|----------|
| `name` | String | Profile identifier | Yes |
| `description` | String | Human-readable profile description | No |
| `match_list` | Block | Log matching & forwarding configuration | Yes (min 1) |

### Match List Block Structure

```hcl
match_list {
  name             = string  # Identifier for this log category
  log_type         = string  # Type of logs to match
  send_to_panorama = bool    # Panorama forwarding flag
}
```

#### Supported Log Types

From provider analysis (v2.0.0+):
- `traffic` - Traffic logs
- `threat` - Threat prevention logs
- `wildfire` - WildFire logs
- `url` - URL filtering logs
- `data` - Data filtering logs
- `tunnel` - Tunnel logs
- `auth` - Authentication logs
- `decryption` - SSL/TLS decryption logs (added v2.0.0+)

### NGFW Example Configuration

```hcl
resource "panos_log_forwarding_profile" "web_traffic" {
  name        = "log-forward-web"
  description = "Forward web traffic and threat logs"

  match_list {
    name             = "Forward-Traffic-Logs"
    log_type         = "traffic"
    send_to_panorama = false
  }

  match_list {
    name             = "Forward-Threat-Logs"
    log_type         = "threat"
    send_to_panorama = false
  }
}
```

### Panorama Example Configuration

```hcl
resource "panos_panorama_log_forwarding_profile" "central_logging" {
  name        = "panorama-log-forwarding"
  description = "Central log forwarding policy"

  match_list {
    name             = "Forward-Decryption"
    log_type         = "decryption"
    send_to_panorama = true
  }

  match_list {
    name             = "Forward-All-Threats"
    log_type         = "threat"
    send_to_panorama = true
  }
}
```

### Integration with Security Rules

Security policy rules reference log forwarding profiles via:

```hcl
resource "panos_security_policy_rules" "example" {
  # ... other rule config ...

  log_setting = panos_log_forwarding_profile.web_traffic.name
}
```

Or for Panorama:

```hcl
resource "panos_security_policy_rules" "example" {
  # ... other rule config ...

  log_setting = panos_panorama_log_forwarding_profile.central_logging.name
}
```

### YAML Integration Pattern

For GitOps implementation, store log forwarding profiles in `cluster.yaml`:

```yaml
log_forwarding_profiles:
  - name: "web-logs"
    description: "Web application logging"
    match_list:
      - name: "traffic"
        log_type: "traffic"
        send_to_panorama: false
      - name: "threat"
        log_type: "threat"
        send_to_panorama: false

rules:
  - name: "allow-web"
    # ... rule config ...
    log_setting: "web-logs"
```

Parse & iterate in `modules/palo-alto/main.tf`:

```hcl
# Create log forwarding profiles
resource "panos_log_forwarding_profile" "profiles" {
  for_each    = { for p in var.log_forwarding_profiles : p.name => p }

  name        = each.value.name
  description = try(each.value.description, "")

  dynamic "match_list" {
    for_each = each.value.match_list
    content {
      name             = match_list.value.name
      log_type         = match_list.value.log_type
      send_to_panorama = try(match_list.value.send_to_panorama, false)
    }
  }
}
```

### Known Issues & Fixes

- **Issue #305**: Missing "decryption" log type in log forwarding profiles
  - **Status**: CLOSED/RESOLVED (v2.0.0+)
  - **Fix**: Decryption log type now supported via auto-codegen

---

## 2. Schedule Objects

### Availability Status: NOT AVAILABLE

**Finding:** Schedule objects are NOT available as dedicated Terraform resources in the panos provider (v2.0.0 through current).

#### Evidence
1. **No resource documentation** on Terraform Registry for `panos_schedule` or `panos_schedule_object`
2. **GitHub repository search** yields zero results for schedule resource implementation
3. **Availability in other tools:**
   - ✅ **Ansible**: `panos_schedule_object` module exists in paloaltonetworks.panos collection
   - ❌ **Terraform**: No equivalent resource found
   - ✅ **PAN-OS API**: Schedule objects available via REST/XML APIs

#### Alternative: Syslog Server Profiles

Closest comparable resource for *log scheduling/forwarding*:

```
Resource Name: panos_syslog_server_profile
NGFW: panos_syslog_server_profile
Panorama: panos_panorama_syslog_server_profile
```

While not true schedules, these can forward logs to syslog servers with configuration.

### Recommended Implementation Approaches

#### Option 1: Use Ansible with Terraform (Hybrid)
Pair Terraform provider with Ansible module for schedules:

```hcl
# Terraform for main firewall config
resource "panos_log_forwarding_profile" "main" {
  name = "production-logging"
  # ... config ...
}

# Execute Ansible playbook via local-exec for schedules
resource "null_resource" "schedule_objects" {
  provisioner "local-exec" {
    command = "ansible-playbook configure_schedules.yml"
  }

  depends_on = [panos_log_forwarding_profile.main]
}
```

**ansible playbook example:**
```yaml
- name: Create schedule objects
  panos_schedule_object:
    provider: '{{ panos_provider }}'
    name: 'business-hours'
    recurring:
      - monday: '09:00-17:00'
      - tuesday: '09:00-17:00'
      - wednesday: '09:00-17:00'
      - thursday: '09:00-17:00'
      - friday: '09:00-17:00'
```

#### Option 2: Direct PAN-OS API via HTTP Provider

Use Terraform's `http` provider to call PAN-OS REST API directly:

```hcl
resource "http_request" "schedule_object" {
  url    = "https://${var.panorama_hostname}/restapi/v10.0/Objects/ScheduleObjects"
  method = "POST"

  headers = {
    "X-PAN-KEY" = var.panos_api_key
    "Content-Type" = "application/json"
  }

  request_body = jsonencode({
    entry = [{
      name = "business-hours"
      recurring = {
        monday = "09:00-17:00"
        tuesday = "09:00-17:00"
        # ... other days
      }
    }]
  })
}
```

#### Option 3: Request Feature from PaloAlto

File feature request with PaloAlto for schedule object Terraform resource:
- **Link:** [terraform-provider-panos Issues](https://github.com/PaloAltoNetworks/terraform-provider-panos/issues)
- **Precedent:** Issue #305 (decryption log type) was resolved via community request

#### Option 4: Custom Terraform Module

Create wrapper module managing schedules via PAN-OS API (requires panos API SDK in Go):

```hcl
module "panos_schedules" {
  source = "./modules/schedule-objects"

  panorama_host = var.panorama_hostname
  api_key       = var.panos_api_key

  schedules = [
    {
      name = "business-hours"
      recurrence = "weekdays-9-17"
    }
  ]
}
```

---

## 3. Integration Patterns with Existing System

### YAML Structure Update (cluster.yaml)

```yaml
firewall:
  panorama_device: "panorama.example.com"
  device_group: "production"

# ✅ New: Log forwarding profiles
log_forwarding_profiles:
  - name: "central-logging"
    description: "Forward to SIEM"
    match_list:
      - name: "all-traffic"
        log_type: "traffic"
        send_to_panorama: true

# ❌ Not supported yet: Direct schedule objects
# Use Ansible playbook alternative:
schedules:
  - name: "business-hours"
    type: "recurring"
    recurrence: "Mon-Fri 09:00-17:00"
```

### Module Integration (modules/palo-alto/main.tf)

```hcl
# Add log forwarding profiles support
variable "log_forwarding_profiles" {
  description = "Log forwarding profile configurations"
  type = list(object({
    name        = string
    description = optional(string)
    match_list = list(object({
      name             = string
      log_type         = string
      send_to_panorama = optional(bool, false)
    }))
  }))
  default = []
}

resource "panos_log_forwarding_profile" "profiles" {
  for_each    = { for p in var.log_forwarding_profiles : p.name => p }
  name        = each.value.name
  description = try(each.value.description, "")

  dynamic "match_list" {
    for_each = each.value.match_list
    content {
      name             = match_list.value.name
      log_type         = match_list.value.log_type
      send_to_panorama = match_list.value.send_to_panorama
    }
  }
}

# Output for rule references
output "log_forwarding_profiles" {
  value = { for name, profile in panos_log_forwarding_profile.profiles : name => profile.name }
}
```

### Security Rule Integration

```hcl
resource "panos_security_policy_rules" "rules" {
  for_each = { for r in var.firewall_rules : r.name => r }

  name        = each.value.name
  action      = each.value.action
  log_setting = try(
    panos_log_forwarding_profile.profiles[each.value.log_setting].name,
    ""
  )

  # ... other rule attributes ...
}
```

### YAML Configuration Example

```yaml
# clusters/production/cluster.yaml
firewall:
  type: "panos"
  panorama:
    device: "panorama-prod.internal"
    device_group: "prod-firewalls"

log_forwarding:
  profiles:
    - name: "siem-forward"
      description: "Forward to Splunk SIEM"
      match_list:
        - name: "traffic-logs"
          log_type: "traffic"
          send_to_panorama: false
        - name: "threat-logs"
          log_type: "threat"
          send_to_panorama: false

# clusters/production/objects.yaml
rules:
  - name: "allow-http"
    source: ["trust"]
    destination: ["untrust"]
    service: ["service-http"]
    action: "allow"
    log_setting: "siem-forward"
    log_start: true
    log_end: false
```

---

## 4. Recommendations

### For Log Forwarding Profiles

✅ **Implement immediately:**
1. Add `log_forwarding_profiles` block to `cluster.yaml`
2. Create `panos_log_forwarding_profile` resources in module
3. Update security rules to reference profiles via `log_setting`
4. Support both NGFW and Panorama variants

**YAML-first approach** maintains consistency with existing GitOps pattern.

### For Schedule Objects

⚠️ **Current situation:** Not available in Terraform provider

**Recommended approach:**
1. **Short-term:** Use Ansible `panos_schedule_object` module
2. **Medium-term:** File feature request with PaloAlto
3. **Long-term:** Monitor provider releases for native support

**Hybrid implementation:**
```hcl
module "log_forwarding" {
  # Managed by Terraform
  source = "./modules/palo-alto"
  log_forwarding_profiles = local.log_profiles
}

# Schedules managed externally
resource "null_resource" "schedules" {
  provisioner "local-exec" {
    command = "ansible-playbook setup-schedules.yml"
  }
  depends_on = [module.log_forwarding]
}
```

### Implementation Priority

| Component | Priority | Status | Implementation |
|-----------|----------|--------|-----------------|
| Log Forwarding (NGFW) | High | Available | Terraform resource |
| Log Forwarding (Panorama) | High | Available | Terraform resource |
| Schedule Objects | Medium | Not Available | Ansible module |
| Log Settings Blocks | High | Available | YAML in objects |

### Best Practices

1. **One profile per log category** for flexibility:
   ```hcl
   panos_log_forwarding_profile.traffic
   panos_log_forwarding_profile.threat
   panos_log_forwarding_profile.decryption
   ```

2. **Panorama-first strategy** when available:
   - Reduces rule duplication
   - Centralized policy management
   - Easier log correlation

3. **Store profiles in cluster.yaml** for transparency:
   - Single source of truth
   - Easy to audit changes
   - Consistent with YAML-first GitOps approach

4. **Use `for_each` loops** for dynamic resource creation:
   - Scales with profile count
   - Enables flexible YAML structure
   - Supports partial updates

5. **Explicit dependencies** in rules:
   ```hcl
   depends_on = [panos_log_forwarding_profile.profiles]
   ```

---

## 5. Source Documentation & References

### Official Palo Alto Networks Resources
- [Terraform Registry - panos Provider](https://registry.terraform.io/providers/PaloAltoNetworks/panos/latest/docs)
- [panos_log_forwarding_profile Resource](https://registry.terraform.io/providers/PaloAltoNetworks/panos/latest/docs/resources/log_forwarding_profile)
- [panos_panorama_log_forwarding_profile Resource](https://registry.terraform.io/providers/PaloAltoNetworks/panos/latest/docs/resources/panorama_log_forwarding_profile)
- [PAN-OS Terraform Documentation](https://pan.dev/terraform/docs/panos/)

### Provider Versions Tested
- v2.0.0 (initial release with auto-codegen)
- v2.0.1-v2.0.6 (subsequent releases)
- No schedule objects in any tested version

### Related Issues
- [Issue #305: Add support for "decryption" log type](https://github.com/PaloAltoNetworks/terraform-provider-panos/issues/305) - CLOSED/RESOLVED
- [Issue #403: panos_syslog_server_profile stack trace](https://github.com/PaloAltoNetworks/terraform-provider-panos/issues/403)
- [Issue #437: user_id_format parameter changes not deploying](https://github.com/PaloAltoNetworks/terraform-provider-panos/issues/437)

### Ansible Alternative
- [Ansible Collection - panos_schedule_object](https://paloaltonetworks.github.io/pan-os-ansible/modules/panos_schedule_object_module.html)

---

## 6. Unresolved Questions

1. **Schedule Objects Timeline:** When will PaloAlto add native Terraform schedule object resources?
2. **API Compatibility:** Can newer PAN-OS versions (11.0+) manage schedules via REST API instead of XML?
3. **Multi-config Performance:** Do log forwarding profiles benefit from v2.0.0+ multi-config performance improvements?
4. **Log Field Filtering:** Can match_list blocks filter by specific log fields (source IP, user, etc.)?

---

## Implementation Files

This research informs:
1. **YAML Schema** - Update for log_forwarding_profiles block
2. **Terraform Module** - Add panos_log_forwarding_profile resources
3. **Rule Processing** - Map cluster.yaml log_setting to profiles
4. **Ansible Playbook** - Schedule object creation (if needed)

**Next Steps:**
- Review plan at: `/Users/notekunn/workspaces/side-project/pet-project/devops/firewall-gitops/plans/20251127-0838-palo-alto-log-schedule/`
- Reference this research in implementation tasks
