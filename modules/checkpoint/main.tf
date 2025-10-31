terraform {
  required_providers {
    checkpoint = {
      source  = "CheckPointSW/checkpoint"
      version = "~> 2.11.0"
    }
  }
}

locals {
  # Separate hosts (single IPs) from networks (subnets)
  # Hosts: /32 for IPv4 or single IP addresses
  # Networks: anything else with CIDR notation

  hosts = [
    for addr in var.firewall_addresses :
    addr if(
      addr.ip_netmask != null &&
      (can(regex("/32$", addr.ip_netmask)) || !can(regex("/", addr.ip_netmask)))
    ) || addr.fqdn != null
  ]

  networks = [
    for addr in var.firewall_addresses :
    addr if addr.ip_netmask != null &&
    can(regex("/", addr.ip_netmask)) &&
    !can(regex("/32$", addr.ip_netmask)) &&
    addr.fqdn == null
  ]

  # Separate TCP and UDP services
  tcp_services = [for svc in var.firewall_services : svc if svc.type == "tcp"]
  udp_services = [for svc in var.firewall_services : svc if svc.type == "udp"]

  # Global settings with defaults
  layer_name   = try(var.global.layer_name, "Network")
  auto_publish = try(var.global.auto_publish, true)
  install_on   = try(var.global.install_on, ["Policy Targets"])
  track_type   = try(var.global.track_type, "Log")
  track_settings = try(var.global.track_settings, {
    accounting              = false
    alert                   = "none"
    enable_firewall_session = false
    per_connection          = true
    per_session             = false
  })
}

# Create host objects (single IP addresses and FQDNs)
resource "checkpoint_management_host" "hosts" {
  for_each = { for host in local.hosts : host.name => host }

  name = each.value.name
  ipv4_address = each.value.fqdn == null ? (
    can(regex("/", each.value.ip_netmask)) ?
    split("/", each.value.ip_netmask)[0] :
    each.value.ip_netmask
  ) : null
  comments = each.value.description
  tags     = each.value.tags
  color    = "blue"

  ignore_warnings = true
  ignore_errors   = false
}

# Create network objects (subnets)
resource "checkpoint_management_network" "networks" {
  for_each = { for net in local.networks : net.name => net }

  name         = each.value.name
  subnet4      = can(regex("/", each.value.ip_netmask)) ? split("/", each.value.ip_netmask)[0] : null
  mask_length4 = can(regex("/", each.value.ip_netmask)) ? tonumber(split("/", each.value.ip_netmask)[1]) : null
  comments     = each.value.description
  tags         = each.value.tags
  color        = "blue"

  ignore_warnings = true
  ignore_errors   = false
}

# Create TCP service objects
resource "checkpoint_management_service_tcp" "tcp_services" {
  for_each = { for svc in local.tcp_services : svc.name => svc }

  name        = each.value.name
  port        = each.value.destination_port
  source_port = each.value.source_port
  comments    = each.value.description
  tags        = each.value.tags
  color       = "blue"

  ignore_warnings = true
  ignore_errors   = false
}

# Create UDP service objects
resource "checkpoint_management_service_udp" "udp_services" {
  for_each = { for svc in local.udp_services : svc.name => svc }

  name        = each.value.name
  port        = each.value.destination_port
  source_port = each.value.source_port
  comments    = each.value.description
  tags        = each.value.tags
  color       = "blue"

  ignore_warnings = true
  ignore_errors   = false
}

# Create access rules
resource "checkpoint_management_access_rule" "rules" {
  for_each = { for idx, rule in var.firewall_rules : rule.name => merge(rule, { index = idx }) }

  layer    = local.layer_name
  name     = each.value.name
  comments = each.value.description

  # Position: first rule goes to top, subsequent rules go below the previous one
  position = each.value.index == 0 ? {
    top = "top"
    } : var.position.where == "top" ? {
    top = "top"
    } : var.position.where == "bottom" ? {
    bottom = "bottom"
    } : var.position.where == "above" && var.position.pivot != null ? {
    above = var.position.pivot
    } : var.position.where == "below" && var.position.pivot != null ? {
    below = var.position.pivot
    } : {
    bottom = "bottom"
  }

  source             = each.value.source_addresses
  source_negate      = each.value.negate_source
  destination        = each.value.destination_addresses
  destination_negate = each.value.negate_destination
  service            = each.value.services
  vpn                = each.value.vpn
  action             = each.value.action
  enabled            = !each.value.disabled
  install_on         = local.install_on

  track = {
    type                    = each.value.log_end ? local.track_type : "None"
    accounting              = local.track_settings.accounting
    alert                   = local.track_settings.alert
    enable_firewall_session = local.track_settings.enable_firewall_session
    per_connection          = local.track_settings.per_connection
    per_session             = local.track_settings.per_session
  }

  ignore_warnings = true
  ignore_errors   = false

  depends_on = [
    checkpoint_management_host.hosts,
    checkpoint_management_network.networks,
    checkpoint_management_service_tcp.tcp_services,
    checkpoint_management_service_udp.udp_services
  ]
}

# Publish changes if auto_publish is enabled
resource "checkpoint_management_publish" "publish" {
  count = local.auto_publish ? 1 : 0

  triggers = [
    jsonencode(checkpoint_management_host.hosts),
    jsonencode(checkpoint_management_network.networks),
    jsonencode(checkpoint_management_service_tcp.tcp_services),
    jsonencode(checkpoint_management_service_udp.udp_services),
    jsonencode(checkpoint_management_access_rule.rules),
  ]

  depends_on = [
    checkpoint_management_host.hosts,
    checkpoint_management_network.networks,
    checkpoint_management_service_tcp.tcp_services,
    checkpoint_management_service_udp.udp_services,
    checkpoint_management_access_rule.rules
  ]
}
