variable "firewall_addresses" {
  type = list(object({
    name        = string
    description = optional(string, "")
    tags        = optional(list(string), [])
    ip_netmask  = optional(string, null)
    ip_range    = optional(string, null)
    ip_wildcard = optional(string, null)
    fqdn        = optional(string, null)
  }))
  default = []
}

variable "firewall_services" {
  type = list(object({
    name             = string
    description      = optional(string, "")
    type             = string # tcp, udp
    tags             = optional(list(string), [])
    destination_port = optional(string, null)
    source_port      = string
  }))
  default = []
}

variable "firewall_rules" {
  description = "Map of rule groups containing firewall rules"
  type = map(object({
    description = optional(string, "")
    rules = list(object({
      name                  = string
      description           = optional(string, "")
      rule_type             = optional(string, "universal")
      source_zones          = list(string)
      destination_zones     = list(string)
      source_addresses      = list(string)
      destination_addresses = list(string)
      applications          = list(string)
      services              = list(string)
      source_users          = optional(list(string), [])
      action                = optional(string, "allow")
      log_start             = optional(bool, false)
      log_end               = optional(bool, true)
      log_setting           = optional(string, null)
      disabled              = optional(bool, false)
      schedule              = optional(string, null)
      tags                  = optional(list(string), [])
      group_tag             = optional(string, null)
      negate_source         = optional(bool, false)
      negate_destination    = optional(bool, false)

      profile_setting = optional(object({
        group = optional(list(string), [])
        profiles = optional(object({
          virus             = optional(list(string), [])
          spyware           = optional(list(string), [])
          vulnerability     = optional(list(string), [])
          url_filtering     = optional(list(string), [])
          file_blocking     = optional(list(string), [])
          wildfire_analysis = optional(list(string), [])
          data_filtering    = optional(list(string), [])
        }), null)
      }), null)
    }))
  }))
}

variable "location" {
  type = object({
    vsys = optional(object({
      name        = optional(string, null)
      ngfw_device = optional(string, null)
    }), null)
    shared = optional(object({
      rulebase = optional(string, null)
    }), null)
    panorama = optional(object({
      device_group    = optional(string, null)
      panorama_device = optional(string, null)
      rulebase        = optional(string, null)
    }), null)
  })
  description = "The location of the firewall"
}

variable "position" {
  type = object({
    where    = string
    pivot    = optional(string, null)
    directly = optional(bool, false)
  })
  description = "The position of the firewall rules"

  validation {
    condition     = contains(["first", "last", "after", "before"], var.position.where)
    error_message = "where must be one of first, last, after, or before"
  }
  validation {
    condition     = contains(["after", "before"], var.position.where) ? var.position.pivot != null : true
    error_message = "pivot is required when where is after or before"
  }
}
