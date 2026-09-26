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
    destination_port = string
    source_port      = optional(string, null)
  }))
  default = []
}

variable "firewall_rules" {
  description = "Map firewall rules"
  type = list(object({
    name                  = string
    description           = optional(string, "")
    rule_type             = optional(string, "universal")
    source_zones          = list(string)
    destination_zones     = list(string)
    source_addresses      = list(string)
    destination_addresses = list(string)
    services              = list(string)
    applications          = optional(list(string), ["any"])
    source_users          = optional(list(string), [])
    action                = optional(string, "allow")
    log_start             = optional(bool, false)
    log_end               = optional(bool, true)
    log_setting           = optional(string, null)
    disabled              = optional(bool, false)
    schedule              = optional(string, null)
    expires_at            = optional(string, null)
    change = optional(object({
      ticket   = string
      revision = number
      comment  = string
    }), null)
    tags               = optional(list(string))
    group_tag          = optional(string, null)
    negate_source      = optional(bool, false)
    negate_destination = optional(bool, false)

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

variable "global" {
  type = object({
    log_setting = optional(string, null)
    timezone    = optional(string, "Asia/Bangkok")
  })
  default     = {}
  description = "Global rule-level defaults (fallbacks)"
}

variable "firewall_schedules" {
  description = "PAN-OS schedule objects"
  type = list(object({
    name             = string
    disable_override = optional(string, "yes")
    schedule_type = object({
      non_recurring = optional(list(string), null)
      recurring = optional(object({
        daily = optional(list(string), null)
        weekly = optional(object({
          monday    = optional(list(string), null)
          tuesday   = optional(list(string), null)
          wednesday = optional(list(string), null)
          thursday  = optional(list(string), null)
          friday    = optional(list(string), null)
          saturday  = optional(list(string), null)
          sunday    = optional(list(string), null)
        }), null)
      }), null)
    })
  }))
  default = []
}
