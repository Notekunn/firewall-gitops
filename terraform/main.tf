terraform {
  required_providers {
    panos = {
      source  = "paloaltonetworks/panos"
      version = "~> 2.0.5"
    }
  }
  backend "http" {}
}

# Data sources to read YAML configuration files
locals {
  # Get cluster name from environment variable or directory structure
  cluster_name = var.cluster_name != "" ? var.cluster_name : basename(abspath(path.module))

  # Read cluster configuration
  cluster_config_raw = file("${path.module}/../clusters/${local.cluster_name}/cluster.yaml")
  cluster_config     = yamldecode(local.cluster_config_raw)

  # Read firewall rules configuration
  firewall_rules_raw = file("${path.module}/../clusters/${local.cluster_name}/rules.yaml")
  firewall_rules     = yamldecode(local.firewall_rules_raw)

  # Extract firewall configuration
  firewall_config = local.cluster_config.firewall

  # Determine if using Panorama or standalone
  is_panorama = can(local.firewall_config.panorama)

  # Prepare configuration for the module
  panorama_config = local.is_panorama ? {
    device_group    = local.firewall_config.panorama.device_group
    panorama_device = try(local.firewall_config.panorama.panorama_device, "localhost.localdomain")
    rulebase        = try(local.firewall_config.panorama.rulebase, "pre-rulebase")
  } : null

  standalone_config = !local.is_panorama ? {
    ngfw_device = try(local.firewall_config.standalone.ngfw_device, "localhost.localdomain")
    vsys_name   = try(local.firewall_config.standalone.vsys_name, "vsys1")
  } : null

  location_config = merge(local.standalone_config != null ? { vsys = local.standalone_config } : {},
  local.panorama_config != null ? { panorama = local.panorama_config } : {})

  # Position configuration
  position_config = {
    where    = try(local.cluster_config.position.where, "last")
    pivot    = try(local.cluster_config.position.pivot, null)
    directly = try(local.cluster_config.position.directly, false)
  }
}

# Configure the PAN-OS provider
provider "panos" {}

module "palo_alto_firewall" {
  count = local.firewall_config.type == "palo-alto" ? 1 : 0

  source = "../modules/palo-alto"

  firewall_rules     = try(local.firewall_rules.rules, {})
  firewall_addresses = try(local.firewall_rules.addresses, [])
  firewall_services  = try(local.firewall_rules.services, [])
  position           = local.position_config
  location           = local.location_config
}

# Future: Fortinet module (placeholder)
# module "fortinet_firewall" {
#   count = local.firewall_config.type == "fortinet" ? 1 : 0
#   
#   source = "../modules/fortinet"
#   # ... configuration
# }
