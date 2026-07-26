variable "environment" {
  description = "Target environment name."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,62}$", var.environment))
    error_message = "environment must use lowercase letters, numbers, and hyphens."
  }
}

variable "common_tags" {
  description = "Non-secret tags applied by provider-specific modules."
  type        = map(string)
  default     = {}
}
