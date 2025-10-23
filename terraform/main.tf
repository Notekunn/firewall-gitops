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

  # Path to cluster directory
  cluster_dir = "${path.module}/../clusters/${local.cluster_name}"

  # Read cluster configuration
  cluster_config_raw = file("${local.cluster_dir}/cluster.yaml")
  cluster_config     = yamldecode(local.cluster_config_raw)

  # Check if using single file or multiple files in objects/ folder
  has_single_objects_file = fileexists("${local.cluster_dir}/objects.yaml")
  has_objects_folder      = try(length(fileset("${local.cluster_dir}/objects", "*.yaml")) > 0, false)

  # Read configuration from single file or multiple files
  # Single file mode (backward compatible)
  single_file_data = local.has_single_objects_file ? yamldecode(file("${local.cluster_dir}/objects.yaml")) : yamldecode("{}")

  # Multiple files mode - read all YAML files from objects/ folder
  objects_files = local.has_objects_folder ? fileset("${local.cluster_dir}/objects", "*.yaml") : []
  objects_data_list = [
    for f in local.objects_files : yamldecode(file("${local.cluster_dir}/objects/${f}"))
  ]

  # Merge addresses from all files
  addresses_from_single = try(local.single_file_data.addresses, [])
  addresses_from_multi  = flatten([for data in local.objects_data_list : try(data.addresses, [])])
  firewall_addresses    = concat(local.addresses_from_single, local.addresses_from_multi)

  # Merge services from all files
  services_from_single = try(local.single_file_data.services, [])
  services_from_multi  = flatten([for data in local.objects_data_list : try(data.services, [])])
  firewall_services    = concat(local.services_from_single, local.services_from_multi)

  # Merge rules from all files (rules are maps, so we need to merge them)
  rules_from_single = try(local.single_file_data.rules, [])
  rules_from_multi  = flatten([for data in local.objects_data_list : try(data.rules, [])])
  firewall_rules    = concat(local.rules_from_single, local.rules_from_multi)

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

  firewall_rules     = local.firewall_rules
  firewall_addresses = local.firewall_addresses
  firewall_services  = local.firewall_services
  position           = local.position_config
  location           = local.location_config
  auto_commit        = try(local.cluster_config.auto_commit.enabled, true)
  commit_description = try(local.cluster_config.auto_commit.commit_description, "Committed by Terraform GitOps")
  commit_admins      = try(local.cluster_config.auto_commit.commit_admins, [])
}

# Future: Fortinet module (placeholder)
# module "fortinet_firewall" {
#   count = local.firewall_config.type == "fortinet" ? 1 : 0
#   
#   source = "../modules/fortinet"
#   # ... configuration
# }

output "rules" {
  value = local.firewall_rules
}
output "addresses" {
  value = local.firewall_addresses
}
output "services" {
  value = local.firewall_services
}
