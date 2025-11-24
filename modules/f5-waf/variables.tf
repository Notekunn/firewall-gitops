variable "ip_lists" {
  description = "IP lists for blocklist and whitelist"
  type = object({
    global = optional(object({
      blocklist = optional(list(string), [])
      whitelist = optional(list(string), [])
    }), {})
    domains = optional(map(object({
      blocklist = optional(list(string), [])
      whitelist = optional(list(string), [])
    })), {})
  })
  default = {}
}

variable "location" {
  description = "F5 BIG-IP location configuration"
  type = object({
    partition = optional(string, "Common")
  })
  default = {}
}

variable "global" {
  description = "Global F5 WAF settings"
  type = object({
    irule_name = optional(string, "gitops_ip_filter")
  })
  nullable = true
  default  = {}
}
