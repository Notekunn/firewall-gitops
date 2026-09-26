terraform {
  required_providers {
    panos = {
      source  = "paloaltonetworks/panos"
      version = "2.0.13"
    }
  }
}

locals {
  location = var.location

  # panos_schedule location shape differs from rule location:
  # flat {device_group|vsys|shared} object, no nested `panorama` wrapper.
  schedule_location = var.location.panorama != null ? {
    device_group = {
      name            = var.location.panorama.device_group
      panorama_device = var.location.panorama.panorama_device
    }
    } : (var.location.vsys != null ? {
      vsys = {
        name        = var.location.vsys.name
        ngfw_device = var.location.vsys.ngfw_device
      }
      } : (var.location.shared != null ? {
        shared = {}
  } : null))
}

resource "panos_addresses" "address_objects" {
  location = local.location
  addresses = {
    for addr in var.firewall_addresses : addr.name => {
      description = addr.description
      tag         = addr.tags
      ip_netmask  = lookup(addr, "ip_netmask", null)
      ip_range    = lookup(addr, "ip_range", null)
      ip_wildcard = lookup(addr, "ip_wildcard", null)
      fqdn        = lookup(addr, "fqdn", null)
    }
  }
}

resource "panos_service" "service_objects" {
  for_each = { for svc in var.firewall_services : svc.name => svc }

  location    = local.location
  name        = each.value.name
  description = each.value.description
  protocol = {
    for protocol in [each.value.type] : protocol => {
      destination_port = each.value.destination_port
      source_port      = each.value.source_port
      tag              = each.value.tags
    }
  }
}

resource "panos_schedule" "schedules" {
  for_each = { for s in var.firewall_schedules : s.name => s }

  location         = local.schedule_location
  name             = each.value.name
  disable_override = each.value.disable_override
  schedule_type    = each.value.schedule_type
}

resource "panos_security_policy_rules" "firewall_rules" {
  location = local.location
  position = {
    where    = var.position.where
    pivot    = var.position.pivot
    directly = var.position.directly
  }
  depends_on = [
    panos_addresses.address_objects,
    panos_service.service_objects,
    panos_schedule.schedules,
  ]
  rules = [
    for rule in var.firewall_rules : {
      name                  = rule.name
      description           = rule.description
      rule_type             = rule.rule_type
      tag                   = rule.tags
      group_tag             = rule.group_tag
      negate_source         = rule.negate_source
      negate_destination    = rule.negate_destination
      disabled              = rule.disabled
      action                = rule.action
      source_zones          = rule.source_zones
      destination_zones     = rule.destination_zones
      source_addresses      = rule.source_addresses
      source_users          = rule.source_users
      destination_addresses = rule.destination_addresses
      applications          = rule.applications
      services              = rule.services
      log_start             = rule.log_start
      log_end               = rule.log_end
      log_setting           = rule.log_setting != null ? rule.log_setting : var.global.log_setting
      schedule              = rule.schedule
      audit_comment_wo      = rule.change != null ? "${rule.change.ticket}: ${rule.change.comment}" : null
      audit_comment_version = rule.change != null ? tostring(rule.change.revision) : null
      profile_setting = rule.profile_setting != null ? {
        group = rule.profile_setting.group
        profiles = rule.profile_setting.profiles != null ? {
          virus             = rule.profile_setting.profiles.virus
          spyware           = rule.profile_setting.profiles.spyware
          vulnerability     = rule.profile_setting.profiles.vulnerability
          url_filtering     = rule.profile_setting.profiles.url_filtering
          file_blocking     = rule.profile_setting.profiles.file_blocking
          wildfire_analysis = rule.profile_setting.profiles.wildfire_analysis
          data_filtering    = rule.profile_setting.profiles.data_filtering
        } : null
      } : null
    }
  ]
}
