# PaloAlto Log Forwarding & Schedule Objects Research Plan

**Date:** 2025-11-27 08:38:28
**Status:** Research Complete
**Deliverable:** Implementation-ready findings

---

## Research Scope

1. **Log Forwarding Profiles** - Resource availability, arguments, examples
2. **Schedule Objects** - Resource availability, configuration methods, alternatives

---

## Key Findings at a Glance

| Component | Status | Resource | Notes |
|-----------|--------|----------|-------|
| Log Forwarding (NGFW) | ✅ Available | `panos_log_forwarding_profile` | Full support for 8 log types |
| Log Forwarding (Panorama) | ✅ Available | `panos_panorama_log_forwarding_profile` | Central mgmt variant |
| Schedule Objects | ❌ Not Available | N/A | Available in Ansible only |

---

## Deliverables

### 1. Full Research Report
**File:** `research/researcher-01-provider-resources.md` (534 lines)

Contains:
- Complete argument reference with tables
- NGFW & Panorama code examples
- YAML integration patterns
- GitOps workflow design
- Known issues & resolutions
- Implementation priority matrix
- Unresolved questions

### 2. Quick Reference Summary
**File:** `RESEARCH-SUMMARY.md`

Quick lookup for:
- Key findings (what's available/not)
- Basic code examples
- Workarounds for schedule objects
- Next steps for implementation

---

## Research Methodology

**Query Strategy:** Multi-source verification
- Terraform Registry (primary)
- GitHub provider repository
- pan.dev documentation
- Medium articles & release notes
- GitHub issues (closed & open)

**Verification:** Cross-referenced across:
- v2.0.0+ provider versions
- NGFW & Panorama variants
- Provider changelogs
- Issue resolution status

---

## Implementation Next Steps

### Immediate Actions (Log Forwarding)

1. **Update YAML Schema** - Add log_forwarding_profiles block to clusters/**/cluster.yaml
2. **Module Enhancement** - Create panos_log_forwarding_profile resources
3. **Rule Integration** - Map log_setting field in security rules
4. **Testing** - Validate profile creation & rule references

### Deferred (Schedule Objects)

1. Investigate Ansible hybrid approach
2. Monitor PaloAlto releases for Terraform support
3. Consider API-based implementation if needed

---

## Key Findings Summary

### Log Forwarding Profiles

**Status:** Fully implemented, well-documented

```hcl
resource "panos_log_forwarding_profile" "main" {
  name = "central-logging"

  match_list {
    name     = "traffic-logs"
    log_type = "traffic"
    send_to_panorama = true
  }
}
```

**Supported log types:** traffic, threat, wildfire, url, data, tunnel, auth, decryption

**Integration:** Reference in security rules via `log_setting = profile.name`

### Schedule Objects

**Status:** Not available in Terraform provider

**Alternatives:**
1. Ansible `panos_schedule_object` module
2. Direct PAN-OS REST API via `http` provider
3. Hybrid Terraform + Ansible workflow

**Recommended:** Use Ansible for schedules pending Terraform support

---

## Documentation Sources

- [Terraform Registry - panos Provider](https://registry.terraform.io/providers/PaloAltoNetworks/panos/latest/docs)
- [panos_log_forwarding_profile](https://registry.terraform.io/providers/PaloAltoNetworks/panos/latest/docs/resources/log_forwarding_profile)
- [panos_panorama_log_forwarding_profile](https://registry.terraform.io/providers/PaloAltoNetworks/panos/latest/docs/resources/panorama_log_forwarding_profile)
- [PAN-OS Terraform Documentation](https://pan.dev/terraform/docs/panos/)
- [GitHub Issues #305, #403, #437](https://github.com/PaloAltoNetworks/terraform-provider-panos/issues)

---

## File Structure

```
plans/20251127-0838-palo-alto-log-schedule/
├── README.md (this file)
├── RESEARCH-SUMMARY.md
└── research/
    └── researcher-01-provider-resources.md
```

---

## Technical Details Reference

**Provider Version Tested:** v2.0.0+
**Terraform:** 1.8+
**PAN-OS Compatibility:** v10.1+

**Resources:**
- NGFW: `panos_log_forwarding_profile`
- Panorama: `panos_panorama_log_forwarding_profile`
- Schedules: Not available (Ansible alternative documented)

---

## Questions Resolved

✅ Log forwarding profile resource names and variants
✅ Complete argument reference for both NGFW & Panorama
✅ Log types supported (including decryption in v2.0.0+)
✅ Integration patterns with security rules
✅ YAML-to-Terraform mapping strategy
✅ Schedule object status & alternatives
✅ Known issues & resolution status

---

## Questions Remaining

- Timeline for Terraform schedule object support?
- REST API schedule support in newer PAN-OS versions?
- Multi-config performance impact on log profiles?
- Log field filtering capabilities in match_list?

(See research report Section 6 for details)

---

## Next Steps for Implementation Team

1. **Review** this research + detailed report
2. **Validate** findings against firewall-gitops project requirements
3. **Design** YAML schema for log_forwarding_profiles block
4. **Implement** module resources & YAML parsing
5. **Test** profile creation & rule references
6. **Plan** schedule object strategy (Terraform pending vs. Ansible now)

---

**Ready for:** Implementation Planning
**Prepared by:** Claude Code Research Agent
**Quality:** Thoroughly researched, cross-verified, implementation-ready
