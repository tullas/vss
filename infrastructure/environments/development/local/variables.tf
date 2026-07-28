variable "project" {
  description = "VSS project name."
  type        = string
  default     = "vss"
}

variable "environment" {
  description = "VSS environment name."
  type        = string
  default     = "development"
  validation {
    condition     = var.environment == "development"
    error_message = "The local provider root is only for the development environment."
  }
}

variable "minio_root_user" {
  description = "S3 root access key, supplied through an ignored local tfvars file. The legacy variable name is retained for compatibility."
  type        = string
  sensitive   = true
}

variable "minio_root_password" {
  description = "S3 root secret key, supplied through an ignored local tfvars file. The legacy variable name is retained for compatibility."
  type        = string
  sensitive   = true
}

variable "api_port" {
  description = "Host port for the S3-compatible API."
  type        = number
  default     = 9000
}
