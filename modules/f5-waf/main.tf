terraform {
  required_providers {
    bigip = {
      source  = "F5Networks/bigip"
      version = "~> 1.24.1"
    }
  }
}

locals {
  partition = var.location.partition

  # Flatten domain blocklists and whitelists
  domain_blocklists = {
    for domain, lists in var.ip_lists.domains : domain => lists.blocklist
    if length(lists.blocklist) > 0
  }
  domain_whitelists = {
    for domain, lists in var.ip_lists.domains : domain => lists.whitelist
    if length(lists.whitelist) > 0
  }

  # Normalize domain names for resource naming (replace dots with underscores)
  domain_blocklist_names = {
    for domain, ips in local.domain_blocklists : domain => replace(domain, ".", "_")
  }
  domain_whitelist_names = {
    for domain, ips in local.domain_whitelists : domain => replace(domain, ".", "_")
  }
}

# Global blocklist data group
resource "bigip_ltm_datagroup" "global_blocklist" {
  count = length(var.ip_lists.global.blocklist) > 0 ? 1 : 0

  name = "/${local.partition}/global_blocklist"
  type = "ip"

  dynamic "record" {
    for_each = var.ip_lists.global.blocklist
    content {
      name = record.value
    }
  }
}

# Global whitelist data group
resource "bigip_ltm_datagroup" "global_whitelist" {
  count = length(var.ip_lists.global.whitelist) > 0 ? 1 : 0

  name = "/${local.partition}/global_whitelist"
  type = "ip"

  dynamic "record" {
    for_each = var.ip_lists.global.whitelist
    content {
      name = record.value
    }
  }
}

# Per-domain blocklist data groups
resource "bigip_ltm_datagroup" "domain_blocklist" {
  for_each = local.domain_blocklists

  name = "/${local.partition}/${local.domain_blocklist_names[each.key]}_blocklist"
  type = "ip"

  dynamic "record" {
    for_each = each.value
    content {
      name = record.value
    }
  }
}

# Per-domain whitelist data groups
resource "bigip_ltm_datagroup" "domain_whitelist" {
  for_each = local.domain_whitelists

  name = "/${local.partition}/${local.domain_whitelist_names[each.key]}_whitelist"
  type = "ip"

  dynamic "record" {
    for_each = each.value
    content {
      name = record.value
    }
  }
}

# iRule for XFF-based IP filtering
resource "bigip_ltm_irule" "ip_filter" {
  name = "/${local.partition}/${var.global.irule_name}"

  irule = <<-EOF
when HTTP_REQUEST {
  set xff [HTTP::header CF-Connecting-IP]
  #set host [HTTP::host]

  # blocklist
  if { [class match $xff equals global_blocklist] } { 
    log local0. "Blocked client IP $xff (matched Data Group)"
    HTTP::respond 403 content "Access denied"
    return
  }
  #if { [class match $xff equals $${host}_blocklist] } { reject }
}
EOF

  depends_on = [
    bigip_ltm_datagroup.global_blocklist,
    bigip_ltm_datagroup.global_whitelist,
    bigip_ltm_datagroup.domain_blocklist,
    bigip_ltm_datagroup.domain_whitelist
  ]
}
