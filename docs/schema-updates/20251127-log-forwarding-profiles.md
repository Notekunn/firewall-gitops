# Schema Updates: Log Forwarding Profiles Support

**Date:** 2025-11-27
**Schema Version:** v2.1
**Feature:** PAN-OS Log Forwarding Profiles

---

## Overview

The cluster configuration schema has been updated to support log forwarding profiles for Palo Alto Networks firewalls. This enhancement enables centralized logging configuration through YAML definitions that are validated by the JSON schema.

## New Schema Section

### `firewall.log_forwarding_profiles`

**Type:** Array of objects
**Required:** No
**Default:** `[]`

```json
{
  "log_forwarding_profiles": {
    "type": "array",
    "description": "List of log forwarding profiles for centralized logging configuration",
    "items": {
      "type": "object",
      "required": ["name", "match_list"],
      "additionalProperties": false,
      "properties": {
        "name": {
          "type": "string",
          "description": "Unique name for the log forwarding profile",
          "minLength": 1,
          "maxLength": 63,
          "pattern": "^[a-zA-Z0-9-_]+$",
          "examples": ["siem-forward", "default-logging", "traffic-only"]
        },
        "description": {
          "type": "string",
          "description": "Optional description for the log forwarding profile",
          "maxLength": 255,
          "default": ""
        },
        "match_list": {
          "type": "array",
          "description": "List of log type matches and forwarding configurations",
          "items": {
            "type": "object",
            "required": ["name", "log_type"],
            "additionalProperties": false,
            "properties": {
              "name": {
                "type": "string",
                "description": "Name for this match configuration",
                "minLength": 1,
                "maxLength": 63
              },
              "log_type": {
                "type": "string",
                "description": "Type of log to forward",
                "enum": ["traffic", "threat", "wildfire", "url", "data", "tunnel", "auth", "decryption"]
              },
              "send_to_panorama": {
                "type": "boolean",
                "description": "Send logs to Panorama instead of external destinations",
                "default": false
              },
              "syslog_profiles": {
                "type": "array",
                "description": "List of syslog server profile names",
                "items": {
                  "type": "string",
                  "minLength": 1
                },
                "default": []
              },
              "email_profiles": {
                "type": "array",
                "description": "List of email server profile names",
                "items": {
                  "type": "string",
                  "minLength": 1
                },
                "default": []
              },
              "http_profiles": {
                "type": "array",
                "description": "List of HTTP server profile names",
                "items": {
                  "type": "string",
                  "minLength": 1
                },
                "default": []
              },
              "snmp_profiles": {
                "type": "array",
                "description": "List of SNMP server profile names",
                "items": {
                  "type": "string",
                  "minLength": 1
                },
                "default": []
              }
            }
          },
          "minItems": 1
        }
      }
    },
    "default": [],
    "uniqueItems": true
  }
}
```

## Validation Features

### Profile Name Validation
- **Pattern:** `^[a-zA-Z0-9-_]+$`
- **Length:** 1-63 characters
- **Unique:** Profile names must be unique within a cluster

### Log Type Validation
**Supported Log Types:** `traffic`, `threat`, `wildfire`, `url`, `data`, `tunnel`, `auth`, `decryption`

### Destination Profile Validation
- **syslog_profiles:** Array of syslog server profile names
- **email_profiles:** Array of email server profile names
- **http_profiles:** Array of HTTP server profile names
- **snmp_profiles:** Array of SNMP server profile names
- **send_to_panorama:** Boolean to forward to Panorama instead

## Configuration Examples

### Basic Example
```yaml
firewall:
  type: palo-alto
  standalone:
    ngfw_device: 'firewall.example.com'
    vsys_name: 'vsys1'

  log_forwarding_profiles:
    - name: "default-logging"
      description: "Forward all logs to Panorama"
      match_list:
        - name: "traffic-to-panorama"
          log_type: "traffic"
          send_to_panorama: true
        - name: "threat-to-panorama"
          log_type: "threat"
          send_to_panorama: true
```

### SIEM Integration Example
```yaml
log_forwarding_profiles:
  - name: "siem-forwarding"
    description: "Forward security logs to SIEM"
    match_list:
      - name: "threat-to-siem"
        log_type: "threat"
        syslog_profiles: ["siem-syslog-primary", "siem-syslog-backup"]
        email_profiles: ["security-alerts"]
      - name: "wildfire-to-siem"
        log_type: "wildfire"
        http_profiles: ["siem-http-collector"]
  - name: "compliance-audit"
    description: "Audit trail for compliance"
    match_list:
      - name: "traffic-audit"
        log_type: "traffic"
        syslog_profiles: ["audit-syslog"]
      - name: "auth-audit"
        log_type: "auth"
        syslog_profiles: ["audit-syslog"]
```

## Integration with Rules

Log forwarding profiles are referenced in firewall rules using the `log_setting` field:

```yaml
rules:
  - name: "allow-web-access"
    description: "Allow web traffic with security logging"
    source_zones: ["trust"]
    destination_zones: ["untrust"]
    applications: ["web-browsing", "ssl"]
    services: ["application-default"]
    action: "allow"
    log_setting: "siem-forwarding"  # References profile above
    log_start: false
    log_end: true
```

## Backward Compatibility

The schema update is fully backward compatible:
- **Default Value:** Empty array (`[]`)
- **Optional Field:** Not required for existing configurations
- **No Breaking Changes:** Existing clusters continue to work without modification

## Terraform Variable Integration

The schema aligns with the Terraform variable definition in `modules/palo-alto/variables.tf`:

```hcl
variable "log_forwarding_profiles" {
  description = "List of log forwarding profiles for centralized logging"
  type = list(object({
    name        = string
    description = optional(string, "")
    match_list = list(object({
      name             = string
      log_type         = string
      send_to_panorama = optional(bool, false)
      syslog_profiles  = optional(list(string), [])
      email_profiles   = optional(list(string), [])
      http_profiles    = optional(list(string), [])
      snmp_profiles    = optional(list(string), [])
    }))
  }))
  default = []
}
```

## Validation Benefits

1. **Type Safety:** Ensures correct data structure
2. **Value Validation:** Prevents invalid log_type values
3. **Constraint Enforcement:** Name length and pattern validation
4. **Documentation:** Rich descriptions guide configuration
5. **Error Prevention:** Early validation catches issues before deployment

## Testing

### Valid Configuration Test
```bash
# Test valid configuration
python scripts/validate_yaml.py

# Should pass without errors
✓ cluster.yaml validation passed
✓ log_forwarding_profiles schema validation passed
```

### Invalid Configuration Test
```bash
# Example invalid configuration (bad log_type)
log_forwarding_profiles:
  - name: "invalid-profile"
    match_list:
      - name: "bad-log-type"
        log_type: "invalid-type"  # Not in enum

# Validation output:
ERROR: Invalid log_type 'invalid-type' in profile 'invalid-profile'
```

## Files Modified

- **`schemas/cluster.schema.json`:** Added log_forwarding_profiles validation
- **`modules/palo-alto/variables.tf`:** Added corresponding Terraform variable

## Next Steps

Phase 2 will implement YAML parser integration to read these configurations and pass them to the Terraform module for resource creation.

---

**Schema Compatibility:** ✅ Backward Compatible
**Validation Status:** ✅ Tested and Working
**Implementation Phase:** ✅ Phase 1 Complete