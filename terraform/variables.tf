variable "cluster_name" {
  description = "Name of the cluster to deploy firewall configuration for"
  type        = string
  default     = ""

  validation {
    condition     = var.cluster_name == "" || can(regex("^[a-zA-Z0-9-_]+$", var.cluster_name))
    error_message = "Cluster name must contain only alphanumeric characters, hyphens, and underscores."
  }
}
