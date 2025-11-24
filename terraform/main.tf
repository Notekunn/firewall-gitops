terraform {
  required_providers {
    panos = {
      source  = "paloaltonetworks/panos"
      version = "~> 2.0.5"
    }
    checkpoint = {
      source  = "CheckPointSW/checkpoint"
      version = "~> 2.11.0"
    }
    bigip = {
      source  = "F5Networks/bigip"
      version = "~> 1.24.0"
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

  # CheckPoint domain configuration
  checkpoint_location_config = {
    domain = try(local.firewall_config.checkpoint.domain, null)
  }

  # F5 WAF configuration
  f5_location_config = {
    partition = try(local.firewall_config.f5.partition, "Common")
  }

  f5_global_config = {
    irule_name = try(local.firewall_config.f5.irule_name, "gitops_ip_filter")
  }

  # F5 IP lists from single file or multiple files
  ip_lists_from_single = try(local.single_file_data.ip_lists, {})
  ip_lists_from_multi = try(
    merge([for data in local.objects_data_list : try(data.ip_lists, {})]...),
    {}
  )
  f5_ip_lists = merge(local.ip_lists_from_single, local.ip_lists_from_multi)

  # Position configuration
  position_config = {
    where    = try(local.cluster_config.position.where, "last")
    pivot    = try(local.cluster_config.position.pivot, null)
    directly = try(local.cluster_config.position.directly, false)
  }
}

# Configure the PAN-OS provider
provider "panos" {}

# Configure the CheckPoint provider
provider "checkpoint" {}

# Configure the F5 BIG-IP provider
provider "bigip" {}

module "palo_alto_firewall" {
  count = local.firewall_config.type == "palo-alto" ? 1 : 0

  source = "../modules/palo-alto"

  firewall_rules     = local.firewall_rules
  firewall_addresses = local.firewall_addresses
  firewall_services  = local.firewall_services
  position           = local.position_config
  location           = local.location_config
  global = {
    log_setting = try(local.cluster_config.log_setting, null)
  }
}

module "fortinet_firewall" {
  count = local.firewall_config.type == "fortinet" ? 1 : 0

  source = "../modules/fortinet"

  firewall_rules     = local.firewall_rules
  firewall_addresses = local.firewall_addresses
  firewall_services  = local.firewall_services
  position           = local.position_config
  location           = local.location_config
}

module "checkpoint_firewall" {
  count = local.firewall_config.type == "checkpoint" ? 1 : 0

  source = "../modules/checkpoint"

  firewall_rules     = local.firewall_rules
  firewall_addresses = local.firewall_addresses
  firewall_services  = local.firewall_services
  position           = local.position_config
  location           = local.checkpoint_location_config
  global = {
    layer_name   = try(local.cluster_config.checkpoint.layer_name, "Network")
    auto_publish = try(local.cluster_config.checkpoint.auto_publish, true)
    install_on   = try(local.cluster_config.checkpoint.install_on, ["Policy Targets"])
    track_type   = try(local.cluster_config.checkpoint.track_type, "Log")
    track_settings = try(local.cluster_config.checkpoint.track_settings, {
      accounting              = false
      alert                   = "none"
      enable_firewall_session = false
      per_connection          = true
      per_session             = false
    })
  }
}

module "f5_waf" {
  count = local.firewall_config.type == "f5-waf" ? 1 : 0

  source = "../modules/f5-waf"

  ip_lists = local.f5_ip_lists
  location = local.f5_location_config
  global   = local.f5_global_config
}
output "rules" {
  value = local.firewall_rules
}
output "addresses" {
  value = local.firewall_addresses
}
output "services" {
  value = local.firewall_services
}
