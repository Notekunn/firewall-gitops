variable "firewall_addresses" {
  type = list(object({
    name        = string
    description = optional(string, "")
    tags        = optional(list(string), [])
    ip_netmask  = optional(string, null)
    ip_range    = optional(string, null)
    fqdn        = optional(string, null)
  }))
  default     = []
  description = "List of firewall address objects (hosts and networks)"
}

variable "firewall_services" {
  type = list(object({
    name             = string
    description      = optional(string, "")
    type             = string # tcp, udp
    tags             = optional(list(string), [])
    destination_port = optional(string, null)
    source_port      = optional(string, null)
  }))
  default     = []
  description = "List of firewall service objects"
}

variable "firewall_rules" {
  description = "List of firewall access rules"
  type = list(object({
    name                  = string
    description           = optional(string, "")
    source_zones          = optional(list(string), [])
    destination_zones     = optional(list(string), [])
    source_addresses      = list(string)
    destination_addresses = list(string)
    applications          = optional(list(string), [])
    services              = list(string)
    action                = optional(string, "Accept")
    log_start             = optional(bool, false)
    log_end               = optional(bool, true)
    disabled              = optional(bool, false)
    tags                  = optional(list(string), [])
    negate_source         = optional(bool, false)
    negate_destination    = optional(bool, false)
    vpn                   = optional(string, "Any")
  }))
}

variable "location" {
  type = object({
    domain = optional(string, null)
  })
  description = "The management domain for CheckPoint"
  default     = {}
}

variable "position" {
  type = object({
    where    = string
    pivot    = optional(string, null)
    directly = optional(bool, false)
  })
  description = "The position of the firewall rules"

  validation {
    condition     = contains(["top", "bottom", "above", "below"], var.position.where)
    error_message = "where must be one of top, bottom, above, or below"
  }
  validation {
    condition     = contains(["above", "below"], var.position.where) ? var.position.pivot != null : true
    error_message = "pivot is required when where is above or below"
  }
}

variable "global" {
  type = object({
    layer_name   = optional(string, "Network")
    auto_publish = optional(bool, true)
    install_on   = optional(list(string), ["Policy Targets"])
    track_type   = optional(string, "Log")
    track_settings = optional(object({
      accounting              = optional(bool, false)
      alert                   = optional(string, "none")
      enable_firewall_session = optional(bool, false)
      per_connection          = optional(bool, true)
      per_session             = optional(bool, false)
    }), {})
  })
  nullable    = true
  default     = {}
  description = "Global settings for CheckPoint firewall"
}

variable "ip_lists" {
  description = "IP lists for blocklist and whitelist (global only)"
  type = object({
    global = optional(object({
      blocklist = optional(list(string), [])
      whitelist = optional(list(string), [])
    }), {})
  })
  default = {}
}
