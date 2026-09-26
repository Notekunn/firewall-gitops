terraform {
  required_providers {
    fortios = {
      source  = "fortinetdev/fortios"
      version = ">= 1.23.0"
    }
  }
}

locals {
  address_map = { for addr in var.firewall_addresses : addr.name => addr }
  service_map = { for svc in var.firewall_services : svc.name => svc }
  rule_map = {
    for idx, rule in var.firewall_rules :
    format("%03d-%s", idx, rule.name) => rule
  }
  action_map = {
    allow  = "accept"
    accept = "accept"
    deny   = "deny"
    drop   = "deny"
    reset  = "deny"
  }
}

resource "fortios_firewall_address" "addresses" {
  for_each = local.address_map

  name     = each.value.name
  comment  = trimspace(each.value.description) != "" ? each.value.description : null
  type     = each.value.fqdn != null ? "fqdn" : each.value.ip_range != null ? "iprange" : each.value.ip_wildcard != null ? "wildcard" : "ipmask"
  subnet   = each.value.ip_netmask != null ? format("%s %s", cidrhost(each.value.ip_netmask, 0), cidrnetmask(each.value.ip_netmask)) : null
  start_ip = each.value.ip_range != null ? trimspace(split("-", each.value.ip_range)[0]) : null
  end_ip   = each.value.ip_range != null ? trimspace(split("-", each.value.ip_range)[1]) : null
  wildcard = each.value.ip_wildcard != null ? replace(each.value.ip_wildcard, "/", " ") : null
  fqdn     = each.value.fqdn
}

resource "fortios_firewallservice_custom" "services" {
  for_each = local.service_map

  name            = each.value.name
  category        = "General"
  comment         = trimspace(each.value.description) != "" ? each.value.description : null
  protocol_number = each.value.type == "tcp" ? 6 : 17
  tcp_portrange   = each.value.type == "tcp" && coalesce(each.value.destination_port, "") != "" ? each.value.destination_port : null
  udp_portrange   = each.value.type == "udp" && coalesce(each.value.destination_port, "") != "" ? each.value.destination_port : null
  visibility      = "enable"
}

resource "fortios_firewall_policy" "rules" {
  for_each = local.rule_map

  name             = each.value.name
  comments         = trimspace(each.value.description) != "" ? each.value.description : null
  action           = lookup(local.action_map, lower(each.value.action), "accept")
  schedule         = coalesce(each.value.schedule, "always")
  status           = each.value.disabled ? "disable" : "enable"
  logtraffic       = each.value.log_end ? "all" : each.value.log_start ? "utm" : "disable"
  logtraffic_start = each.value.log_start ? "enable" : "disable"
  srcaddr_negate   = each.value.negate_source ? "enable" : "disable"
  dstaddr_negate   = each.value.negate_destination ? "enable" : "disable"

  dynamic "srcintf" {
    for_each = each.value.source_zones
    content {
      name = srcintf.value
    }
  }

  dynamic "dstintf" {
    for_each = each.value.destination_zones
    content {
      name = dstintf.value
    }
  }

  dynamic "srcaddr" {
    for_each = [for addr in each.value.source_addresses : addr == "any" ? "all" : addr]
    content {
      name = srcaddr.value
    }
  }

  dynamic "dstaddr" {
    for_each = [for addr in each.value.destination_addresses : addr == "any" ? "all" : addr]
    content {
      name = dstaddr.value
    }
  }

  dynamic "service" {
    for_each = [for svc in each.value.services : svc == "any" ? "ALL" : svc]
    content {
      name = service.value
    }
  }

  depends_on = [
    fortios_firewall_address.addresses,
    fortios_firewallservice_custom.services
  ]
}
