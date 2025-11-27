# Research Summary: PaloAlto Log Forwarding & Schedules

## Key Findings

### ✅ Log Forwarding Profiles - AVAILABLE

**Resources:**
- `panos_log_forwarding_profile` (NGFW)
- `panos_panorama_log_forwarding_profile` (Panorama)

**Log Types Supported:**
- traffic, threat, wildfire, url, data, tunnel, auth, decryption

**Integration:**
```hcl
resource "panos_log_forwarding_profile" "main" {
  name = "central-logging"

  match_list {
    name     = "forward-traffic"
    log_type = "traffic"
    send_to_panorama = true
  }
}

resource "panos_security_policy_rules" "rule" {
  log_setting = panos_log_forwarding_profile.main.name
}
```

---

### ❌ Schedule Objects - NOT AVAILABLE in Terraform

**Status:** No `panos_schedule` or `panos_schedule_object` resource in panos provider

**Alternatives:**
1. **Ansible Module** - `panos_schedule_object` available in paloaltonetworks.panos collection
2. **Direct API** - Use `http` provider to call PAN-OS REST API
3. **Hybrid Approach** - Terraform for profiles, Ansible for schedules

**Recommended Workaround:**
```hcl
resource "null_resource" "schedules" {
  provisioner "local-exec" {
    command = "ansible-playbook setup-schedules.yml"
  }
  depends_on = [panos_log_forwarding_profile.main]
}
```

---

## Implementation Plan

### For Log Forwarding (IMMEDIATE)

1. Add to `cluster.yaml`:
   ```yaml
   log_forwarding_profiles:
     - name: "prod-logging"
       match_list:
         - name: "traffic"
           log_type: "traffic"
         - name: "threat"
           log_type: "threat"
   ```

2. Update module to create resources:
   ```hcl
   resource "panos_log_forwarding_profile" "profiles" {
     for_each = { for p in var.log_forwarding_profiles : p.name => p }
     # ... config from YAML ...
   }
   ```

3. Reference in rules:
   ```hcl
   log_setting = panos_log_forwarding_profile.profiles[rule.log_setting].name
   ```

### For Schedules (DEFERRED)

**Current Blockers:**
- No Terraform resource available
- Request feature from PaloAlto or use Ansible

**Recommended:** Store schedule config in separate YAML, manage via Ansible until Terraform support available.

---

## Documentation

Full research report: `/Users/notekunn/workspaces/side-project/pet-project/devops/firewall-gitops/plans/20251127-0838-palo-alto-log-schedule/research/researcher-01-provider-resources.md`

**Contains:**
- Complete argument reference
- Code examples (NGFW & Panorama)
- YAML-to-Terraform integration patterns
- Known issues & resolution status
- Best practices & implementation priority
